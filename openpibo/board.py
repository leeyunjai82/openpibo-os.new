"""
보드 프로파일 — 파이보 / 파이브레인의 차이가 모이는 **유일한 분기 지점**.

두 레포(openpibo-os.pibo / openpibo-os.pibrain)를 하나로 합치면서,
실측 차이의 대부분이 로직이 아니라 **보드 상수**라는 것이 확인됐다.
그 상수를 전부 이 모듈 뒤로 밀어넣는다.

  from openpibo.board import BOARD

  BOARD.name                 # 'pibo' | 'pibrain'
  BOARD.audio.card           # 'Headphones' | 'MAX98357A'
  BOARD.features.has_legs    # True | False

**새 분기를 만들지 말 것.** `if board == 'pibo'` 를 모듈에 쓰기 시작하면
갈라졌던 두 레포로 돌아간다. 값이 모자라면 프로파일에 키를 추가한다.

프로파일 결정 순서
------------------
1. 환경변수 ``OPENPIBO_BOARD``      — 개발 / 시험용 강제 지정
2. ``/home/pi/.board``              — 기기에 구운 값 (system/set_board.sh 가 쓴다)
3. ``/home/pi/config.json`` 의 ``board`` 키
4. 없으면 'pibo' + 경고             — 기존 파이보 기기가 조용히 깨지지 않게

로컬 덮어쓰기
-------------
``/home/pi/board.toml`` (또는 ``OPENPIBO_BOARD_OVERRIDE``)이 있으면 그 내용을
프로파일 위에 얕게 병합한다. ``[unverified]`` 의 핀 값을 한 대에서만 시험해 볼 때
패키지를 건드리지 않고 쓰라고 둔 자리다.

Class:
:obj:`~openpibo.board.Profile`
"""

import os
import json
import warnings

try:
  import tomllib as _toml
except ImportError:                      # python < 3.11
  import tomli as _toml                  # noqa: F401

__all__ = ['BOARD', 'Profile', 'BOARDS', 'load', 'current_board_name', 'profile_dir']

PROFILE_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'profiles')
BOARD_FILE     = '/home/pi/.board'
CONFIG_FILE    = '/home/pi/config.json'
OVERRIDE_FILE  = '/home/pi/board.toml'
DEFAULT_BOARD  = 'pibo'


class Profile(dict):
  """
  프로파일 한 벌. ``dict`` 이면서 점 표기로도 읽힌다.

  example::

    BOARD.camera.width      # 640
    BOARD['camera']['width']  # 같은 값
  """

  def __getattr__(self, key):
    try:
      value = self[key]
    except KeyError:
      raise AttributeError(
        f"보드 프로파일 '{self.get('name', '?')}' 에 '{key}' 키가 없습니다. "
        f"{PROFILE_DIR} 의 toml 에 추가하세요."
      ) from None
    return Profile(value) if isinstance(value, dict) else value

  def require(self, key):
    """
    ``[unverified]`` 처럼 비어 있을 수 있는 값을 **반드시** 써야 할 때 쓴다.
    비어 있으면 조용히 넘어가지 않고 무엇을 확인해야 하는지 말하고 멈춘다.
    """

    value = self.get(key)
    if value in (None, '', [], {}):
      raise ValueError(
        f"'{key}' 는 아직 확인되지 않은 값입니다. 데이터시트나 실기로 확인한 뒤 "
        f"{PROFILE_DIR} 의 toml 또는 {OVERRIDE_FILE} 에 채우세요. "
        f"(docs/plan/00-decisions.md 2.4)"
      )
    return value


def profile_dir():
  """프로파일 toml 이 들어 있는 디렉토리."""

  return PROFILE_DIR


def _available():
  try:
    return sorted(
      f[:-5] for f in os.listdir(PROFILE_DIR) if f.endswith('.toml')
    )
  except OSError:
    return []


BOARDS = _available()


