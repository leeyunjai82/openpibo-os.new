/* ── 경로 앞가지 (셸 프록시) ──────────────────────────────────
   이 앱은 포트로 바로 열리기도 하고(:50000), 셸 프록시 뒤에서
   /tools/ 아래로 열리기도 한다. 코드 곳곳이 '/led', '/camera'
   같은 절대 경로를 쓰는데 프록시 뒤에서는 '/tools/led' 여야 한다.
   프록시가 <head> 에 넣어 주는 window.__BASE__ 를 앞에 붙인다.
   호출부 20 군데를 각각 고치는 대신 fetch/EventSource 를 한 겹 감싼다.
   같은 출처의 절대 경로만 건드린다 ('//' 로 시작하는 것과 http(s):// 는 그대로).
──────────────────────────────────────────────────────────── */
const __BASE = (window.__BASE__ || '').replace(/\/$/, '');
function __u(u) {
  if (typeof u !== 'string') return u;
  if (!__BASE) return u;
  if (u[0] !== '/' || u[1] === '/') return u;
  return __BASE + u;
}
if (__BASE) {
  const _fetch = window.fetch.bind(window);
  window.fetch = (u, opt) => _fetch(__u(u), opt);
  const _ES = window.EventSource;
  window.EventSource = function (u, opt) { return new _ES(__u(u), opt); };
  window.EventSource.prototype = _ES.prototype;
}

/* ── Language ────────────────────────────────────────────────
   Depends on tools_ko2en.js (T, t(), lang) loaded first.
──────────────────────────────────────────────────────────── */

function applyLang() {
  /* Static text nodes with data-key */
  document.querySelectorAll('[data-key]').forEach(el => {
    const key = el.getAttribute('data-key');
    const entry = T[key];
    if (!entry) return;
    const raw = entry[lang] !== undefined ? entry[lang] : entry.ko;
    if (typeof raw !== 'string') return;        // skip function-type entries

    if (el.hasAttribute('data-html')) {
      el.innerHTML = raw;                       // for entries with <br> etc.
    } else if ((el.tagName === 'INPUT') && el.type !== 'button' && el.type !== 'submit') {
      el.placeholder = raw;
    } else if (el.tagName === 'TEXTAREA') {
      el.placeholder = raw;
    } else {
      el.textContent = raw;
    }
  });

  /* Toggle button label */
  const btn = document.getElementById('lang-toggle');
  if (btn) btn.textContent = lang === 'ko' ? 'EN' : 'KO';

  /* Dynamic UI strings that were already written to the DOM */
  if (!camOn) {
    document.getElementById('cam-ph').textContent  = t('cam_off_msg');
    document.getElementById('btn-cam').textContent = t('cam_on_btn');
  } else {
    document.getElementById('cam-ph').textContent  = t('cam_streaming');
    document.getElementById('btn-cam').textContent = t('cam_off_btn');
  }

  /* Result / status placeholders — only reset if still showing placeholder */
  const vr = document.getElementById('vision-result');
  const isPlaceholder = (el, keys) => keys.some(k => el.textContent === (T[k].ko || '') || el.textContent === (T[k].en || ''));
  if (isPlaceholder(vr, ['result_ph', 'no_result'])) vr.textContent = t('result_ph');

  const ts = document.getElementById('tts-status');
  if (isPlaceholder(ts, ['waiting'])) ts.textContent = t('waiting');

  const ls = document.getElementById('lcd-status');
  if (isPlaceholder(ls, ['waiting'])) ls.textContent = t('waiting');

  const ors = document.getElementById('oled-reset-status');
  if (isPlaceholder(ors, ['waiting'])) ors.textContent = t('waiting');
}

function toggleLang() {
  lang = lang === 'ko' ? 'en' : 'ko';
  localStorage.setItem('tools_language', lang);
  applyLang();
}

/* ── Tab switching ───────────────────────────────────────────*/
let btnSrc = null;

function switchTab(name, btn) {
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
  if (name === 'buttons' && !btnSrc) startButtonStream();
  if (name === 'camera') resetVision();
  if (name === 'lcd') updateLcdPreview();
}

/* ── Button SSE ──────────────────────────────────────────────*/
function startButtonStream() {
  btnSrc = new EventSource('/button_stream');
  btnSrc.onmessage = e => {
    const state = JSON.parse(e.data);
    for (const [k, v] of Object.entries(state)) {
      const el = document.getElementById('bi-' + k);
      const on = v === 'on';
      el.classList.toggle('on', on);
      el.querySelector('.lbl').textContent = on ? 'ON' : 'OFF';
      if (on) {
        const time = new Date().toLocaleTimeString();
        const log = document.getElementById('btn-log');
        log.innerHTML =
          `<span style="color:#f9c300">${time}</span> ${t('btn_pressed', k)}<br>` +
          log.innerHTML;
      }
    }
  };
}
startButtonStream();

