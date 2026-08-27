#!/bin/bash
# 레포의 유닛 파일을 /etc/systemd/system/ 으로 심볼릭 링크한다.
#
#   sudo bash system/units/install.sh
#
# 심볼릭 링크라서 레포를 git pull 하면 유닛도 같이 갱신된다.
# 기기에 있던 실물 유닛은 지우지 않고 .bak 로 밀어 둔다.

set -eu
UNIT_DIR="$(cd "$(dirname "$0")" && pwd)"
DST=/etc/systemd/system
STAMP="$(date +%Y%m%d%H%M%S)"

UNITS="booting.service ide.service tools.service classify.service llama-server.service"

for u in $UNITS; do
  src="$UNIT_DIR/$u"

  # 아직 기기에서 떠 오지 않은 유닛은 건드리지 않는다.
  # 채워지지 않은 llama-server 유닛으로 돌고 있는 설정을 덮어쓰면
  # -c 값을 영영 잃는다.
  if grep -q '아직 실물이 아니다' "$src" 2>/dev/null; then
    echo "[건너뜀] $u — 아직 기기에서 떠 오지 않았습니다."
    echo "          sudo bash $UNIT_DIR/capture-from-device.sh 를 먼저 실행하세요."
    continue
  fi

  if [ -f "$DST/$u" ] && [ ! -L "$DST/$u" ]; then
    mv "$DST/$u" "$DST/$u.bak.$STAMP"
    echo "[백업] $DST/$u -> $u.bak.$STAMP"
  fi

  ln -sfn "$src" "$DST/$u"
  echo "[링크] $DST/$u -> $src"
done

systemctl daemon-reload
echo
echo "완료. 부팅 시 뜨게 하려면:"
echo "  sudo systemctl enable booting.service ide.service"
echo "(tools / classify / llama-server 는 ide 가 필요할 때 켠다. enable 하지 말 것)"
