"""
응답 봉투. vapi-od `view_project` 의 규약을 그대로 가져온다.

    { "type": "...", "result": "ok"|"fail", "data": ..., "elapsed_ms": 12, "device": "pibo" }

**왜 봉투를 씌우나**

지금 허브의 응답이 제각각이다. 어떤 건 문자열, 어떤 건 dict, 어떤 건 빈 HTML 이다.
프론트가 매번 다르게 받아야 하고, 실패했는지 아닌지도 형식이 달라 알기 어렵다.
사내에 이미 자리잡은 규약이 있으니 그걸 쓴다 (docs/plan/02-roadmap.md 2단계 1항).

``elapsed_ms`` 는 장식이 아니다. 파이 4 에서는 어떤 호출이 느린지가 바로 UX 다.
화면이 "왜 멈춰 있지"를 추측하지 않아도 되게 숫자를 같이 준다.

``device`` 는 어느 보드가 답했는지다. 교실에 파이보와 파이브레인이 섞여 있을 때
응답만 보고 구분할 수 있어야 한다.
"""

import time
import traceback

from fastapi.responses import JSONResponse

from openpibo.board import BOARD


def ok(type_, data=None, started=None, status=200):
  """성공 응답."""

  return JSONResponse(status_code=status, content={
    'type': type_,
    'result': 'ok',
    'data': data,
    'elapsed_ms': _elapsed(started),
    'device': BOARD.name,
  })


def fail(type_, message, started=None, status=500, detail=None):
  """
  실패 응답.

  ``message`` 는 **화면에 그대로 띄울 수 있는 문장**이어야 한다.
  아이가 읽는다. detail 에 개발자용 내용을 따로 담는다.
  """

  return JSONResponse(status_code=status, content={
    'type': type_,
    'result': 'fail',
    'data': {'message': message, 'detail': detail},
    'elapsed_ms': _elapsed(started),
    'device': BOARD.name,
  })


def _elapsed(started):
  return None if started is None else int((time.monotonic() - started) * 1000)


class Envelope:
  """
  ``with Envelope('system.info') as e:`` 로 쓰면 시간 재기와 예외 처리를 같이 해준다.

  example::

    with Envelope('system.info') as e:
      return e.ok(read_info())
  """

  def __init__(self, type_):
    self.type = type_
    self.started = time.monotonic()

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc, tb):
    return False

  def ok(self, data=None, status=200):
    return ok(self.type, data, self.started, status)

  def fail(self, message, status=500, detail=None):
    return fail(self.type, message, self.started, status, detail)

  def from_exception(self, ex, message=None):
    """예상 못 한 예외를 봉투에 담는다. 트레이스백은 detail 로만 나간다."""

    return self.fail(
      message or f'처리 중 문제가 생겼습니다: {type(ex).__name__}',
      detail=''.join(traceback.format_exception_only(type(ex), ex)).strip(),
    )