/* ── LED ─────────────────────────────────────────────────────*/
let R = 0, G = 0, B = 0;

function syncLed(ch, val) {
  val = Math.max(0, Math.min(255, parseInt(val) || 0));
  if (ch === 'r') R = val; else if (ch === 'g') G = val; else B = val;
  document.getElementById(`${ch}-range`).value = val;
  document.getElementById(`${ch}-num`).value   = val;
  const el = document.getElementById('led-preview');
  el.style.background  = `rgb(${R},${G},${B})`;
  el.style.boxShadow   = R + G + B > 0 ? `0 0 24px rgba(${R},${G},${B},0.5)` : 'none';
  document.getElementById('led-picker').value  =
    '#' + [R, G, B].map(v => v.toString(16).padStart(2, '0')).join('');
}

function applyColorPicker(hex) {
  syncLed('r', parseInt(hex.slice(1, 3), 16));
  syncLed('g', parseInt(hex.slice(3, 5), 16));
  syncLed('b', parseInt(hex.slice(5, 7), 16));
}

function applyLed() { fetch(`/led?r=${R}&g=${G}&b=${B}`); }
function ledOff()   { syncLed('r', 0); syncLed('g', 0); syncLed('b', 0); fetch('/led_off'); }
function setPreset(r, g, b) { syncLed('r', r); syncLed('g', g); syncLed('b', b); applyLed(); }

/* ── Camera ──────────────────────────────────────────────────*/
let camOn = false, resultInterval = null;

function toggleCamera() {
  if (camOn) {
    fetch('/camera?d=off');
    camOn = false;
    clearInterval(resultInterval);
    document.getElementById('btn-cam').textContent    = t('cam_on_btn');
    document.getElementById('btn-capture').disabled  = true;
    document.getElementById('cam-ph').textContent    = t('cam_off_msg');
    document.getElementById('cam-wrap').style.display = 'none';
  } else {
    fetch('/camera?d=on');
    camOn = true;
    document.getElementById('btn-cam').textContent   = t('cam_off_btn');
    document.getElementById('btn-capture').disabled  = false;
    document.getElementById('cam-ph').textContent    = t('cam_streaming');
  }
}

async function captureToWeb() {
  const res = await fetch('/capture_frame').then(r => r.json());
  if (res.frame) {
    document.getElementById('cam-img').src             = 'data:image/jpeg;base64,' + res.frame;
    document.getElementById('cam-wrap').style.display  = 'block';
  }
}

/* ── Vision ──────────────────────────────────────────────────*/
let currentVision = 'camera';

function resetVision() {
  currentVision = 'camera';
  fetch('/vision_type?t=camera');
  document.querySelectorAll('.vbtn').forEach(b => b.classList.remove('active'));
  document.querySelector('.vbtn').classList.add('active');
  clearInterval(resultInterval);
  document.getElementById('vision-result').textContent = t('result_ph');
  document.getElementById('marker-row').style.display  = 'none';
}

