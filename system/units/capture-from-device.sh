#!/bin/bash
# 기기에서 돌고 있는 systemd 유닛을 레포로 떠 온다.
#
# 왜 필요한가: 지금 유닛 파일이 기기의 /etc/systemd/system/ 에만 있어서
# 이미지를 다시 구우면 재현이 안 된다 (docs/plan/04-known-issues.md 12).
# 특히 llama-server 의 -c(컨텍스트) 값은 코드 어디에도 없다.
#
#   sudo bash system/units/capture-from-device.sh
#
# 뜬 파일을 git diff 로 확인하고 커밋할 것. 그대로 덮어쓰기만 한다.

set -u
UNIT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC=/etc/systemd/system

UNITS="booting.service ide.service tools.service classify.service llama-server.service"

captured=0
for u in $UNITS; do
  if [ -f "$SRC/$u" ]; then
    cp "$SRC/$u" "$UNIT_DIR/$u"
    echo "[받음] $u"
    captured=$((captured+1))
  else
    echo "[없음] $u  ($SRC/$u 가 없습니다)"
  fi
done

echo
echo "$captured 개를 $UNIT_DIR 로 가져왔습니다."
echo "git diff 로 확인한 뒤 커밋하세요."
