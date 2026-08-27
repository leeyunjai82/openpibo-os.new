#!/bin/bash
# 하드웨어 없이 도는 시험 전부.
#
#   bash test/run.sh
#
# 기기에서만 확인할 수 있는 것(부팅 화면, LED, 카메라)은 여기 없다.
# README.md 의 "기기에서 확인하는 순서" 를 볼 것.

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3}"
failed=0

run() {
  echo
  echo "──────────────────────────────────────────────"
  echo " $1"
  echo "──────────────────────────────────────────────"
  shift
  "$@" || failed=$((failed+1))
}

run "보드 프로파일" $PY test/test_board.py

if command -v node >/dev/null 2>&1; then
  run "블록 툴박스 보드 필터" node test/js/board_filter.test.js
  run "프록시 base 경로"      node test/js/proxy_base.test.js
else
  echo
  echo "[건너뜀] 툴박스 필터 / 프록시 시험 — node 가 없습니다."
fi

# 셸(SPA) 브라우저 시험. playwright 가 없으면 스스로 건너뛴다.
run "셸 UI (브라우저)" bash test/ui/run.sh

run "파이썬 문법 (전체)" $PY -m compileall -q openpibo system ide classifier tools test

echo
echo "── 쉘 문법 ──"
for f in system/init system/set_board.sh system/install.sh system/build_wheel.sh \
         system/units/install.sh system/units/capture-from-device.sh \
         requirements/check.sh tools/measure/run.sh; do
  if bash -n "$f" 2>/dev/null; then
    echo "  ok   $f"
  else
    echo " FAIL  $f"; failed=$((failed+1))
  fi
done

echo
if [ $failed -eq 0 ]; then
  echo "전부 통과"
else
  echo "$failed 개 실패"
fi
exit $failed
