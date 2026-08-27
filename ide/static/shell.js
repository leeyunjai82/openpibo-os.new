/*
 * SPA shell — 탭 라우팅, 서비스 전환, 설정 모달, 상태 배지
 *
 * 프레임워크를 쓰지 않는다. 탭 셸 하나에 React/Preact 를 얹을 이유가 없고,
 * 교실 파이는 인터넷이 없을 수 있어 CDN 도 못 쓴다.
 * (docs/plan/00-decisions.md 5.3 — 번들 크기가 SD 카드 I/O 에 직결된다)
 *
 * 각 탭은 iframe 이다. 1단계에서 뒤쪽 서비스가 전부 같은 origin 으로 들어와서
 * 가능해진 구조다. 셸은 상단바·전환·설정만 맡고, 앱 자체는 손대지 않는다.
 */

'use strict';

const BOARD = window.__BOARD__ || { name: 'pibo', label: '파이보', features: {} };

/*
 * 탭 정의.
 *
 * service: 이 탭을 열려면 켜야 하는 뒤쪽 서비스. 셋은 서로 배타다 —
 *          2GB 라 동시에 못 뜬다 (00-decisions.md 4.3).
 * keep:    탭을 떠날 때 iframe 을 살려 둘지.
 *          IDE 는 살린다 — 편집 중이던 코드가 날아가면 안 된다.
 *          나머지는 버린다 — 어차피 서비스가 꺼져서 죽은 화면이 된다.
 */
/*
 * 아이콘·이름·설명은 landing.html 의 카드와 **같은 것**을 쓴다.
 * 아이콘은 Font Awesome (all.min.css + webfonts 가 레포에 들어 있다 — CDN 아님).
 */
const TABS = [
  { id: 'home',  name: '홈',    tab: '홈',   icon: 'fa-house', kind: 'home' },
  { id: 'play',  name: 'Tools', tab: '체험', icon: 'fa-screwdriver-wrench',
    kind: 'frame', src: '/tools/',    service: 'tools',
    desc: '모션, 비전, 음성<br>센서 제어' },
  { id: 'code',  name: 'IDE',   tab: '코딩', icon: 'fa-code',
    kind: 'frame', src: '/ide',       keep: true,
    desc: '코드 작성 및<br>실행 환경' },
  { id: 'learn', name: 'Classifier', tab: '학습', icon: 'fa-images',
    kind: 'frame', src: '/classify/', service: 'classify',
    desc: '이미지 분류<br>학습 도구' },
  { id: 'chat',  name: 'Chat Bot',   tab: '대화', icon: 'fa-comment',
    kind: 'frame', src: '/llm/',      service: 'llm',
    desc: 'AI 챗봇<br>대화 인터페이스' },
];

const byId = (id) => document.getElementById(id);
const TAB = Object.fromEntries(TABS.map((t) => [t.id, t]));

let current = null;      // 지금 탭 id
let switching = null;    // 진행 중인 EventSource
let statusES = null;     // 상태 배지용 EventSource

/* ── 알림 ──────────────────────────────────────────────── */

let toastTimer = null;
function toast(msg, kind) {
  const el = byId('toast');
  el.textContent = msg;
  el.className = 'toast on ' + (kind || 'err');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = 'toast'; }, 6000);
}

/* ── 봉투 응답 ─────────────────────────────────────────── */

/*
 * 모든 /api 응답은 { type, result, data, elapsed_ms, device } 봉투다.
 * 실패는 예외로 올린다 — 호출한 쪽이 try/catch 하나로 처리하게.
 */
