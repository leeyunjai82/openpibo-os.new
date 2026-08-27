/*
 * 블록 정의 · 코드 생성기 · 번역 메시지가 서로 맞물리는지.
 *
 *   node test/js/blocks_messages.test.js
 *
 * 확인하는 것
 *   - 툴박스에 보이는 커스텀 블록에 파이썬 생성기가 다 있는지
 *     (파이브레인 레포는 안 쓰는 생성기를 "주석 처리"로 껐다. 우리는 보드 필터로
 *      **툴박스에서만** 감추므로 생성기는 전부 살아 있어야 한다)
 *   - ko.js 와 en.js 의 키 집합이 같은지
 *     (en.js 에 SPEECH_GTTS 가 통째로 빠져 있었다 — 영어에서 한글이 섞여 나왔다)
 *   - 메시지의 %N 개수가 블록 args0 개수를 넘지 않는지
 *     (en.js 의 SPEECH_OSTT 가 인자 3개짜리 블록에 %4 를 썼다.
 *      영어로 바꾸는 순간 그 블록 생성이 통째로 던진다)
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '../..');
const STATIC = path.join(ROOT, 'ide/static');

let failed = 0;
function check(label, ok, detail) {
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${label}${detail ? ' — ' + detail : ''}`);
  if (!ok) failed++;
}

/* ── 블록 정의를 진짜로 평가해서 얻는다 ────────────────────
   정규식으로 긁으면 /* *\/ 로 죽여 둔 블록까지 세게 된다.
   Blockly 를 흉내낸 껍데기에 defineBlocksWithJsonArray 만 받아 챙긴다. */
function loadBlockDefs() {
  const defs = [];
  const sandbox = {
    console,
    Blockly: {
      defineBlocksWithJsonArray: (arr) => defs.push(...arr),
      Msg: {},
      Extensions: { register: () => {}, registerMutator: () => {} },
      fieldRegistry: { register: () => {} },
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(STATIC, 'customblock.js'), 'utf8'),
                  sandbox, { filename: 'customblock.js' });
  return defs;
}

/* ── 언어 파일의 Blockly.Msg 를 읽는다 ──────────────────── */
function loadMsg(file) {
  const sandbox = { console, Blockly: { Msg: {} } };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(STATIC, file), 'utf8'), sandbox, { filename: file });
  return sandbox.Blockly.Msg;
}

/* ── 살아 있는 파이썬 생성기 ────────────────────────────── */
function loadGenerators() {
  const src = fs.readFileSync(path.join(STATIC, 'customblock_callback.js'), 'utf8');
  const live = new Set();
  for (const line of src.split('\n')) {
    const m = line.match(/^Blockly\.Python\.forBlock\['([a-z0-9_]+)'\]/);
    if (m) live.add(m[1]);
  }
  return live;
}

const defs = loadBlockDefs();
const byType = new Map(defs.map((d) => [d.type, d]));
const live = loadGenerators();
const ko = loadMsg('ko.js');
const en = loadMsg('en.js');

console.log(`블록 정의 ${defs.length}개 / 파이썬 생성기 ${live.size}개`);
console.log(`ko.js ${Object.keys(ko).length}키 / en.js ${Object.keys(en).length}키\n`);

/* 1. 정의된 블록에는 생성기가 있어야 한다 */
const noGen = [...byType.keys()].filter((t) => !live.has(t));
check('정의된 블록에 파이썬 생성기가 다 있음', noGen.length === 0, noGen.join(', '));

/* 2. ko / en 키 집합이 같아야 한다 */
const koKeys = new Set(Object.keys(ko));
const enKeys = new Set(Object.keys(en));
const onlyKo = [...koKeys].filter((k) => !enKeys.has(k));
const onlyEn = [...enKeys].filter((k) => !koKeys.has(k));
check('ko 에만 있는 키 없음', onlyKo.length === 0, onlyKo.join(', '));
check('en 에만 있는 키 없음', onlyEn.length === 0, onlyEn.join(', '));

/* 3. message0 의 %N 이 args0 개수를 넘지 않아야 한다 */
function maxIndex(msg) {
  let max = 0;
  for (const m of String(msg).matchAll(/%(\d+)/g)) max = Math.max(max, Number(m[1]));
  return max;
}
for (const [langName, msgs] of [['ko', ko], ['en', en]]) {
  const over = [];
  for (const d of defs) {
    const ref = String(d.message0 || '').match(/^%\{BKY_([A-Z0-9_]+)\}$/);
    if (!ref) continue;
    const text = msgs[ref[1]];
    if (text === undefined) { over.push(`${d.type}: ${ref[1]} 없음`); continue; }
    const n = (d.args0 || []).length;
    const hi = maxIndex(text);
    if (hi > n) over.push(`${d.type}: %${hi} > 인자 ${n}개 (${ref[1]})`);
  }
  check(`${langName}: 메시지의 %N 이 인자 수를 안 넘음`, over.length === 0, over.join(' | '));
}

console.log(failed === 0 ? '\n전부 통과' : `\n${failed}개 실패`);
process.exit(failed === 0 ? 0 : 1);
