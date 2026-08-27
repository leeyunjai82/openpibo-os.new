#!/bin/bash
# 지금 환경이 명세와 맞는지 본다. 아무것도 설치하지 않는다.
#
#   bash requirements/check.sh              # 기기 전체(device-all) 기준
#   bash requirements/check.sh base server  # 일부만
#
# 보여주는 것
#   [빠짐] 명세에 있는데 안 깔린 것
#   [남음] 깔렸는데 명세에도 frozen 참고에도 근거가 없는 것
#   [겹침] 같은 모듈을 두 패키지가 제공해 깨질 수 있는 조합

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REQ="$ROOT/requirements"
PY="${PYTHON:-python3}"

SETS=("$@")
[ ${#SETS[@]} -eq 0 ] && SETS=(device-all)

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
: > "$TMP/conditional"

# -r 을 따라가며 패키지 이름만 뽑는다
expand() {
  local f="$1"
  [ -f "$f" ] || return
  while IFS= read -r line; do
    line="${line%%#*}"
    line="$(echo "$line" | tr -d '[:space:]')"
    [ -z "$line" ] && continue
    case "$line" in
      -r*) expand "$REQ/${line#-r}" ;;
      # 환경 마커(; python_version < "3.11" 등)가 붙은 줄은 여기서 판정하지 않는다.
      # 조건에 안 맞는 것을 "빠짐"으로 보고하면 매번 거짓 경보가 난다.
      *\;*) echo "$line" | sed 's/[<>=!;].*//' | tr 'A-Z_.' 'a-z--' >> "$TMP/conditional" ;;
      *)   echo "$line" | sed 's/[<>=!].*//' | tr 'A-Z_.' 'a-z--' ;;
    esac
  done < "$f"
}

for s in "${SETS[@]}"; do expand "$REQ/$s.txt"; done | sort -u > "$TMP/want"

if ! $PY -m pip --version >/dev/null 2>&1; then
  echo "pip 을 찾지 못했습니다 ($PY). PYTHON=... 로 지정하세요." >&2
  exit 1
fi
$PY -m pip freeze 2>/dev/null | sed 's/[<>=@ ].*//' | tr 'A-Z_.' 'a-z--' | sort -u > "$TMP/have"

echo "명세: ${SETS[*]}  ($(wc -l < "$TMP/want") 개)"
echo "설치: $($PY -c 'import sys;print(sys.executable)')  ($(wc -l < "$TMP/have") 개)"
echo

missing=$(comm -23 "$TMP/want" "$TMP/have")
if [ -n "$missing" ]; then
  echo "[빠짐] 명세에 있는데 안 깔렸습니다:"
  echo "$missing" | sed 's/^/    /'
else
  echo "[빠짐] 없음"
fi

if [ -s "$TMP/conditional" ]; then
  echo "[조건부] 환경 마커가 붙어 있어 판정하지 않았습니다:"
  sort -u "$TMP/conditional" | sed 's/^/    /'
fi
echo

# frozen 에도 없고 명세에도 없는 것만 남음으로 본다.
# (frozen 에 있는 건 기기에서 돌던 것이라 함부로 남는다고 말하지 않는다)
cat "$REQ"/frozen/*.txt 2>/dev/null | sed 's/#.*//;s/[<>=@ ].*//' \
  | tr 'A-Z_.' 'a-z--' | grep -v '^$' | sort -u > "$TMP/frozen"
extra=$(comm -23 "$TMP/have" "$TMP/want" | comm -23 - "$TMP/frozen")
if [ -n "$extra" ]; then
  echo "[남음] 깔렸는데 명세에도 frozen 에도 없습니다 (의존성으로 딸려온 것일 수 있음):"
  echo "$extra" | sed 's/^/    /' | head -40
else
  echo "[남음] 없음"
fi
echo

# 같은 모듈을 두 패키지가 제공하는 조합. 버전이 어긋나면 깨진다.
echo "[겹침]"
conflict=0
check_pair() {
  if grep -qx "$1" "$TMP/have" && grep -qx "$2" "$TMP/have"; then
    echo "    $1 + $2  — 같은 '$3' 를 제공합니다. 하나만 남기세요."
    conflict=1
  fi
}
check_pair opencv-python opencv-contrib-python cv2
check_pair rpi-lgpio rpi-gpio RPi.GPIO
[ $conflict -eq 0 ] && echo "    없음"