async function api(path, options) {
  const res = await fetch(path, options);
  let body;
  try {
    body = await res.json();
  } catch (_) {
    throw new Error(`서버가 이해할 수 없는 답을 보냈습니다 (HTTP ${res.status})`);
  }
  if (body && body.result === 'fail') {
    throw new Error((body.data && body.data.message) || '알 수 없는 오류');
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return body.data;
}

/* ── 라우팅 ────────────────────────────────────────────── */

/*
 * History API 를 쓴다. 주소가 /app/<탭> 으로 남아서 새로고침해도 그 탭이 열리고,
 * 뒤로가기가 탭 사이를 오간다. 이게 1·2단계의 핵심 목표다.
 */
function tabFromLocation() {
  const m = location.pathname.match(/^\/app\/([a-z]+)/);
  const id = m && m[1];
  return TAB[id] ? id : 'home';
}

function go(id, { push = true } = {}) {
  if (!TAB[id]) id = 'home';
  if (push && id !== tabFromLocation()) {
    history.pushState({ tab: id }, '', `/app/${id}`);
  }
  show(id);
}

window.addEventListener('popstate', () => show(tabFromLocation()));

/* ── 탭 표시 ───────────────────────────────────────────── */

function markTabs(id) {
  document.querySelectorAll('.tab').forEach((b) => {
    if (b.dataset.tab === id) b.setAttribute('aria-current', 'page');
    else b.removeAttribute('aria-current');
  });
}

function hideAllPanes() {
  byId('home_pane').style.display = 'none';
  document.querySelectorAll('.frame').forEach((f) => f.classList.remove('active'));
  byId('switching').classList.remove('on');
}

async function show(id) {
  const tab = TAB[id];
  if (!tab) return;

  // 떠나는 탭 정리: keep 이 아니면 iframe 을 버린다.
  // 서비스가 곧 꺼지므로 살려 둬 봐야 죽은 화면이다. 메모리도 아깝다.
  if (current && current !== id) {
    const prev = TAB[current];
    if (prev && prev.kind === 'frame' && !prev.keep) {
      const f = byId('frame_' + prev.id);
      if (f) f.remove();
    }
  }

  current = id;
  markTabs(id);
  hideAllPanes();
  // 이전 화면의 조작을 상단바에서 치운다.
  // 남겨 두면 다른 화면의 버튼을 누르게 된다.
  clearActions();

  if (tab.kind === 'home') {
    byId('home_pane').style.display = '';
    return;
  }

  // 서비스가 필요한 탭이면 먼저 켜고 준비될 때까지 기다린다
  if (tab.service) {
    const ready = await ensureService(tab);
    if (!ready) return;            // 실패 화면은 ensureService 가 그린다
    if (current !== id) return;    // 기다리는 사이 다른 탭으로 갔다
  }

  mountFrame(tab);
}

function mountFrame(tab) {
  let f = byId('frame_' + tab.id);
  // 살려 둔 iframe(코딩 탭)으로 돌아온 경우 — 조작을 다시 올린다.
  // embed.js 는 이미 들어가 있으므로 다시 알려 달라고만 한다.
  if (f && f.contentWindow) {
    injectEmbed(f);
    try {
      f.contentWindow.postMessage({ type: 'pibo:rescan' }, window.location.origin);
    } catch (_) { /* 아직 안 떴으면 load 때 주입된다 */ }
  }
  if (!f) {
    f = document.createElement('iframe');
    f.id = 'frame_' + tab.id;
    f.className = 'frame';
    f.title = tab.name;
    // 전체화면을 명시적으로 허용해 둔다.
    //
    // 지금은 없어도 된다 — 같은 origin 이라 브라우저가 기본으로 허용한다
    // (A/B 로 확인했다: allow 없이도 앱의 전체화면 버튼이 동작한다).
    // 명시하는 이유는 나중에 sandbox 를 걸거나 origin 이 갈릴 때
    // 조용히 죽는 것을 막기 위해서다. 아래 시험이 이걸 지킨다.
    f.setAttribute('allow', 'fullscreen');
    f.allowFullscreen = true;
    // 같은 origin 이라 sandbox 를 걸면 오히려 앱이 망가진다.
    // 1단계에서 origin 을 합쳤기 때문에 그냥 붙여도 된다.

    // 앱 헤더의 조작을 셸 상단바로 올린다.
    // 같은 origin 이라 iframe 안에 스크립트를 넣을 수 있다 —
    // 덕분에 앱 세 개를 각각 고칠 필요가 없다.
    f.addEventListener('load', () => injectEmbed(f));

    f.src = tab.src;
    byId('stage').appendChild(f);
  }
  f.classList.add('active');
}

/* ── 앱 조작을 상단바로 올리기 ─────────────────────────── */

/*
 * 셸 바 + 앱 헤더로 바가 두 겹이던 것을 하나로 만든다.
 * 앱 헤더는 CSS 로 감추고(html.embedded), 그 안의 조작만 여기로 올린다.
 */

let actionOwner = null;      // 지금 상단바에 올라와 있는 조작의 주인 탭

function injectEmbed(frame) {
  try {
    const d = frame.contentDocument;
    if (!d || d.getElementById('pibo_embed')) return;
    const s = d.createElement('script');
    s.id = 'pibo_embed';
    s.src = '/static/embed.js?ver=260827v1';
    d.head.appendChild(s);
  } catch (_) {
    // 접근이 막히면 앱이 자기 헤더를 그대로 쓴다. 기능은 잃지 않는다.
  }
}

function clearActions() {
  byId('app_actions').innerHTML = '';
  actionOwner = null;
}

function renderActions(actions, tabId) {
  const wrap = byId('app_actions');
  wrap.innerHTML = '';
  actionOwner = tabId;

  actions.forEach((a) => {
    let el;
    if (a.kind === 'select') {
      el = document.createElement('select');
      el.className = 'bar-select';
      (a.options || []).forEach((o) => {
        const opt = document.createElement('option');
        opt.value = o.value; opt.textContent = o.label;
        el.appendChild(opt);
      });
      if (a.value != null) el.value = a.value;
      el.onchange = () => sendAction(a.id, el.value);
    } else {
      el = document.createElement('button');
      el.type = 'button';
      el.className = 'icon-btn';
      if (a.icon) {
        el.innerHTML = `<i class="fa-solid ${a.icon}"></i>`;
      } else {
        el.textContent = a.text || '?';
        el.classList.add('icon-btn-text');
      }
      el.onclick = () => sendAction(a.id);
    }
    el.title = a.title || '';
    if (a.title) el.setAttribute('aria-label', a.title);
    wrap.appendChild(el);
  });
}

function sendAction(id, value) {
  const f = actionOwner && byId('frame_' + actionOwner);
  if (!f || !f.contentWindow) return;
  f.contentWindow.postMessage(
    { type: 'pibo:action', id, value }, window.location.origin);
}

window.addEventListener('message', (ev) => {
  if (ev.origin !== window.location.origin) return;
  if (!ev.data || ev.data.type !== 'pibo:actions') return;
  // 보낸 쪽이 지금 보고 있는 탭인지 확인한다.
  // 살려 둔 숨은 iframe(코딩 탭)이 상단바를 가로채면 안 된다.
  const cur = TAB[current];
  const f = cur && byId('frame_' + cur.id);
  if (!f || f.contentWindow !== ev.source) return;
  renderActions(ev.data.actions || [], cur.id);
});

/* ── 서비스 전환 ───────────────────────────────────────── */

const PHASE_LABEL = {
  starting: '서비스를 시작하는 중',
  active: '거의 다 됐어요',
  ready: '준비 끝',
};

function paintSteps(phase) {
  const order = ['starting', 'active', 'ready'];
  const at = order.indexOf(phase);
  document.querySelectorAll('#switch_steps span').forEach((el, i) => {
    el.className = i < at ? 'done' : (i === at ? 'now' : '');
  });
}

/*
 * 켜고, **실제로 응답할 때까지** 기다린다.
 *
 * systemctl is-active 는 uvicorn 이 포트를 잡기 전에 이미 active 를 준다.
 * 그래서 서버가 active 와 ready 를 나눠 보내고, 여기서는 ready 만 믿는다.
 * 몇 초 걸리든 그대로 보여준다 — 지연을 숨기지 않는다 (00-decisions.md 5.1).
 */
function ensureService(tab) {
  return new Promise((resolve) => {
    if (switching) { switching.close(); switching = null; }

    const box = byId('switching');
    box.classList.remove('failed');
    byId('switch_title').textContent = `${tab.tab} 준비 중`;
    byId('switch_detail').textContent = '';
    byId('switch_tech').style.display = 'none';
    byId('switch_retry').style.display = 'none';
    paintSteps('starting');
    box.classList.add('on');

    const fail = (msg, tech) => {
      if (switching) { switching.close(); switching = null; }
      // 도는 것을 멈춘다. 계속 돌면 "아직 하는 중"으로 읽힌다.
      box.classList.add('failed');
      document.querySelectorAll('#switch_steps span').forEach(
        (el) => { el.className = ''; });
      byId('switch_title').textContent = `${josa(tab.tab, '을', '를')} 열지 못했습니다`;
      byId('switch_detail').textContent = msg;
      // 개발자용 내용은 따로, 작게. 아이가 읽는 문장과 섞지 않는다.
      const t = byId('switch_tech');
      t.textContent = tech || '';
      t.style.display = tech ? '' : 'none';
      byId('switch_retry').style.display = '';
      byId('switch_retry').onclick = () => show(tab.id);
      resolve(false);
    };

    // api() 를 쓴다. 봉투의 result:'fail' 을 예외로 올려 주므로
    // 실패했는데 그냥 다음 단계로 넘어가는 일이 없다.
    api(`/api/service/${tab.service}/start`, { method: 'POST' })
      .then(() => {
        switching = new EventSource(`/api/service/${tab.service}/events`);

        switching.onmessage = (ev) => {
          let d;
          try { d = JSON.parse(ev.data); } catch (_) { return; }

          if (d.phase === 'ready') {
            switching.close(); switching = null;
            paintSteps('ready');
            box.classList.remove('on');
            resolve(true);
            return;
          }
          if (d.phase === 'failed' || d.phase === 'timeout') {
            fail(d.reason || '알 수 없는 이유로 시작하지 못했습니다.', d.detail);
            return;
          }
          paintSteps(d.phase);
          byId('switch_detail').innerHTML =
            `${PHASE_LABEL[d.phase] || '시작하는 중'} · ` +
            `<span class="elapsed">${d.elapsed}초</span>`;
        };

        switching.onerror = () => {
          if (!switching) return;
          fail('상태를 받지 못했습니다. 잠시 후 다시 시도하세요.');
        };
      })
      .catch((err) => fail('시작 요청을 보내지 못했습니다.', err.message));
  });
}

/* ── 상태 배지 ─────────────────────────────────────────── */

/* 자원을 누가 잡고 있는지 항상 드러낸다 (00-decisions.md 5.2) */
function paintBadges(s) {
  const set = (id, on, text) => {
    const el = byId(id);
    el.classList.toggle('on', !!on);
    if (text) el.querySelector('span').textContent = text;
  };
  const owner = s.camera_owner ? (TABS.find((t) => t.service === s.camera_owner) || {}).tab : null;
  set('badge_cam', !!s.camera_owner, owner ? `카메라 사용중 (${owner})` : '카메라 사용중');
  set('badge_run', s.code_running, '코드 실행중');
  set('badge_model', s.model_loading, '모델 로딩중');
}

function startStatusStream() {
  if (statusES) statusES.close();
  statusES = new EventSource('/api/system/events');
  statusES.onmessage = (ev) => {
    try { paintBadges(JSON.parse(ev.data)); } catch (_) { /* keep-alive */ }
  };
  statusES.onerror = () => {
    // 끊기면 배지를 지운다. 옛 상태를 계속 보여주면 거짓말이 된다.
    ['badge_cam', 'badge_run', 'badge_model']
      .forEach((id) => byId(id).classList.remove('on'));
  };
}

/* ── 설정 모달 ─────────────────────────────────────────── */

function openSettings(pane) {
  byId('modal_settings').classList.add('on');
  showSettingsPane(pane || 'info');
}
function closeSettings() {
  byId('modal_settings').classList.remove('on');
}
function showSettingsPane(id) {
  document.querySelectorAll('.settings-pane').forEach(
    (p) => p.classList.toggle('on', p.dataset.pane === id));
  document.querySelectorAll('.settings-tabs button').forEach(
    (b) => b.setAttribute('aria-current', String(b.dataset.pane === id)));
  if (id === 'info') loadInfo();
  if (id === 'wifi') loadWifi();
  if (id === 'log') loadLog();
}

async function loadInfo() {
  const dl = byId('info_kv');
  dl.innerHTML = '<div class="si-item"><dt>불러오는 중</dt><dd>…</dd></div>';
  try {
    const d = await api('/api/system/info');
    const rows = [
      ['보드', `${d.board_label} (${d.board})`],
      ['시리얼', d.serial],
      ['버전', d.os_version],
      ['IP', d.ip || '(연결 없음)'],
      ['와이파이', d.ssid || '(없음)'],
      ['온도', d.temp_c == null ? '-' : `${d.temp_c}°C`],
      ['메모리', d.mem_used_percent == null ? '-' : `${d.mem_used_percent}% 사용중`],
      ['가동시간', d.uptime_text || '-'],
    ];
    dl.innerHTML = rows
      .map(([k, v]) =>
        `<div class="si-item"><dt>${esc(k)}</dt>` +
        `<dd>${esc(String(v ?? '-'))}</dd></div>`)
      .join('');
  } catch (err) {
    dl.innerHTML = `<div class="si-item"><dt>오류</dt><dd>${esc(err.message)}</dd></div>`;
  }
}

async function loadWifi() {
  const sel = byId('wifi_ssid');
  sel.innerHTML = '<option>찾는 중…</option>';
  try {
    const cur = await api('/api/system/wifi').catch(() => null);
    if (cur && cur.ssid) byId('wifi_current').textContent = `현재: ${cur.ssid}`;

    const list = await api('/api/system/wifi/scan');
    const items = Array.isArray(list) ? list : (list && list.data) || [];
    sel.innerHTML = '';
    if (!items.length) {
      sel.innerHTML = '<option value="">(찾은 와이파이 없음)</option>';
      return;
    }
    items.forEach((n) => {
      const ssid = typeof n === 'string' ? n : (n.ssid || n.SSID || '');
      if (!ssid) return;
      const o = document.createElement('option');
      o.value = ssid;
      o.textContent = ssid + (n.signal ? `  (${n.signal})` : '');
      sel.appendChild(o);
    });
  } catch (err) {
    sel.innerHTML = `<option value="">${esc(err.message)}</option>`;
  }
}

async function saveWifi() {
  const btn = byId('wifi_save');
  const ssid = byId('wifi_ssid').value;
  const psk = byId('wifi_psk').value;
  const identity = byId('wifi_identity').value;

  if (!ssid) { toast('와이파이를 고르세요.'); return; }
  if (psk && psk.length < 8) { toast('비밀번호는 8자 이상이어야 합니다.'); return; }

  btn.disabled = true;
  try {
    await api('/api/system/wifi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ssid, psk, identity }),
    });
    toast('와이파이를 설정했습니다. 곧 다시 시작합니다.', 'ok');
  } catch (err) {
    // 접속 후 곧바로 재부팅하므로 응답을 못 받는 것이 정상일 수 있다
    toast(`설정 요청은 보냈지만 응답을 못 받았습니다: ${err.message}`);
  } finally {
    btn.disabled = false;
  }
}

