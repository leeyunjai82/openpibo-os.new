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
    cards = pg.eval_on_selector_all('#home_cards .card .name', 'els => els.map(e=>e.textContent)')
    # 카드 이름은 기존 landing.html 과 같아야 한다 (디자인·용어 일관성)
    check('홈 카드가 기존 화면과 같은 이름',
          cards == ['Tools','IDE','Classifier','Chat Bot'], str(cards))
    check('카드 색이 앱별로 다름 (landing 과 동일)',
          len(set(pg.eval_on_selector_all('#home_cards .card',
              'els=>els.map(e=>getComputedStyle(e).borderTopColor)'))) == 4)
    check('상단바가 금색 (기존 header 와 동일)',
          pg.eval_on_selector('.topbar', 'e=>getComputedStyle(e).backgroundColor')
          == 'rgb(249, 195, 0)',
          pg.eval_on_selector('.topbar', 'e=>getComputedStyle(e).backgroundColor'))

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
    check('셸 안: 앱 제목이 감춰짐', not fr.locator('.header-logo').is_visible())
    check('셸 안: THE MAKER 로고가 감춰짐', not fr.locator('#logo_bt').is_visible())
    check('셸 안: 기능 버튼은 남음 (메뉴)', fr.locator('#sidebar_toggle_btn').is_visible())
    check('셸 안: 기능 버튼은 남음 (언어)', fr.locator('#lang-toggle').is_visible())

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
