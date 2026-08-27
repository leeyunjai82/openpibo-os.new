#!/bin/bash
# 셸(SPA)을 진짜 브라우저로 몰아 본다. **하드웨어가 필요 없다.**
#
#   bash test/ui/run.sh
#
# 필요한 것: playwright + 크로미움
#   pip install playwright && playwright install chromium
#
# 무엇을 흉내내나
#   fakedev/system.sh   system.sh 출력
#   fake_booting.py     booting.py(:8080) — 와이파이
#   fake_upstream.py    tools(:50000)     — 배지/프록시
#   shell_host.py       run_ide.py 의 2단계 계층만 (하드웨어 import 없이)

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3}"

if ! $PY -c "import playwright" 2>/dev/null; then
  echo "[건너뜀] playwright 가 없습니다:  pip install playwright && playwright install chromium"
  exit 0
fi

export OPENPIBO_HOME="${OPENPIBO_HOME:-$ROOT/.tmp-ui}"
export OPENPIBO_BOARD="${OPENPIBO_BOARD:-pibrain}"
mkdir -p "$OPENPIBO_HOME"

$PY test/ui/fake_booting.py  >/dev/null 2>&1 & FB=$!
$PY test/ui/fake_upstream.py 50000 >/dev/null 2>&1 & UP=$!
$PY test/ui/shell_host.py    >/dev/null 2>&1 & SH=$!
cleanup() { kill $FB $UP $SH 2>/dev/null; }
trap cleanup EXIT

for _ in $(seq 1 60); do
  curl -s -o /dev/null http://127.0.0.1:18080/ && break
  sleep 0.25
done

$PY test/ui/shell_test.py