def current_board_name():
  """
  이 기기가 어느 보드인지 결정한다. 파일을 읽기만 하고 쓰지 않는다.
  """

  name = os.environ.get('OPENPIBO_BOARD', '').strip()
  if name:
    return name

  try:
    with open(BOARD_FILE) as f:
      name = f.read().strip()
    if name:
      return name
  except OSError:
    pass

  try:
    with open(CONFIG_FILE) as f:
      name = str(json.load(f).get('board', '')).strip()
    if name:
      return name
  except (OSError, ValueError):
    pass

  # 조용히 기본값으로 넘어가지 않는다. 보드를 잘못 잡으면 화면도 마이크도
  # 카메라 방향도 전부 틀리는데, 그때 원인을 되짚기가 아주 어렵다.
  # 한 줄로 줄인 것은 IDE 콘솔에 학생 코드와 섞여 보이기 때문이다.
  # `sudo bash system/set_board.sh <보드>` 를 한 번 하면 사라진다.
  warnings.warn(
    f"보드 미지정 — '{DEFAULT_BOARD}' 로 진행합니다 "
    f"(고치기: sudo bash system/set_board.sh <{'|'.join(BOARDS) or 'pibo'}>)",
    RuntimeWarning, stacklevel=2,
  )
  return DEFAULT_BOARD


def _merge(base, over):
  """over 를 base 위에 얕게(절 단위로) 병합한다. 빈 문자열은 '값 없음'으로 본다."""

  for key, value in over.items():
    if isinstance(value, dict) and isinstance(base.get(key), dict):
      _merge(base[key], value)
    elif value not in ('', None):
      base[key] = value
  return base


def load(name=None):
  """
  프로파일을 읽어 :obj:`Profile` 로 돌려준다.

  :param str name: 보드 이름. 생략하면 :func:`current_board_name` 이 정한다.
  """

  name = name or current_board_name()
  path = os.path.join(PROFILE_DIR, f'{name}.toml')

  if not os.path.isfile(path):
    raise FileNotFoundError(
      f"'{name}' 보드 프로파일이 없습니다: {path}\n"
      f"쓸 수 있는 값: {', '.join(BOARDS) or '(없음)'}"
    )

  with open(path, 'rb') as f:
    data = _toml.load(f)

  override = os.environ.get('OPENPIBO_BOARD_OVERRIDE', OVERRIDE_FILE)
  if os.path.isfile(override):
    try:
      with open(override, 'rb') as f:
        _merge(data, _toml.load(f))
    except Exception as ex:                      # 덮어쓰기 파일이 깨져도 부팅은 되어야 한다
      warnings.warn(f"보드 덮어쓰기 파일을 읽지 못했습니다({override}): {ex}", RuntimeWarning)

  data.setdefault('name', name)
  return Profile(data)


#: 현재 기기의 프로파일. import 시 한 번 읽는다.
BOARD = load()


def __getattr__(name):
  """
  Adafruit Blinka 도 ``board`` 라는 **최상위** 모듈을 쓴다 (``board.D8`` 같은 핀 상수).

  ``openpibo/__init__.py`` 가 패키지 경로를 ``sys.path`` 에 append 하기 때문에,
  cwd 가 openpibo 폴더인 채로 파이썬을 띄우면 ``import board`` 가 Blinka 대신
  이 파일을 집을 수 있다. 그러면 oled.py 가 ``board.D8`` 에서 죽는데,
  기본 AttributeError 만 봐서는 원인을 알 수 없다.

  핀 이름처럼 생긴 속성을 찾으면 무슨 일이 났는지 말해 준다.
  """

  if len(name) > 1 and name[0] in 'DAG' and name[1:].isdigit():
    raise AttributeError(
      f"'board.{name}' 은 Adafruit Blinka 의 핀 상수입니다. 그런데 지금 import 된 "
      f"'board' 는 openpibo/board.py(보드 프로파일) 입니다.\n"
      f"openpibo 폴더 안에서 파이썬을 띄우면 이런 일이 납니다. "
      f"다른 폴더에서 실행하거나 `from openpibo import board` 로 명시하세요."
    )
  raise AttributeError(f"module 'openpibo.board' has no attribute '{name}'")


if __name__ == "__main__":
  import sys

  target = sys.argv[1] if len(sys.argv) > 1 else None
  p = load(target) if target else BOARD
  print(json.dumps(p, ensure_ascii=False, indent=2))
