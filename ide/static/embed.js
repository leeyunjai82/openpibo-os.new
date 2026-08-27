/*
 * 셸(iframe) 안에서 앱 헤더를 걷어내고, 그 안의 조작 버튼만 셸 상단바로 올린다.
 *
 * 왜 필요한가
 *   셸 금색 바 아래에 앱 헤더가 또 있어서 바가 두 겹이었다.
 *   앱 헤더를 그냥 없애면 메뉴·전체화면·볼륨 같은 조작을 잃는다.
 *   그래서 **감추되 조작만 위로 올린다.** 결과적으로 바는 하나다.
 *
 * 어떻게
 *   셸이 iframe 이 뜬 뒤 이 파일을 그 안에 넣는다 (같은 origin 이라 가능하다).
 *   앱은 아무것도 안 고쳐도 된다 — 여기서 알려진 선택자만 찾아 셸에 알린다.
 *
 *     iframe -> 셸 : { type:'pibo:actions', actions:[...] }
 *     셸 -> iframe : { type:'pibo:action', id, value }
 *
 *   셸은 원래 요소를 대신 눌러 준다. 앱의 동작 코드는 그대로 돌아간다.
 *
 * 포트로 직접 열면 이 파일이 아예 주입되지 않는다. 앱은 예전 그대로다.
 */

(function () {
  'use strict';

  if (window.self === window.top) return;          // 셸 안이 아니면 할 일 없음
  if (window.__PIBO_EMBED__) return;               // 두 번 주입 방지
  window.__PIBO_EMBED__ = true;

  /*
   * 어떤 조작을 올릴지. 앱마다 요소가 다르니 여기서만 안다.
   * 없는 선택자는 조용히 건너뛴다 — 앱마다 있는 것/없는 것이 다르다.
   *
   * order 는 셸 상단바에서의 순서다.
   */
  var CONTROLS = [
    { sel: '#sidebar_toggle_btn', icon: 'fa-bars',            title: '파일 목록' },
    { sel: '#restore_bt',         icon: 'fa-eraser',          title: '초기화' },
    { sel: '#volume',             icon: 'fa-volume-high',     title: '소리 크기', kind: 'select' },
    { sel: '#lang-toggle',        icon: null, text: 'EN',     title: '언어' },
    { sel: '#fullscreen_bt',      icon: 'fa-expand',          title: '전체화면' },
  ];

  var found = [];

  CONTROLS.forEach(function (c, i) {
    var el = document.querySelector(c.sel);
    if (!el) return;

    var item = {
      id: 'c' + i,
      icon: c.icon,
      text: c.text || null,
      title: c.title,
      kind: c.kind || 'button',
    };

    if (item.kind === 'select') {
      item.options = Array.prototype.map.call(el.options, function (o) {
        return { value: o.value, label: o.textContent };
      });
      item.value = el.value;
    }

    found.push(item);
    item._el = el;
  });

  // 셸이 대신 눌러 달라고 보내오면 원래 요소를 조작한다.
  window.addEventListener('message', function (ev) {
    if (!ev.data) return;
    // 살려 둔 iframe 으로 돌아오면 셸이 조작 목록을 다시 물어본다.
    if (ev.data.type === 'pibo:rescan') { announce(); return; }
    if (ev.data.type !== 'pibo:action') return;
    var item = found.filter(function (f) { return f.id === ev.data.id; })[0];
    if (!item || !item._el) return;

    if (item.kind === 'select') {
      item._el.value = ev.data.value;
      item._el.dispatchEvent(new Event('change', { bubbles: true }));
    } else {
      item._el.click();
    }
  });

  function announce() {
    if (!found.length) return;
    window.parent.postMessage({
      type: 'pibo:actions',
      actions: found.map(function (f) {
        return { id: f.id, icon: f.icon, text: f.text, title: f.title,
                 kind: f.kind, options: f.options, value: f.value };
      }),
    }, window.location.origin);
  }

  announce();
  // 앱이 늦게 초기화하며 값을 바꾸는 경우가 있어 한 번 더 알린다.
  setTimeout(announce, 800);
})();
