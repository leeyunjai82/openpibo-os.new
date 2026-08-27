#!/bin/bash
# openpibo-python wheel 을 만든다.
#
#   bash system/build_wheel.sh
#
# 결과: dist/openpibo_python-<버전>-py3-none-any.whl
#       + system/ 의 whl 을 새 것으로 교체 (기기 이미지가 이걸 쓴다)
#
# PyPI 에 올리지 않는다.

set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"

echo "== 준비 =="
if ! $PY -c "import setuptools, wheel" 2>/dev/null; then
  echo "setuptools / wheel 이 없습니다:"
  echo "  $PY -m pip install -r requirements/build.txt"
  exit 1
fi

VERSION=$($PY -c "import re;print(re.search(r'__version__\s*=\s*[\'\"]([^\'\"]+)', open('openpibo/__init__.py').read()).group(1))")
echo "   버전 $VERSION"

echo
echo "== 빌드 전 확인 =="
# 프로파일이 wheel 에 들어가지 않으면 기기에서 import openpibo.board 가 바로 죽는다.
# 빌드가 조용히 성공하고 기기에서 터지는 것이 제일 나쁘다.
for f in openpibo/profiles/pibo.toml openpibo/profiles/pibrain.toml; do
  [ -f "$f" ] || { echo "   [없음] $f"; exit 1; }
  echo "   [있음] $f"
done

echo
echo "== 빌드 =="
rm -rf build dist openpibo_python.egg-info
$PY setup.py -q bdist_wheel

WHL=$(ls -1 dist/*.whl | head -1)
echo "   $WHL"

echo
echo "== wheel 내용 확인 =="
# 프로파일이 실제로 들어갔는지 본다. 목록에 없으면 실패로 친다.
if $PY -c "
import zipfile, sys
names = zipfile.ZipFile('$WHL').namelist()
want = ['openpibo/profiles/pibo.toml', 'openpibo/profiles/pibrain.toml']
missing = [w for w in want if w not in names]
for n in sorted(n for n in names if 'profiles' in n): print('   [담김]', n)
sys.exit(1 if missing else 0)
"; then
  echo "   프로파일 확인"
else
  echo "   [실패] 프로파일이 wheel 에 없습니다. MANIFEST.in / package_data 를 보세요."
  exit 1
fi

echo
echo "== system/ 갱신 =="
# 기기 이미지가 system/ 의 whl 을 쓴다. 옛 버전은 지운다.
rm -f system/openpibo_python-*.whl
cp "$WHL" system/
echo "   system/$(basename "$WHL")"

echo
echo "완료."
echo "기기에 넣기:"
echo "  /home/pi/.pyenv/bin/pip install --force-reinstall --no-deps system/$(basename "$WHL")"
echo "(--no-deps: 기기에는 의존성이 이미 다 깔려 있다. 재해석시키면 오래 걸리고 위험하다)"