async function loadLog() {
  const pre = byId('log_view');
  pre.textContent = '불러오는 중…';
  try {
    const d = await api('/api/system/log');
    pre.textContent = d.record || '(기록 없음)';
    pre.scrollTop = pre.scrollHeight;
  } catch (err) {
    pre.textContent = err.message;
  }
}

async function power(action) {
  const label = action === 'off' ? '전원을 끕' : '다시 시작합';
  if (!confirm(`정말 ${label}니까?`)) return;
  try {
    await api(`/api/system/power/${action}`, { method: 'POST' });
    toast(`${label}니다. 잠시 기다려 주세요.`, 'ok');
  } catch (err) {
    toast(err.message);
  }
}

/*
 * 한국어 조사. "학습 를 열지 못했습니다" 처럼 어긋나면 아이가 읽기에 어색하다.
 * 받침이 있으면 을/이/은, 없으면 를/가/는.
 */
function josa(word, withBatchim, without) {
  const last = String(word).charCodeAt(String(word).length - 1);
  const isHangul = last >= 0xac00 && last <= 0xd7a3;
  const hasBatchim = isHangul && (last - 0xac00) % 28 !== 0;
  return word + (hasBatchim ? withBatchim : without);
}

function esc(s) {
  return String(s).replace(/[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ── 시작 ──────────────────────────────────────────────── */

function buildTabs() {
  const top = byId('tabs');
  const bottom = byId('bottom_tabs');
  TABS.forEach((t) => {
    const a = document.createElement('button');
    a.className = 'tab'; a.dataset.tab = t.id; a.type = 'button';
    a.textContent = t.tab;
    a.onclick = () => go(t.id);
    top.appendChild(a);

    const b = document.createElement('button');
    b.className = 'tab'; b.dataset.tab = t.id; b.type = 'button';
    b.innerHTML = `<i class="ico fa-solid ${t.icon}"></i>${esc(t.tab)}`;
    b.onclick = () => go(t.id);
    bottom.appendChild(b);
  });
}

function buildHomeCards() {
  const wrap = byId('home_cards');
  TABS.filter((t) => t.id !== 'home').forEach((t) => {
    const b = document.createElement('button');
    b.className = 'card'; b.type = 'button'; b.dataset.tab = t.id;
    // desc 는 우리가 쓴 고정 문자열이라 <br> 을 그대로 둔다.
    // 사용자 입력이 아니므로 esc 대상이 아니다.
    b.innerHTML =
      `<span class="card-icon"><i class="fa-solid ${t.icon}"></i></span>` +
      `<span class="card-body">` +
        `<span class="name">${esc(t.name)}</span>` +
        `<span class="desc">${t.desc || ''}</span>` +
      `</span>` +
      `<span class="card-btn">열기 →</span>`;
    b.onclick = () => go(t.id);
    wrap.appendChild(b);
  });
}

function init() {
  byId('board_label').textContent = BOARD.label || BOARD.name;
  document.title = `${BOARD.label || '파이보'} — openpibo`;

  buildTabs();
  buildHomeCards();

  byId('brand').onclick = () => go('home');
  byId('btn_settings').onclick = () => openSettings('info');
  byId('modal_settings').onclick = (e) => {
    if (e.target === byId('modal_settings')) closeSettings();
  };
  byId('settings_close').onclick = closeSettings;
  document.querySelectorAll('.settings-tabs button').forEach(
    (b) => { b.onclick = () => showSettingsPane(b.dataset.pane); });
  byId('wifi_rescan').onclick = loadWifi;
  byId('wifi_save').onclick = saveWifi;
  byId('log_refresh').onclick = loadLog;
  byId('btn_power_off').onclick = () => power('off');
  byId('btn_power_restart').onclick = () => power('restart');

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeSettings();
  });

  startStatusStream();
  show(tabFromLocation());
}

document.addEventListener('DOMContentLoaded', init);
