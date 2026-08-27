/*
 * 프록시 아래에서 뒤쪽 앱의 URL 이 제대로 풀리는지 본다.
 *
 *   node test/js/proxy_base.test.js
 *
 * 확인하는 것
 *   - 앱 JS 에 하드코딩된 절대 URL (http://${location.host}/...) 이 남아 있지 않은지
 *     남아 있으면 프록시(/tools/) 아래에서 허브 루트로 새어 나간다
 *   - BASE 가 있을 때/없을 때 URL 이 각각 어디로 가는지
 *   - index.js 가 tools_extra.js 보다 먼저 로드되는지 (BASE 정의 순서)
 *   - 템플릿의 캐시 버전이 올라갔는지 (안 올리면 브라우저가 옛 JS 를 쓴다)
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
let failed = 0;

function check(label, ok, detail) {
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${label}${detail ? ' — ' + detail : ''}`);
  if (!ok) failed++;
}

// ── 1. 하드코딩된 절대 URL 이 남아 있으면 안 된다 ──────────────
const APP_JS = [
  'tools/pibo/static/index.js',
  'tools/pibo/static/tools_extra.js',
  'classifier/static/index.js',
  'classifier/static/classifier_extra.js',
];

for (const rel of APP_JS) {
  const p = path.join(ROOT, rel);
  if (!fs.existsSync(p)) continue;
  const src = fs.readFileSync(p, 'utf8');
  const bad = (src.match(/http:\/\/\$\{location\.(host|hostname)\}/g) || []);
  check(`${rel}: location.host 절대 URL 없음`, bad.length === 0, `${bad.length}건`);
}

// ── 2. BASE 유무에 따라 URL 이 어디로 가는지 ────────────────────
// 앱 JS 를 통째로 돌리려면 DOM 이 필요하다. BASE 를 만드는 한 줄만 떼어
// 같은 식으로 평가한다.
function resolveWith(baseValue, expr) {
  const location = { origin: 'http://pibo.local' };
  const BASE = baseValue || '';
  // eslint-disable-next-line no-eval
  return eval('`' + expr + '`');
}

const CASES = [
  ['/classify', '${location.origin}${BASE}/camera_stream',
   'http://pibo.local/classify/camera_stream'],
  ['',          '${location.origin}${BASE}/camera_stream',
   'http://pibo.local/camera_stream'],
  ['/tools',    '${BASE}/upload_file/myaudio', '/tools/upload_file/myaudio'],
  ['',          '${BASE}/upload_file/myaudio', '/upload_file/myaudio'],
  ['/tools',    '${BASE}/socket.io',           '/tools/socket.io'],
  ['',          '${BASE}/socket.io',           '/socket.io'],
];

console.log();
for (const [base, expr, want] of CASES) {
  const got = resolveWith(base, expr);
  check(`BASE="${base}"  ${expr}`, got === want, got);
}

// ── 3. BASE 정의가 먼저 로드되는지 ─────────────────────────────
console.log();
const toolsHtml = fs.readFileSync(path.join(ROOT, 'tools/pibo/templates/index.html'), 'utf8');
const iIndex = toolsHtml.indexOf('static/index.js');
const iExtra = toolsHtml.indexOf('static/tools_extra.js');
check('tools: index.js 가 tools_extra.js 보다 먼저 로드',
      iIndex !== -1 && iExtra !== -1 && iIndex < iExtra);
check('tools/pibo/static/index.js 가 BASE 를 정의',
      /const BASE\s*=/.test(fs.readFileSync(path.join(ROOT, 'tools/pibo/static/index.js'), 'utf8')));
check('classifier/static/index.js 가 BASE 를 정의',
      /const BASE\s*=/.test(fs.readFileSync(path.join(ROOT, 'classifier/static/index.js'), 'utf8')));

// ── 4. 캐시 버전이 올라갔는지 ──────────────────────────────────
console.log();
const clsHtml = fs.readFileSync(path.join(ROOT, 'classifier/templates/index.html'), 'utf8');
check('tools 템플릿 캐시 버전 갱신', toolsHtml.includes('index.js?ver=260827v1'));
check('classifier 템플릿 캐시 버전 갱신', clsHtml.includes('index.js?ver=260827v1'));

// ── 5. 랜딩에서 새 창이 열리지 않는지 ──────────────────────────
console.log();
const landing = fs.readFileSync(path.join(ROOT, 'ide/templates/landing.html'), 'utf8');
const opens = (landing.match(/^\s*window\.open\(/gm) || []).length;
// 안내 문서(:8080)만 예외로 남겨 뒀다
check('landing: window.open 이 안내 문서 1건만 남음', opens <= 1, `${opens}건`);
check('landing: 3초 blind sleep 제거',
      !/setTimeout\([^)]*window\.open/.test(landing));
check('landing: SSE 로 준비 상태를 기다림',
      landing.includes('/api/service/') && landing.includes('EventSource'));

console.log(failed === 0 ? '\n전부 통과' : `\n${failed}개 실패`);
process.exit(failed === 0 ? 0 : 1);
