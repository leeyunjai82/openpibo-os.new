"""tools/launch.py — 보드가 자기 tools 앱을 고르는지.

파이브레인에 파이보 화면이 뜨면 "모션" 탭 전체가 죽은 화면이 된다.
반대도 마찬가지다. 여기서 막는다. **하드웨어가 필요 없다.**
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import launch  # noqa: E402

fails = []


def check(name, cond, detail=''):
  if cond:
    print(f'  ok   {name}')
  else:
    print(f' FAIL  {name}  {detail}')
    fails.append(name)


print('── 보드 -> tools 앱 폴더 ──')
pibo = launch.app_dir_for('pibo')
pibrain = launch.app_dir_for('pibrain')

check('파이보는 tools/', os.path.basename(pibo) == 'tools', pibo)
check('파이브레인은 tools/pibrain/', os.path.basename(pibrain) == 'pibrain', pibrain)
check('둘이 다른 폴더', pibo != pibrain)
# 모르는 보드에서 죽는 것보다 파이보 것으로 뜨는 편이 낫다(예전 그대로).
check('모르는 보드는 파이보로', launch.app_dir_for('무엇') == pibo)

print('── 두 앱이 다 갖춰져 있나 ──')
for name, d in (('파이보', pibo), ('파이브레인', pibrain)):
  for f in ('run_tools.py', 'templates/index.html', 'static/index.css', 'static/index.js'):
    check(f'{name} {f}', os.path.exists(os.path.join(d, f)))

print('── 파이브레인 앱이 셸 뒤에서 열릴 준비가 됐나 ──')
tpl = open(os.path.join(pibrain, 'templates/index.html'), encoding='utf-8').read()
js = open(os.path.join(pibrain, 'static/index.js'), encoding='utf-8').read()
css = open(os.path.join(pibrain, 'static/index.css'), encoding='utf-8').read()

# 프록시가 ../static/ 만 고쳐 준다. /static/ 이 남아 있으면 셸 안에서 404 다.
check('정적 경로가 상대 경로', 'href="/static/' not in tpl and 'src="/static/' not in tpl,
      '아직 /static/ 절대 경로가 있습니다')
check('theme.css 가 index.css 뒤에',
      tpl.index('theme.css') > tpl.index('index.css'),
      '순서가 뒤집히면 변수 재정의가 진다')
check('iframe 판별(embedded) 있음', "classList.add('embedded')" in tpl)
check('html.embedded 규칙 있음', 'html.embedded' in css)
# fetch/EventSource 가 /led, /button_stream 같은 절대 경로를 쓴다.
# 셸 뒤에서는 /tools/led 여야 한다.
check('__BASE__ 앞가지 있음', 'window.__BASE__' in js and 'function __u(' in js)
# 주석에는 왜 뺐는지가 적혀 있다. 주석을 걷어내고 **코드**만 본다.
js_code = re.sub(r'/\*.*?\*/', '', js, flags=re.S)
js_code = re.sub(r'^\s*//.*$', '', js_code, flags=re.M)
check('허브 서비스 종료 호출 없음', 'enable=off' not in js_code,
      '셸이 서비스 수명을 쥔다 — 앱이 자기를 끄면 싸운다')

print('── 파이보 tools 는 그대로인가 ──')
ptpl = open(os.path.join(pibo, 'templates/index.html'), encoding='utf-8').read()
check('파이보도 상대 경로', 'href="/static/' not in ptpl and 'src="/static/' not in ptpl)

print('── socket.io 번들 (userAgent 오타) ──')
# 어느 시점에 navigator.userAgent 가 통째로 userAgentData 로 치환돼 있었다.
# userAgentData 는 문자열이 아니라 객체라 .toLowerCase() 에서 던진다.
# 보안 컨텍스트(https, localhost)에서만 정의되므로 LAN http 로 쓸 때는
# 조용히 넘어갔지만, 켜지는 순간 socket.io 가 통째로 안 뜬다.
for rel in ('ide/static/socket.io.min.js',
            'tools/static/socket.io.min.js',
            'classifier/static/socket.io.min.js'):
  body = open(os.path.join(ROOT, rel), encoding='utf-8', errors='replace').read()
  check(rel, 'navigator.userAgentData' not in body, 'userAgentData 오타가 남아 있습니다')

print()
if fails:
  print(f'{len(fails)} 개 실패')
  sys.exit(1)
print('전부 통과')
