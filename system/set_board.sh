#!/bin/bash
# 이 기기가 어느 보드인지 정한다. openpibo.board 가 이 값을 읽는다.
#
#   sudo bash system/set_board.sh pibo
#   sudo bash system/set_board.sh pibrain
#   bash system/set_board.sh              # 지금 값 확인
#
# /home/pi/.board 에 이름 한 줄을 쓴다. config.json 의 board 키도 같이 맞춘다.

set -eu

BOARD_FILE=/home/pi/.board
CONFIG_FILE=/home/pi/config.json
PROFILE_DIR="$(cd "$(dirname "$0")/.." && pwd)/openpibo/profiles"

if [ $# -eq 0 ]; then
  if [ -f "$BOARD_FILE" ]; then
    echo "현재 보드: $(cat "$BOARD_FILE")"
  else
    echo "현재 보드: (설정 안 됨 — openpibo.board 가 pibo 로 넘어가며 경고합니다)"
  fi
  echo "쓸 수 있는 값: $(ls "$PROFILE_DIR" 2>/dev/null | sed 's/\.toml$//' | tr '\n' ' ')"
  exit 0
fi

NAME="$1"

if [ ! -f "$PROFILE_DIR/$NAME.toml" ]; then
  echo "'$NAME' 프로파일이 없습니다: $PROFILE_DIR/$NAME.toml" >&2
  echo "쓸 수 있는 값: $(ls "$PROFILE_DIR" | sed 's/\.toml$//' | tr '\n' ' ')" >&2
  exit 1
fi

echo "$NAME" > "$BOARD_FILE"
chown pi:pi "$BOARD_FILE" 2>/dev/null || true

# config.json 의 board 키도 맞춰 둔다. 웹 UI 가 이쪽을 읽는다.
if [ -f "$CONFIG_FILE" ]; then
  /home/pi/.pyenv/bin/python3 - "$CONFIG_FILE" "$NAME" <<'PY'
import json, sys
path, name = sys.argv[1], sys.argv[2]
try:
    with open(path) as f:
        cfg = json.load(f)
except Exception:
    cfg = {}
cfg['board'] = name
with open(path, 'w') as f:
    json.dump(cfg, f)
PY
  chown pi:pi "$CONFIG_FILE" 2>/dev/null || true
fi

echo "보드를 '$NAME' 으로 설정했습니다."
echo "이미 떠 있는 서비스는 다시 시작해야 반영됩니다:"
echo "  sudo systemctl restart booting.service ide.service"
