"""
보드 프로파일 시험. 하드웨어 없이 돈다.

  python3 test/test_board.py

확인하는 것
  - 두 프로파일이 **같은 키 집합**을 갖는지
    (한쪽에만 있는 키는 그 보드에서만 AttributeError 로 터진다. 조용한 버그다)
  - features 플래그가 블록 툴박스의 requires 와 맞물리는지
  - display.driver 가 oled.DRIVERS 에 있는 값인지
  - features.device_class 가 device.py 에 실제로 있는 클래스 이름인지
  - unverified 값을 require() 로 꺼내면 멈추는지
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 기기 밖에서 돌리므로 /home/pi 를 건드리지 않게 한다
os.environ.setdefault('OPENPIBO_HOME', os.path.join(ROOT, '.tmp-test'))
os.makedirs(os.environ['OPENPIBO_HOME'], exist_ok=True)
os.environ.setdefault('OPENPIBO_BOARD', 'pibo')

from openpibo.board import BOARDS, load          # noqa: E402

failed = []


def check(label, ok, detail=''):
  print(f"{'  ok  ' if ok else ' FAIL '} {label}{' — ' + detail if detail else ''}")
  if not ok:
    failed.append(label)


def keyset(d, prefix=''):
  out = set()
  for k, v in d.items():
    out.add(prefix + k)
    if isinstance(v, dict):
      out |= keyset(v, prefix + k + '.')
  return out


print(f"프로파일: {', '.join(BOARDS)}\n")
check('프로파일이 2개 이상', len(BOARDS) >= 2)

profiles = {n: load(n) for n in BOARDS}

# 1. 키 집합이 같아야 한다
sets = {n: keyset(p) for n, p in profiles.items()}
common = set.intersection(*sets.values())
for n, s in sets.items():
  extra = sorted(s - common)
  check(f'{n}: 다른 프로파일에 없는 키가 없음', not extra, ', '.join(extra))

# 2. features 플래그 <-> 툴박스 requires
toolbox = open(os.path.join(ROOT, 'ide/static/customblock_toolbox.js'), encoding='utf-8').read()
used = set(re.findall(r'"requires"\s*:\s*"([a-z0-9_]+)"', toolbox))
print(f'\n툴박스가 쓰는 플래그: {", ".join(sorted(used))}')
for n, p in profiles.items():
  missing = sorted(f for f in used if f not in p['features'])
  check(f'{n}: 툴박스가 쓰는 플래그가 전부 있음', not missing, ', '.join(missing))

# 3. 값의 정합성
DRIVERS = {'ssd1306', 'ili9341', 'st7735'}
device_src = open(os.path.join(ROOT, 'openpibo/device.py'), encoding='utf-8').read()
device_classes = set(re.findall(r'^class\s+(\w+)', device_src, re.M))
print()
for n, p in profiles.items():
  check(f'{n}: display.driver 가 알려진 값', p['display']['driver'] in DRIVERS,
        p['display']['driver'])
  check(f'{n}: device_class 가 실재하는 클래스',
        p['features']['device_class'] in device_classes,
        p['features']['device_class'])
  check(f'{n}: boot.splash 파일이 있음',
        os.path.isfile(os.path.join(ROOT, 'system', p['boot']['splash'])),
        p['boot']['splash'])
  layout = p['network_disp']['layout']
  check(f'{n}: network_disp 레이아웃이 비어 있지 않음', len(layout) > 0, f'{len(layout)}줄')
  bad = [l['text'] for l in layout
         if not set(re.findall(r'\{(\w+)\}', l['text'])) <= {'sn', 'ip', 'ssid', 'os_version'}]
  check(f'{n}: network_disp 가 아는 값만 씀', not bad, '; '.join(bad))

# 4. 확인 안 된 값은 조용히 통과하지 않아야 한다
print()
for n, p in profiles.items():
  try:
    p.unverified.require('display_rst_pin')
    check(f'{n}: unverified.require() 가 빈 값에서 멈춤', False, '멈추지 않았다')
  except ValueError:
    check(f'{n}: unverified.require() 가 빈 값에서 멈춤', True)
  except AttributeError:
    check(f'{n}: [unverified] 절이 있음', False)

print('\n전부 통과' if not failed else f'\n{len(failed)}개 실패: ' + ', '.join(failed))
sys.exit(0 if not failed else 1)
