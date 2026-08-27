#!/bin/bash
# 기기에 openpibo-os 를 설치/갱신한다.
#
#   sudo bash system/install.sh              # 전부
#   sudo bash system/install.sh wheel        # 라이브러리만
#   sudo bash system/install.sh units        # systemd 유닛만
#
# 의존성(cv2, dlib, tensorflow ...)은 건드리지 않는다. 기기 이미지에 이미 있다.
# 새로 깔아야 하면:
#   /home/pi/.pyenv/bin/pip install -r requirements/device-all.txt

set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIP="${PIP:-/home/pi/.pyenv/bin/pip}"
WHAT="${1:-all}"

do_wheel() {
  echo "== openpibo-python 설치 =="
  WHL=$(ls -1 "$ROOT"/system/openpibo_python-*.whl 2>/dev/null | head -1 || true)
  if [ -z "$WHL" ]; then
    echo "   system/ 에 whl 이 없습니다. 먼저 만드세요:"
    echo "     bash system/build_wheel.sh"
    exit 1
  fi
  echo "   $WHL"
  # --no-deps: 의존성을 재해석시키면 기기에서 오래 걸리고, 최악의 경우
  # dlib 소스 빌드로 들어간다. 기기에는 이미 다 깔려 있다.
  "$PIP" install --force-reinstall --no-deps "$WHL"
}

do_units() {
  echo "== systemd 유닛 =="
  bash "$ROOT/system/units/install.sh"
}

do_board() {
  echo "== 보드 =="
  if [ -f /home/pi/.board ]; then
    echo "   현재: $(cat /home/pi/.board)"
  else
    echo "   설정되어 있지 않습니다. 지금 정하세요:"
    echo "     sudo bash $ROOT/system/set_board.sh <pibo|pibrain>"
  fi
}

case "$WHAT" in
  wheel) do_wheel ;;
  units) do_units ;;
  all)   do_wheel; echo; do_units; echo; do_board ;;
  *)     echo "쓰는 법: $0 [all|wheel|units]" >&2; exit 1 ;;
esac

echo
echo "완료. 서비스 반영:"
echo "  sudo systemctl restart booting.service ide.service"
