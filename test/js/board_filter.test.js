/*
 * 실제 툴박스 정의를 두 보드 프로파일로 걸러 본다.
 *
 *   node test/js/board_filter.test.js
 *
 * 확인하는 것
 *   - 파이보에서 device_pibrain_* / 파이브레인에서 device_eye_* 가 사라지는지
 *   - 파이브레인에서 모션 카테고리가 통째로 사라지는지
 *   - 두 보드 어디에서도 안 보이는 블록이 없는지 (합집합 = 전체)
 *   - "requires" 키가 Blockly 로 새어 나가지 않는지
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '../..');
const STATIC = path.join(ROOT, 'ide/static');
const PROFILES = path.join(ROOT, 'openpibo/profiles');

/** toml 의 [features] 절만 읽는다. 시험에 필요한 건 그것뿐이다. */
function readFeatures(board) {
  const src = fs.readFileSync(path.join(PROFILES, `${board}.toml`), 'utf8');
  const section = src.split(/^\[features\]$/m)[1].split(/^\[/m)[0];
  const out = {};
  for (const line of section.split('\n')) {
    const m = line.match(/^\s*([a-z0-9_]+)\s*=\s*(true|false|"[^"]*")/);
    if (m) out[m[1]] = m[2] === 'true' ? true : m[2] === 'false' ? false : m[2].slice(1, -1);
  }
  return out;
}

function buildToolbox(board) {
  const sandbox = {
    console,
    window: { __BOARD__: { name: board, features: readFeatures(board) } },
    translations: new Proxy({}, { get: (_, k) => ({ ko: String(k), en: String(k) }) }),
    color_type: new Proxy({}, { get: (_, k) => '#000000' }),
  };
  sandbox.window.console = console;
  vm.createContext(sandbox);
  for (const f of ['board_filter.js', 'customblock_toolbox.js']) {
    vm.runInContext(fs.readFileSync(path.join(STATIC, f), 'utf8'), sandbox, { filename: f });
  }
  // 스크립트 최상위의 const/let 은 sandbox 프로퍼티가 되지 않는다.
  // 같은 컨텍스트에서 식을 한 번 더 평가해 꺼낸다.
  return vm.runInContext('toolbox_dict', sandbox).ko;
}

function collect(node, types = new Set(), cats = new Set()) {
  if (Array.isArray(node)) { node.forEach((n) => collect(n, types, cats)); return { types, cats }; }
  if (!node || typeof node !== 'object') return { types, cats };
  if (node.kind === 'block' && node.type) types.add(node.type);
  if (node.kind === 'category' && node.name) cats.add(node.name);
  if (node.contents) collect(node.contents, types, cats);
  return { types, cats };
}

function hasRequiresKey(node) {
  if (Array.isArray(node)) return node.some(hasRequiresKey);
  if (!node || typeof node !== 'object') return false;
  if ('requires' in node) return true;
  return Object.values(node).some(hasRequiresKey);
}

let failed = 0;
function check(label, ok, detail) {
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${label}${detail ? ' — ' + detail : ''}`);
  if (!ok) failed++;
}

const pibo = collect(buildToolbox('pibo'));
const pibrain = collect(buildToolbox('pibrain'));

console.log(`파이보    : 블록 ${pibo.types.size}개 / 카테고리 ${pibo.cats.size}개`);
console.log(`파이브레인: 블록 ${pibrain.types.size}개 / 카테고리 ${pibrain.cats.size}개\n`);

const PIBO_ONLY = ['device_eye_on', 'device_eye_colour_on', 'device_get_battery',
                   'device_get_pir', 'device_get_touch', 'motion_set_motor', 'audio_record'];
const PIBRAIN_ONLY = ['device_pibrain_button', 'device_pibrain_led_on',
                      'device_pibrain_led_off', 'device_pibrain_uart_init'];

for (const t of PIBO_ONLY) {
  check(`${t}: 파이보에 보임`, pibo.types.has(t));
  check(`${t}: 파이브레인에서 감춰짐`, !pibrain.types.has(t));
}
for (const t of PIBRAIN_ONLY) {
  check(`${t}: 파이브레인에 보임`, pibrain.types.has(t));
  check(`${t}: 파이보에서 감춰짐`, !pibo.types.has(t));
}

check('모션 카테고리: 파이보에 있음', pibo.cats.has('motion'));
check('모션 카테고리: 파이브레인에서 통째로 사라짐', !pibrain.cats.has('motion'));

const orphan = [...PIBO_ONLY, ...PIBRAIN_ONLY].filter(
  (t) => !pibo.types.has(t) && !pibrain.types.has(t));
check('어느 보드에서도 안 보이는 블록 없음', orphan.length === 0, orphan.join(', '));

check('requires 키가 Blockly 로 새어 나가지 않음',
      !hasRequiresKey(buildToolbox('pibo')) && !hasRequiresKey(buildToolbox('pibrain')));

// Blockly 의 동적 카테고리는 contents 가 [] 이고 실행 중에 채워진다.
// "비었으니 지운다"에 같이 쓸려 나가면 두 보드 다 변수·함수 서랍이 사라진다.
// 눈으로는 "원래 없었나?" 싶어 놓치기 쉬운 종류라 시험으로 못박는다.
for (const board of ['pibo', 'pibrain']) {
  check(`${board}: 변수 카테고리 살아 있음`, collect(buildToolbox(board)).cats.has('variables'));
  check(`${board}: 함수 카테고리 살아 있음`, collect(buildToolbox(board)).cats.has('functions'));
}

// 걸러진 툴박스가 원본 두 레포와 **블록 단위로** 같은지.
// 통합하면서 한쪽에만 있던 블록을 흘리지 않았는지 보는 것이 이 시험의 요점이다.
const UPSTREAM = {
  pibo:    '/home/user/themakerrobot/openpibo-os.pibo/ide/static',
  pibrain: '/home/user/themakerrobot/openpibo-os.pibrain/ide/static',
};
for (const [board, dir] of Object.entries(UPSTREAM)) {
  if (!fs.existsSync(path.join(dir, 'customblock_toolbox.js'))) {
    console.log(`  건너뜀  ${board} 원본 대조 — ${dir} 가 없습니다`);
    continue;
  }
  const sandbox = {
    console,
    window: { __BOARD__: null },
    translations: new Proxy({}, { get: (_, k) => ({ ko: String(k), en: String(k) }) }),
    color_type: new Proxy({}, { get: () => '#000000' }),
  };
  sandbox.window.console = console;
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(dir, 'customblock_toolbox.js'), 'utf8'),
                  sandbox, { filename: `${board}/customblock_toolbox.js` });
  const up = collect(vm.runInContext('toolbox_dict', sandbox).ko);
  const ours = collect(buildToolbox(board));
  // 원본과 일부러 다르게 한 것. 이유를 적어 두지 않으면 다음 사람이
  // "빠뜨렸나?" 하고 되돌린다.
  const DELIBERATE = {
    // OledByPiBrain 에 invert() 메서드가 없다. 원본 파이브레인 툴박스에는
    // 이 블록이 들어 있는데, 끌어다 실행하면 AttributeError 로 죽는다.
    // 있지도 않은 기능을 서랍에 두는 것보다 감추는 편이 낫다.
    pibrain: ['oled_invert'],
    pibo: [],
  };
  const lost = [...up.types].filter(
    (t) => !ours.types.has(t) && !(DELIBERATE[board] || []).includes(t));
  const extra = [...ours.types].filter((t) => !up.types.has(t));
  check(`${board}: 원본 툴박스에 있던 블록을 안 잃음 (의도한 것 제외)`,
        lost.length === 0, lost.join(', '));
  check(`${board}: 원본에 없던 블록이 안 생김`, extra.length === 0, extra.join(', '));
}

console.log(failed === 0 ? '\n전부 통과' : `\n${failed}개 실패`);
process.exit(failed === 0 ? 0 : 1);
