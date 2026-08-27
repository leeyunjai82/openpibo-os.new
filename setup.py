"""
openpibo-python 패키지 빌드.

  bash system/build_wheel.sh          # 권장 — 검사까지 같이 한다
  python3 setup.py bdist_wheel        # 직접

PyPI 에 올리지 않는다. dist/*.whl 을 기기로 옮겨 설치한다.

의존성의 출처는 이 파일이 아니라 requirements/*.txt 다.
두 군데에 적으면 반드시 어긋나므로 여기서는 그 파일을 읽기만 한다.
"""

import os
import re

from setuptools import setup, find_packages

HERE = os.path.dirname(os.path.abspath(__file__))
REQ = os.path.join(HERE, 'requirements')


def read_version():
  """
  openpibo/__init__.py 에서 버전을 읽는다.

  import 하지 않는 이유: 빌드 머신에는 numpy 도 /home/pi 도 없을 수 있다.
  버전 하나 읽자고 패키지를 통째로 import 하면 빌드가 환경을 탄다.
  """

  src = open(os.path.join(HERE, 'openpibo', '__init__.py'), encoding='utf-8').read()
  m = re.search(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", src, re.M)
  if not m:
    raise RuntimeError('openpibo/__init__.py 에서 __version__ 을 찾지 못했습니다.')
  return m.group(1)


def read_requirements(name, _seen=None):
  """requirements/<name>.txt 를 읽는다. -r 을 따라간다."""

  _seen = _seen if _seen is not None else set()
  path = os.path.join(REQ, f'{name}.txt')

  if name in _seen or not os.path.isfile(path):
    return []
  _seen.add(name)

  out = []
  for line in open(path, encoding='utf-8'):
    line = line.split('#')[0].strip()
    if not line:
      continue
    if line.startswith('-r'):
      out += read_requirements(line[2:].strip().replace('.txt', ''), _seen)
    else:
      out.append(line)
  return out


# 핵심 의존성은 **어디서나 설치되는 것**으로 제한한다.
#
# cv2, dlib, mediapipe, picamera2 를 install_requires 에 넣으면 PC 에서
# `pip install openpibo_python.whl` 이 dlib 소스 빌드로 들어가 몇십 분을 태우거나
# 그냥 실패한다. 기기에는 이미 다 깔려 있고, 없으면 requirements/device-all.txt 로
# 한 번에 넣는다.
#
#   pip install openpibo_python-*.whl                 # 라이브러리만
#   pip install "openpibo_python-*.whl[all]"          # 의존성까지 전부
install_requires = read_requirements('base') + read_requirements('models')

extras_require = {
  'device':   read_requirements('device'),
  'vision':   read_requirements('vision'),
  'server':   read_requirements('server'),
  'optional': read_requirements('optional'),
}
extras_require['all'] = sorted({
  r for k, v in extras_require.items() if k != 'optional' for r in v
})

setup(
  name='openpibo-python',
  version=read_version(),
  description='openpibo-python package. (pibo / pibrain 통합)',
  long_description=open(os.path.join(HERE, 'README.rst'), encoding='utf-8').read(),
  long_description_content_type='text/x-rst',
  author='circulus',
  author_email='leeyunjai@circul.us',
  url='https://github.com/themakerrobot/openpibo-os',
  packages=find_packages(include=['openpibo', 'openpibo.*']),

  # 보드 프로파일은 코드가 아니라 데이터다. 하지만 이게 없으면
  # openpibo.board 가 import 되자마자 실패한다. 반드시 wheel 에 들어가야 한다.
  package_data={'openpibo': ['profiles/*.toml']},
  include_package_data=True,
  zip_safe=False,

  install_requires=install_requires,
  extras_require=extras_require,
  python_requires='>=3.9',
  keywords='openpibo pibo pibrain',
  classifiers=[
    'Natural Language :: Korean',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Operating System :: POSIX :: Linux',
  ],
)
