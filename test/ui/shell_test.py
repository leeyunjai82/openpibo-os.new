"""셸을 실제 브라우저로 몰아 본다. 탭 전환·라우팅·모달·배지."""
import glob, os, sys
from playwright.sync_api import sync_playwright

# playwright 가 심어 둔 크로미움을 찾는다. 버전 폴더 이름이 환경마다 다르다.
_c = sorted(glob.glob('/opt/pw-browsers/chromium*/chrome-linux/chrome'))
CHROME = os.environ.get('CHROME') or (_c[-1] if _c else None)
if not CHROME:
    print('크로미움을 찾지 못했습니다. CHROME=<경로> 로 지정하세요.'); sys.exit(2)

BASE = 'http://127.0.0.1:18080'
failed = []

def check(label, ok, detail=''):
    print(f"{'  ok  ' if ok else ' FAIL '} {label}" + (f' — {detail}' if detail else ''))
    if not ok: failed.append(label)

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME,
                           args=['--no-sandbox'])
    pg = b.new_page(viewport={'width': 1280, 'height': 800})
    # 셸 자신의 에러만 센다. iframe 안 앱(IDE/tools)의 에러는 셸 문제가 아니고,
    # 하니스에는 그 앱들의 뒤쪽이 없어서 원래 에러가 난다.
    errors = []

    def _console(m):
        if m.type != 'error':
            return
        url = (m.location or {}).get('url', '')
        if 'shell.js' in url or url.rstrip('/').endswith(':18080') or '/app/' in url:
            errors.append(m.text)

    pg.on('console', _console)
    pg.on('pageerror', lambda e: errors.append(str(e)))

    pg.goto(BASE, wait_until='networkidle')

    # 1. 탭이 그려졌나
    tabs = pg.eval_on_selector_all('#tabs .tab', 'els => els.map(e => e.textContent)')
    check('상단 탭 5개', tabs == ['홈','체험','코딩','학습','대화'], str(tabs))

    # 2. 보드 이름이 주입됐나
    check('보드 배지', pg.inner_text('#board_label') == '파이브레인',
          pg.inner_text('#board_label'))

    # 3. 홈이 기본
    check('홈이 기본 화면', pg.is_visible('#home_pane'))
    cards = pg.eval_on_selector_all('#home_cards .card .name',
        'els => els.map(e=>e.textContent.trim().split(" ")[0])')
    # 카드 이름은 탭과 같은 한글이어야 한다. 탭엔 "학습", 카드엔 "Classifier" 면
    # 같은 화면인지 아이가 알 수 없다.
    check('홈 카드 이름이 탭과 같음', cards == ['체험','코딩','학습','대화'], str(cards))
    icons = set(pg.eval_on_selector_all('#home_cards .card .card-icon',
        'els=>els.map(e=>getComputedStyle(e).color)'))
    check('카드 아이콘 색이 앱별로 다름 (길찾기)', len(icons) == 4, str(len(icons)))
    # 심리스의 기준: 셸 바탕이 디자인 토큰(--t-bg)과 일치
    bg = pg.evaluate('getComputedStyle(document.body).backgroundColor')
    check('셸 바탕이 디자인 토큰과 일치', bg == 'rgb(245, 247, 251)', bg)

    # 여기까지는 iframe 이 하나도 없다. 이 시점의 에러만 셸 것이다.
    # 아래에서 진짜 IDE 를 붙이면 그 앱 자신의 에러(io/socket 미정의 등)가 섞이는데,
    # 하니스에 그 앱의 뒤쪽이 없어서 나는 것이라 셸 문제가 아니다.
    shell_errors = list(errors)

    # 4. 코딩 탭 — 서비스가 필요 없으니 바로 iframe
    pg.click('#tabs .tab[data-tab="code"]')
    pg.wait_for_selector('#frame_code.active', timeout=5000)
    check('코딩 탭: 주소가 /app/code', pg.url.endswith('/app/code'), pg.url)
    check('코딩 탭: iframe 이 붙음', pg.is_visible('#frame_code'))
    check('코딩 탭: 페이지 리로드 없음(홈 노드 유지)', pg.locator('#home_pane').count() == 1)

    # 4b. 셸 안에서는 앱의 중복 브랜딩이 감춰져야 한다.
    #     (로고 두 개, 바 두 겹으로 보이던 것)
    #
    # iframe 이 다 뜰 때까지 기다린다. 안 기다리면 아직 그려지지 않은 버튼을
    # "감춰졌다"고 잘못 읽는다 — 통과해도 실제로 확인한 게 없는 상태가 된다.
    pg.wait_for_function(
        '() => { const f = document.getElementById("frame_code");'
        '  return f && f.contentDocument'
        '      && f.contentDocument.readyState === "complete"'
        '      && f.contentDocument.querySelector("#sidebar_toggle_btn"); }',
        timeout=15000)

    embedded = pg.eval_on_selector(
        '#frame_code', 'f=>f.contentDocument.documentElement.classList.contains("embedded")')
    check('셸 안: 앱이 embedded 를 인식', embedded)
    fr = pg.frame_locator('#frame_code')
    # 바가 한 줄이어야 한다: 앱 헤더는 통째로 감추고, 그 안의 조작만
    # 셸 상단바로 올라온다 (embed.js -> shell.js).
    hdr = pg.eval_on_selector(
        '#frame_code',
        'f=>{const h=f.contentDocument.querySelector("header.title");'
        ' return h ? getComputedStyle(h).display : "없음";}')
    check('셸 안: 앱 헤더가 통째로 감춰짐 (바 한 줄)', hdr == 'none', hdr)

    # 심리스의 핵심: 셸과 iframe 안 앱의 바탕색이 픽셀 단위로 같아야
    # 경계가 보이지 않는다. theme.css 가 양쪽에 같은 토큰을 준다.
    shell_bg = pg.evaluate('getComputedStyle(document.body).backgroundColor')
    app_bg = pg.eval_on_selector('#frame_code',
        'f=>getComputedStyle(f.contentDocument.body).backgroundColor')
    check('셸과 앱의 바탕색이 같음 (심리스)', shell_bg == app_bg,
          f'{shell_bg} vs {app_bg}')

    pg.wait_for_selector('#app_actions > *', timeout=10000)
    titles = pg.eval_on_selector_all('#app_actions > *', 'els=>els.map(e=>e.title)')
    check('IDE 조작이 상단바로 올라옴',
          titles == ['파일 목록', '초기화', '언어', '전체화면'], str(titles))

    # 올라온 버튼이 **실제로 앱을 조작해야** 의미가 있다. 눌러서 확인한다.
    lang = lambda: pg.eval_on_selector(
        '#frame_code', 'f=>f.contentDocument.getElementById("language").value')
    was = lang()
    pg.locator('#app_actions button[title="언어"]').click()
    pg.wait_for_timeout(500)
    check('상단바 EN 이 앱 언어를 바꿈', lang() != was, f'{was} -> {lang()}')

    collapsed = lambda: pg.eval_on_selector(
        '#frame_code',
        'f=>f.contentDocument.getElementById("browser_en")'
        '   .classList.contains("collapsed")')
    was_c = collapsed()
    pg.locator('#app_actions button[title="파일 목록"]').click()
    pg.wait_for_timeout(500)
    check('상단바 메뉴가 앱 파일패널을 접음', collapsed() != was_c,
          f'{was_c} -> {collapsed()}')
    pg.locator('#app_actions button[title="파일 목록"]').click()
    pg.wait_for_timeout(400)

    # 전체화면도 상단바에서 눌러 확인
    pg.locator('#app_actions button[title="전체화면"]').click()
    pg.wait_for_timeout(700)
    check('상단바 전체화면이 실제로 동작',
          pg.eval_on_selector('#frame_code', 'f=>!!f.contentDocument.fullscreenElement'))
    pg.evaluate('()=>{ if (document.fullscreenElement) document.exitFullscreen(); }')
    pg.wait_for_timeout(400)

    # 넓은 화면에서 하단 탭바 자리를 비워 두면 안 된다 (흰 띠가 남았었다)
    check('넓은 화면: 아래 빈 띠 없음',
          pg.eval_on_selector('#stage', 'e=>getComputedStyle(e).bottom') == '0px',
          pg.eval_on_selector('#stage', 'e=>getComputedStyle(e).bottom'))

    # 포트로 직접 열면 예전 그대로여야 한다
    pg_d = b.new_page(viewport={'width': 1280, 'height': 800})
    pg_d.goto(BASE + '/ide', wait_until='networkidle')
    pg_d.wait_for_timeout(1500)
    check('직접 열기: embedded 아님',
          not pg_d.evaluate('document.documentElement.classList.contains("embedded")'))
    check('직접 열기: 앱 제목 그대로', pg_d.locator('.header-logo').is_visible())
    check('직접 열기: THE MAKER 로고 그대로', pg_d.locator('#logo_bt').is_visible())
    pg_d.close()

    # 5. 뒤로가기가 홈으로
    pg.go_back()
    pg.wait_for_timeout(400)
    check('뒤로가기 → 홈', pg.is_visible('#home_pane') and not pg.is_visible('#frame_code'))

    # 6. 앞으로가기
    pg.go_forward()
    pg.wait_for_timeout(400)
    check('앞으로가기 → 코딩', pg.is_visible('#frame_code'))

    # 7. 서비스가 필요한 탭 — 전환 화면이 뜨고 실패로 끝나야 한다(뒤쪽 없음)
    pg.click('#tabs .tab[data-tab="learn"]')
    pg.wait_for_selector('#switching.on', timeout=5000)
    check('학습 탭: 전환 화면이 뜸', pg.is_visible('#switching'))
    txt = pg.inner_text('#switch_title')
    check('전환 화면이 누른 탭 이름을 씀', '학습' in txt, txt)
    check('한국어 조사가 맞음', '학습 를' not in txt, txt)

    # 8. 코딩 iframe 은 살아 있어야 한다 (keep: true)
    check('코딩 iframe 이 유지됨(편집 내용 보존)', pg.locator('#frame_code').count() == 1)

    # 9. 설정 모달
    # 실패 화면: 스피너가 멈추고 실패로 보여야 한다
    pg.wait_for_selector('#switching.failed', timeout=12000)
    check('실패하면 스피너가 멈춤',
          pg.eval_on_selector('.spin', 'e=>getComputedStyle(e).animationName') == 'none')
    detail = pg.inner_text('#switch_detail')
    check('실패 문장에 개발자 용어가 안 섞임',
          'systemctl' not in detail and '.service' not in detail, detail)
    check('개발자용 내용은 따로 표시', pg.is_visible('#switch_tech'),
          pg.inner_text('#switch_tech'))

    pg.click('#btn_settings')
    pg.wait_for_selector('#modal_settings.on', timeout=3000)
    check('설정 모달 열림', pg.is_visible('#modal_settings'))
    pg.wait_for_timeout(700)
    info = pg.inner_text('#info_kv')
    check('시스템 정보가 채워짐', '파이브레인' in info and '192.168.0.42' in info,
          info.replace('\n', ' ')[:80])
    check('온도가 기계 출력이 아님', "temp=" not in info,
          [l for l in info.split('\n') if 'C' in l][:1])

    pg.click('.settings-tabs button[data-pane="wifi"]')
    pg.wait_for_timeout(900)
    opts = pg.eval_on_selector_all('#wifi_ssid option', 'els => els.map(e=>e.value)')
    check('와이파이 목록을 받아옴', 'pibo-classroom' in opts, str(opts))

    pg.click('.settings-tabs button[data-pane="log"]')
    pg.wait_for_timeout(600)
    check('실행 기록이 보임', '안녕하세요' in pg.inner_text('#log_view'))

    pg.keyboard.press('Escape')
    pg.wait_for_timeout(300)
    check('Esc 로 모달 닫힘', not pg.is_visible('#modal_settings'))

    # 10. 좁은 화면 → 하단 탭바
    pg.set_viewport_size({'width': 480, 'height': 800})
    pg.wait_for_timeout(300)
    check('좁으면 상단 탭 숨김', not pg.is_visible('#tabs .tab[data-tab="code"]'))
    check('좁으면 하단 탭바 표시', pg.is_visible('#bottom_tabs .tab[data-tab="code"]'))

    # 10b. 폰 크기 — 진짜 모바일 컨텍스트로 다시 연다
    pg_m = b.new_page(viewport={'width': 360, 'height': 640},
                      is_mobile=True, has_touch=True, device_scale_factor=2)
    pg_m.goto(BASE, wait_until='networkidle')
    pg_m.wait_for_timeout(1200)
    check('폰 360px: 가로 스크롤 없음',
          not pg_m.evaluate('document.documentElement.scrollWidth > '
                            'document.documentElement.clientWidth'),
          f"scrollWidth={pg_m.evaluate('document.documentElement.scrollWidth')}")
    tb = pg_m.eval_on_selector('#bottom_tabs .tab',
        'e=>{const r=e.getBoundingClientRect();return Math.round(r.height)}')
    check('폰: 하단 탭 터치 크기 44px 이상', tb >= 44, f'{tb}px')
    # 배지는 좁을 때 글자가 사라진다. 뜻 없는 점만 남으면 안 된다.
    icon = pg_m.eval_on_selector('#badge_cam', 'e=>getComputedStyle(e,"::after").content')
    check('폰: 배지가 뜻 있는 아이콘을 가짐', icon and icon not in ('none', '""'), icon)
    # dvh / safe-area 를 실제로 쓰는지
    css = pg_m.evaluate("[...document.styleSheets].map(s=>[...s.cssRules].map(r=>r.cssText).join('')).join('')")
    check('폰: 100dvh 로 높이를 잡음', 'dvh' in css)
    check('폰: safe-area-inset 을 씀 (viewport-fit=cover 와 짝)',
          'safe-area-inset' in css)
    pg_m.close()

    # 11. 새로고침해도 그 탭
    pg.set_viewport_size({'width': 1280, 'height': 800})
    pg.goto(BASE + '/app/code', wait_until='networkidle')
    pg.wait_for_timeout(600)
    check('새로고침해도 코딩 탭', pg.is_visible('#frame_code'))

    # 11b. IDE 는 블록/파이썬 중 **하나만** 보여야 한다.
    # 처음 열었을 때 둘 다 보이면 CSS 가 깨진 것으로 읽힌다.
    # (예전에는 socket 의 init 이 와야만 한쪽이 감춰졌다 —
    #  뒤쪽이 늦거나 없으면 두 편집기가 위아래로 겹쳐 보였다.)
    fr = None
    for f in pg.frames:
        if f != pg.main_frame and '/ide' in f.url:
            fr = f
    if fr is None:
        check('IDE iframe 을 찾음', False)
    else:
        try:
            fr.wait_for_function("() => document.readyState === 'complete'", timeout=8000)
        except Exception:
            pass
        shown = fr.evaluate(
            "() => ['blocklyDiv','codeDiv'].filter("
            "  id => { const e = document.getElementById(id);"
            "          return e && getComputedStyle(e).display !== 'none'; })")
        check('IDE 편집기는 한 번에 하나만', shown == ['blocklyDiv'], str(shown))
        checked = fr.evaluate(
            "() => Array.from(document.querySelectorAll('div[name=codetype] button'))"
            "  .filter(b => b.classList.contains('checked')).map(b => b.name)")
        check('IDE 전환 버튼도 블록에 켜져 있음', checked == ['block'], str(checked))

    # 12. window.open 이 한 번도 안 불렸나
    opened = pg.evaluate('window.__openCalls || 0')
    check('새 창이 열리지 않음', opened == 0, str(opened))

    real_errors = [e for e in shell_errors
                   if 'favicon' not in e and 'circulus_logo' not in e]
    check('셸 자신의 콘솔 에러 없음 (iframe 안 앱은 별도)',
          not real_errors, ' | '.join(real_errors[:3]))

    b.close()

print('\n전부 통과' if not failed else f'\n{len(failed)}개 실패: ' + ', '.join(failed))
sys.exit(0 if not failed else 1)
