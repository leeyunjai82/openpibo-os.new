/*
 * 보드에 없는 블록을 툴박스에서 걷어낸다.
 *
 * 지금까지는 이 일을 "다른 보드 쪽을 주석 처리"로 했다. 그래서 파이보 레포와
 * 파이브레인 레포에 같은 파일이 서로 반대로 주석 처리된 채로 두 벌 있었고,
 * 블록 하나 고치려면 두 번 고쳐야 했다.
 *
 * 이제 툴박스에는 두 보드의 블록이 전부 들어 있고, 각 항목에 어떤 기능이
 * 있어야 보이는지 "requires" 로 적어 둔다. 실제로 보일지는 여기서 정한다.
 *
 *   { "kind": "block", "type": "device_eye_on", "requires": "has_mcu" }
 *
 * 기능 플래그의 출처는 openpibo/profiles/<board>.toml 의 [features] 이고,
 * run_ide.py 가 window.__BOARD__ 로 심어 준다.
 *
 * 블록 정의(customblock.js)와 코드 생성기(customblock_callback.js)는 걷어내지
 * 않는다. 이미 저장된 프로젝트에 그 블록이 들어 있으면 열리기는 해야 하고,
 * 안 그러면 "알 수 없는 블록"이 되어 파일이 깨져 보인다.
 * 툴박스에서만 안 보이게 한다.
 */

const BOARD = (typeof window !== 'undefined' && window.__BOARD__) || null;

// __BOARD__ 가 없으면(옛 캐시, 프록시, 직접 연 정적 파일) 아무것도 걷어내지 않는다.
// 잘못 걸러서 블록이 통째로 사라지는 것보다 다 보이는 편이 낫다.
const BOARD_FEATURES = (BOARD && BOARD.features) || null;

function boardHas(flag) {
  if (!BOARD_FEATURES) return true;
  if (!(flag in BOARD_FEATURES)) {
    console.warn(`[board_filter] "${flag}" 플래그가 ${BOARD.name} 프로파일에 없습니다. 일단 보여줍니다.`);
    return true;
  }
  return !!BOARD_FEATURES[flag];
}

/** requires 를 만족하지 못하는 항목을 재귀로 걷어낸다. requires 키 자체도 지운다. */
function filterToolbox(node) {
  if (Array.isArray(node)) {
    return node
      .filter((item) => !(item && item.requires) || boardHas(item.requires))
      .map(filterToolbox);
  }

  if (node === null || typeof node !== 'object') return node;

  const out = {};
  for (const key of Object.keys(node)) {
    if (key === 'requires') continue;       // Blockly 가 모르는 키다. 넘기지 않는다.
    out[key] = filterToolbox(node[key]);
  }

  // 안에 있는 블록이 **걸러져서** 비게 된 카테고리는 빈 채로 남기지 않는다.
  //
  // 원래부터 비어 있던 것은 건드리지 않는다. Blockly 의 동적 카테고리
  // (변수 "custom": "VARIABLE", 함수 "PROCEDURE")가 정확히 그렇다 —
  // contents 가 [] 이고 Blockly 가 실행 중에 채운다. 이걸 같이 지우면
  // 두 보드 다 변수·함수 서랍이 통째로 없어진다.
  if (out.kind === 'category' &&
      Array.isArray(out.contents) && out.contents.length === 0 &&
      Array.isArray(node.contents) && node.contents.length > 0) {
    return null;
  }
  return out;
}

/** 최상위에서 한 번 부른다. null 로 표시된 빈 카테고리까지 정리한다. */
function applyBoardFilter(toolboxJson) {
  const filtered = filterToolbox(toolboxJson);
  if (filtered && Array.isArray(filtered.contents)) {
    filtered.contents = filtered.contents.filter((c) => c !== null);
  }
  return filtered;
}

if (typeof window !== 'undefined') {
  window.applyBoardFilter = applyBoardFilter;
  window.boardHas = boardHas;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { applyBoardFilter, filterToolbox };   // 시험용
}
