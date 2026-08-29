"""블록이 뱉는 파이썬이 그 보드에서 실제로 도는 코드인지.

    python3 test/test_block_api.py

왜 필요한가
  블록은 보드마다 다른 코드를 뱉고 있었다. 화면(oled) 블록 12개가

    파이보     from openpibo.oled import Oled
    파이브레인 from openpibo.oled import OledByPiBrain as Oled

  로 갈려 있었고, 통합하면서 파이보 것만 가져오는 바람에 **파이브레인에서
  화면 블록이 전부 엉뚱한 하드웨어(SSD1306 흑백)를 잡았다.**

  블록은 JS 고 라이브러리는 파이썬이라 서로를 모른다. 한쪽만 고치면
  조용히 어긋나고, 기기에 올려 봐야 안다. 여기서 맞물리는지 본다.

  - 생성기가 부르는 메서드가 그 보드의 디스플레이 클래스에 있는지
  - 없는 메서드를 쓰는 블록은 툴박스에서 감춰져 있는지
"""

import ast
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, 'ide/static')

fails = []


def check(name, ok, detail=''):
  print(f'{"  ok  " if ok else " FAIL "} {name}' + (f'  — {detail}' if detail else ''))
  if not ok:
    fails.append(name)


# ── 파이썬 쪽: 각 디스플레이 클래스의 메서드 ────────────────
# import 하면 하드웨어(spidev 등)를 잡으므로 소스를 파싱만 한다.
tree = ast.parse(open(os.path.join(ROOT, 'openpibo/oled.py'), encoding='utf-8').read())
DISPLAY_METHODS = {
  node.name: {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
  for node in tree.body if isinstance(node, ast.ClassDef)
}

# 프로파일의 display.driver -> 클래스 이름 (oled.py 의 DRIVERS 표를 읽는다)
src = open(os.path.join(ROOT, 'openpibo/oled.py'), encoding='utf-8').read()
DRIVERS = dict(re.findall(r"'([a-z0-9]+)':\s*'(\w+)'", src.split('DRIVERS = {')[1].split('}')[0]))


def profile(board):
  """toml 의 [display] 와 [features] 만 읽는다."""
  text = open(os.path.join(ROOT, f'openpibo/profiles/{board}.toml'), encoding='utf-8').read()
  out = {}
  for section in ('display', 'features'):
    part = text.split(f'[{section}]')[1].split('\n[')[0]
    vals = {}
    for line in part.split('\n'):
      m = re.match(r'\s*([a-z0-9_]+)\s*=\s*(true|false|"[^"]*"|\d+)', line)
      if m:
        v = m.group(2)
        vals[m.group(1)] = (True if v == 'true' else False if v == 'false'
                            else v[1:-1] if v.startswith('"') else int(v))
    out[section] = vals
  return out


# ── JS 쪽: 생성기가 부르는 oled 메서드 ──────────────────────
gen = open(os.path.join(STATIC, 'customblock_callback.js'), encoding='utf-8').read()
BLOCK_CALLS = {}          # 블록 이름 -> {부르는 메서드}
for m in re.finditer(r"^Blockly\.Python\.forBlock\['([a-z0-9_]+)'\][\s\S]*?(?=^Blockly\.Python|^//\s*Blockly\.Python|\Z)",
                     gen, re.M):
  body = m.group(0)
  calls = set(re.findall(r'\boled\.([a-z_]\w*)\(', body))
  if calls:
    BLOCK_CALLS[m.group(1)] = calls

print(f'화면(oled)을 부르는 블록 {len(BLOCK_CALLS)}개')
print(f'디스플레이 클래스 {", ".join(sorted(DISPLAY_METHODS))}\n')

# ── 1. 생성기가 보드에 안 매여 있어야 한다 ──────────────────
print('── 생성기가 보드 중립인가 ──')
check('oled 클래스를 하드코딩하지 않음',
      'import Oled;' not in gen and 'OledByPiBrain' not in gen,
      'get_display() 를 써야 두 보드에서 같은 코드가 돈다')
check('get_display 를 씀', "from openpibo.oled import get_display" in gen)

# ── 2. 툴박스에 보이는 블록의 메서드가 그 보드 클래스에 있어야 한다 ──
print('\n── 블록이 부르는 메서드가 보드 클래스에 있나 ──')
node_script = r'''
const fs=require('fs'),path=require('path'),vm=require('vm');
const ROOT=process.argv[1], board=process.argv[2];
function feats(){const s=fs.readFileSync(path.join(ROOT,'openpibo/profiles',board+'.toml'),'utf8')
  .split(/^\[features\]$/m)[1].split(/^\[/m)[0];const o={};
  for(const l of s.split('\n')){const m=l.match(/^\s*([a-z0-9_]+)\s*=\s*(true|false|"[^"]*")/);
    if(m)o[m[1]]=m[2]==='true'?true:m[2]==='false'?false:m[2].slice(1,-1);}return o;}
const sb={console:{warn(){},log(){}},window:{__BOARD__:{name:board,features:feats()}},
  translations:new Proxy({},{get:(_,k)=>({ko:String(k),en:String(k)})}),color_type:new Proxy({},{get:()=>'#000'})};
sb.window.console=sb.console;vm.createContext(sb);
for(const f of ['board_filter.js','customblock_toolbox.js'])
  vm.runInContext(fs.readFileSync(path.join(ROOT,'ide/static',f),'utf8'),sb,{filename:f});
const t=new Set();(function c(n){if(Array.isArray(n))return n.forEach(c);
  if(!n||typeof n!=='object')return;if(n.kind==='block'&&n.type)t.add(n.type);if(n.contents)c(n.contents);})
  (vm.runInContext('toolbox_dict',sb).ko);
console.log(JSON.stringify([...t]));
'''
have_node = subprocess.run(['which', 'node'], capture_output=True).returncode == 0
if not have_node:
  print('  건너뜀 — node 가 없습니다')
else:
  for board in ('pibo', 'pibrain'):
    prof = profile(board)
    cls = DRIVERS.get(prof['display'].get('driver'))
    check(f'{board}: display.driver 가 아는 클래스로 이어짐', cls in DISPLAY_METHODS,
          f"driver={prof['display'].get('driver')} -> {cls}")
    if cls not in DISPLAY_METHODS:
      continue
    shown = set(json.loads(subprocess.run(
      ['node', '-e', node_script, ROOT, board],
      capture_output=True, text=True, check=True).stdout))
    missing = []
    for blk, calls in sorted(BLOCK_CALLS.items()):
      if blk not in shown:
        continue                      # 서랍에 없으면 아이가 만들 수 없다
      gap = calls - DISPLAY_METHODS[cls]
      if gap:
        missing.append(f'{blk} -> {cls}.{"/".join(sorted(gap))}()')
    check(f'{board}({cls}): 서랍의 화면 블록이 다 있는 메서드를 부름',
          not missing, ' | '.join(missing))

print()
if fails:
  print(f'{len(fails)} 개 실패')
  sys.exit(1)
print('전부 통과')
