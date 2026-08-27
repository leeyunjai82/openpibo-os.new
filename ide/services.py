"""
뒤쪽 서비스를 켜고 끄고, **실제로 뜰 때까지** 지켜본다.

지금까지는 `systemctl start` 를 던지고 3초 기다렸다.

    fetch('/tools?enable=on').then(() => setTimeout(() => window.open(...), 3000))

3초는 근거가 없었고, 더 나쁜 건 `systemctl is-active` 가 **uvicorn 이 포트를 잡기
전에 이미 active 를 돌려준다**는 점이다. 유닛이 떴다는 것과 앱이 응답한다는 것은
다른 얘기다. 그래서 여기서는 두 단계를 나눠서 본다.

    starting -> active(유닛이 떴다) -> ready(포트가 응답한다)

`ready` 가 되어야 화면을 넘긴다.

전환 지연은 숨기지 않는다. 몇 초가 걸리든 그대로 보여준다
(docs/plan/00-decisions.md 5.1 "전환 지연은 숨기지 말고 정직하게 보여준다").
"""

import asyncio
import json
import logging
import subprocess

from proxy import HOST, UPSTREAMS

logger = logging.getLogger(__name__)

#: 서로 자원을 독점해서 동시에 못 뜬다. 하나를 켜면 나머지를 끈다.
#: systemd 유닛에도 Conflicts= 를 걸어 뒀지만, 여기서도 명시적으로 끈다 —
#: 유닛이 아직 레포 것으로 교체되지 않은 기기가 있을 수 있다.
#: (docs/plan/00-decisions.md 4.3 — Detect() 789MB + LLM 800~950MB 는 2GB 에 못 들어간다)
EXCLUSIVE = set(UPSTREAMS)

#: ready 까지 기다릴 최대 시간(초). LLM 은 모델 적재가 있어 더 준다.
READY_TIMEOUT = {'tools': 60, 'classify': 60, 'llm': 180}


def unit_of(name):
  return UPSTREAMS[name]['unit']


def is_active(name):
  """
  systemd 가 유닛을 active 로 보는가. **앱이 응답한다는 뜻은 아니다.**

  :returns: True / False / None(systemctl 을 부를 수 없음)

  None 을 따로 두는 이유: systemctl 이 없는 환경(컨테이너, 개발 PC)에서
  False 를 돌려주면 "유닛이 죽었다"로 오인해 멀쩡히 돌고 있는 서비스를
  실패로 보고하게 된다.
  """

  try:
    out = subprocess.run(
      ['systemctl', 'is-active', unit_of(name)],
      capture_output=True, text=True, timeout=5,
    )
    return out.stdout.strip() == 'active'
  except FileNotFoundError:
    return None
  except Exception as ex:
    logger.warning('[services] is-active %s 실패: %r', name, ex)
    return None


async def is_ready(name, timeout=1.0):
  """포트가 실제로 TCP 연결을 받는가. 이게 '쓸 수 있다'의 기준이다."""

  port = UPSTREAMS[name]['port']
  try:
    reader, writer = await asyncio.wait_for(
      asyncio.open_connection(HOST, port), timeout=timeout)
    writer.close()
    try:
      await writer.wait_closed()
    except Exception:
      pass
    return True
  except (OSError, asyncio.TimeoutError):
    return False


def start(name):
  """name 을 켜고 나머지 배타 서비스를 끈다. 기다리지 않는다."""

  for other in EXCLUSIVE - {name}:
    subprocess.Popen(['systemctl', 'stop', unit_of(other)])
  subprocess.Popen(['systemctl', 'start', unit_of(name)])


def stop(name):
  subprocess.Popen(['systemctl', 'stop', unit_of(name)])


async def status(name):
  """지금 상태를 한 번 본다."""

  active = is_active(name)
  # ready 는 active 와 무관하게 항상 직접 확인한다.
  # 포트가 응답하는지가 유일하게 믿을 수 있는 기준이다.
  ready = await is_ready(name)
  return {
    'name': name,
    'unit': unit_of(name),
    'port': UPSTREAMS[name]['port'],
    'active': active,
    'ready': ready,
    'path': f'/{name}/',
  }


def _sse(event):
  return f'data: {json.dumps(event, ensure_ascii=False)}\n\n'


async def watch(name, timeout=None):
  """
  `ready` 가 될 때까지 진행 상태를 SSE 로 흘려보낸다.

  프론트는 이 스트림만 보고 스피너 문구를 바꾸고, `ready` 를 받으면 화면을 넘긴다.
  실패하면 왜 실패했는지도 같이 보낸다 — 조용히 멈추면 아이도 교사도 뭘 해야 할지
  모른다.
  """

  timeout = timeout or READY_TIMEOUT.get(name, 60)
  waited = 0.0
  step = 0.5
  phase = None

  while True:
    # 순서가 중요하다. ready 를 먼저, 무조건 본다.
    # is_active 를 통과해야만 ready 를 보게 하면, systemd 가 뭐라 하든
    # 실제로 응답하고 있는 서비스를 영원히 starting 으로 보고하게 된다.
    ready = await is_ready(name)
    active = is_active(name)          # True / False / None(systemctl 없음)

    now = 'ready' if ready else ('active' if active else 'starting')
    changed = now != phase
    phase = now

    if ready:
      yield _sse({'phase': 'ready', 'name': name, 'path': f'/{name}/',
                  'elapsed': round(waited, 1)})
      return

    # 유닛이 확실히 죽었을 때만 일찍 접는다.
    # active is None 이면 systemctl 을 못 부른 것이므로 판단 근거가 없다 —
    # 타임아웃까지 계속 포트를 두드린다.
    if active is False and waited > 3:
      yield _sse({
        'phase': 'failed', 'name': name, 'elapsed': round(waited, 1),
        'reason': f'{unit_of(name)} 가 뜨지 않았습니다. '
                  f'`systemctl status {unit_of(name)}` 를 확인하세요.',
      })
      return

    if waited >= timeout:
      yield _sse({
        'phase': 'timeout', 'name': name, 'elapsed': round(waited, 1),
        'reason': f'{timeout}초 안에 응답하지 않았습니다.',
      })
      return

    # 몇 초가 걸리는지 그대로 보여준다. 단계가 바뀌었을 때는 반드시 보낸다.
    yield _sse({'phase': phase, 'name': name, 'elapsed': round(waited, 1),
                'changed': changed})

    await asyncio.sleep(step)
    waited += step