function setVision(type, btn) {
  currentVision = type;
  document.querySelectorAll('.vbtn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const ml = document.getElementById('marker-len').value || 5;
  document.getElementById('marker-row').style.display = type === 'marker' ? 'flex' : 'none';
  fetch(`/vision_type?t=${type}&ml=${ml}`);
  clearInterval(resultInterval);
  const noResult = ['camera','grayscale','canny','edgePreservingFilter','cartoon','sketch_rgb','detail','pose'];
  if (!noResult.includes(type)) {
    resultInterval = setInterval(() => {
      fetch('/vision_result').then(r => r.json()).then(d => {
        document.getElementById('vision-result').textContent = d.result || t('no_result');
      });
    }, 500);
  } else {
    document.getElementById('vision-result').textContent = t('result_ph');
  }
}

function updateMarkerLen() {
  fetch(`/vision_type?t=marker&ml=${document.getElementById('marker-len').value}`);
}

/* ── TTS ─────────────────────────────────────────────────────*/
let selectedVoice = 'f1';

function setVoice(v, btn) {
  selectedVoice = v;
  document.querySelectorAll('.voice-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

async function speakTTS() {
  const text = document.getElementById('tts-text').value.trim();
  if (!text) return;
  const ttsBtn = document.getElementById('tts-btn');
  ttsBtn.disabled = true;
  document.getElementById('tts-status').textContent = t('tts_speaking');
  const res = await fetch(`/tts?text=${encodeURIComponent(text)}&voice=${selectedVoice}`).then(r => r.json());
  document.getElementById('tts-status').textContent =
    res.ok ? t('tts_done') : `${t('error_prefix')}${res.error || ''}`;
  ttsBtn.disabled = false;
}

function stopTTS() {
  fetch('/tts_stop');
  document.getElementById('tts-status').textContent = t('tts_stopped');
}

/* ── LCD ─────────────────────────────────────────────────────*/
function hexToRgb(hex) {
  return {
    r: parseInt(hex.slice(1, 3), 16),
    g: parseInt(hex.slice(3, 5), 16),
    b: parseInt(hex.slice(5, 7), 16)
  };
}

function updateLcdPreview() {
  const canvas = document.getElementById('lcd-canvas');
  const ctx    = canvas.getContext('2d');
  const text   = document.getElementById('lcd-text').value;
  const size   = parseInt(document.getElementById('lcd-size').value) || 24;
  const x      = parseInt(document.getElementById('lcd-x').value)    || 0;
  const y      = parseInt(document.getElementById('lcd-y').value)    || 0;
  const fg     = document.getElementById('lcd-fg').value;
  const bg     = document.getElementById('lcd-bg').value;

  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, 240, 320);
  ctx.fillStyle    = fg;
  ctx.font         = `${size}px "Noto Sans KR", sans-serif`;
  ctx.textBaseline = 'top';

  text.split(/\\n|\n/).forEach((line, i) => {
    ctx.fillText(line, x, y + i * (size + 4));
  });
}

async function sendLcdText() {
  const text = document.getElementById('lcd-text').value;
  const size = parseInt(document.getElementById('lcd-size').value) || 24;
  const x    = parseInt(document.getElementById('lcd-x').value)    || 0;
  const y    = parseInt(document.getElementById('lcd-y').value)    || 0;
  const fg   = hexToRgb(document.getElementById('lcd-fg').value);
  const bg   = hexToRgb(document.getElementById('lcd-bg').value);

  document.getElementById('lcd-status').textContent = t('lcd_sending');

  const encodedText = encodeURIComponent(text.replace(/\\n/g, '\n'));
  const url =
    `/oled_text?text=${encodedText}&x=${x}&y=${y}&size=${size}` +
    `&r=${fg.r}&g=${fg.g}&b=${fg.b}&bg_r=${bg.r}&bg_g=${bg.g}&bg_b=${bg.b}`;

  const res = await fetch(url).then(r => r.json());
  document.getElementById('lcd-status').textContent =
    res.ok ? t('lcd_done') : `${t('error_prefix')}${res.error || ''}`;
}

async function clearLcd() {
  const bg = hexToRgb(document.getElementById('lcd-bg').value);
  document.getElementById('lcd-status').textContent = t('lcd_clearing');
  const res = await fetch(`/oled_clear?bg_r=${bg.r}&bg_g=${bg.g}&bg_b=${bg.b}`).then(r => r.json());
  document.getElementById('lcd-status').textContent =
    res.ok ? t('lcd_cleared') : `${t('error_prefix')}${res.error || ''}`;
  updateLcdPreview();
}

async function resetOled() {
  document.getElementById('oled-reset-status').textContent = t('lcd_resetting');
  const res = await fetch('/oled_reset').then(r => r.json());
  document.getElementById('oled-reset-status').textContent =
    res.ok ? t('lcd_reset_done') : `${t('error_prefix')}${res.error || ''}`;
}

/* ── Cleanup on leave ────────────────────────────────────────*/
window.addEventListener('beforeunload', () => {
  fetch('/camera?d=off', { keepalive: true });
  fetch('/led_off',      { keepalive: true });
  /* 예전에는 여기서 허브의 /tools?enable=off 를 불러 tools 서비스를 껐다.
     지금은 셸이 서비스 수명을 쥐고 있다(/api/service/tools/stop).
     앱이 자기를 끄겠다고 나서면 셸과 싸우게 되므로 뺐다.
     위 두 줄(카메라/LED 끄기)은 이 앱이 잡은 자원이라 그대로 둔다. */
});

/* ── Init ────────────────────────────────────────────────────*/
document.addEventListener('DOMContentLoaded', () => {
  applyLang();
  updateLcdPreview();
});