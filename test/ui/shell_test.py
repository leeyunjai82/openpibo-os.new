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
    errors = []
    pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
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
    check('홈 카드 4개', cards == ['체험','코딩','학습','대화'], str(cards))

    # 4. 코딩 탭 — 서비스가 필요 없으니 바로 iframe
    pg.click('#tabs .tab[data-tab="code"]')
    pg.wait_for_selector('#frame_code.active', timeout=5000)
    check('코딩 탭: 주소가 /app/code', pg.url.endswith('/app/code'), pg.url)
    check('코딩 탭: iframe 이 붙음', pg.is_visible('#frame_code'))
    check('코딩 탭: 페이지 리로드 없음(홈 노드 유지)', pg.locator('#home_pane').count() == 1)

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
    check('전환 화면에 무엇을 기다리는지 표시', '학습' in txt, txt)
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

    # 11. 새로고침해도 그 탭
    pg.set_viewport_size({'width': 1280, 'height': 800})
    pg.goto(BASE + '/app/code', wait_until='networkidle')
    pg.wait_for_timeout(600)
    check('새로고침해도 코딩 탭', pg.is_visible('#frame_code'))

    # 12. window.open 이 한 번도 안 불렸나
    opened = pg.evaluate('window.__openCalls || 0')
    check('새 창이 열리지 않음', opened == 0, str(opened))

    real_errors = [e for e in errors if 'favicon' not in e and 'circulus_logo' not in e]
    check('콘솔 에러 없음', not real_errors, ' | '.join(real_errors[:3]))

    b.close()

print('\n전부 통과' if not failed else f'\n{len(failed)}개 실패: ' + ', '.join(failed))
sys.exit(0 if not failed else 1)
