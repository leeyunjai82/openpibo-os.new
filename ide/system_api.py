"""
`/api/system/*` — 설정 모달이 쓰는 것들.

지금까지 이 기능들이 흩어져 있었다.

  - 시스템 정보: landing.html 이 socket.io `system` 이벤트로 받음
  - 와이파이:    landing.html 이 **다른 origin**(`http://ip:8080`)으로 직접 fetch
  - 로그/초기화/전원: socket.io 이벤트

설정은 어느 탭에서든 열려야 하는데(00-decisions.md 5.2), 그러려면 셸이
socket.io 를 또 붙이거나 다른 origin 으로 나가야 했다. 둘 다 하지 않는다.
전부 같은 origin 의 REST 로 모으고 봉투를 씌운다.

와이파이는 booting.py(:8080)가 들고 있다. 여기서 중계한다 — **마지막 남은
교차 출처 호출을 없앤다.**
"""

import asyncio
import logging
import os
import subprocess

import httpx

from envelope import Envelope
from openpibo.board import BOARD

logger = logging.getLogger(__name__)

BOOTING = 'http://127.0.0.1:8080'
SYSTEM_SH = '/home/pi/openpibo-os/system/system.sh'

#: system.sh 가 콤마로 뱉는 순서. 위치로 읽으면 나중에 반드시 어긋난다.
SYSTEM_FIELDS = [
  'serial', 'os_version', 'uptime', 'temp', 'mem_total', 'mem_avail',
  'wlan0', 'eth1', 'ssid', 'psk', 'identity', 'key_mgmt',
]


def read_system():
  """system.sh 출력을 이름 붙은 dict 로."""

  raw = subprocess.check_output([SYSTEM_SH], timeout=10).decode().strip('\n')
  parts = raw.split(',')
  info = {k: (parts[i] if i < len(parts) else '') for i, k in enumerate(SYSTEM_FIELDS)}

  # psk 는 와이파이 비밀번호다. 상태 조회 응답에 실어 보내지 않는다.
  # 설정 화면이 굳이 알 필요가 없고, 로그나 캐시에 남으면 그대로 유출이다.
  info.pop('psk', None)

  # 화면이 쓰기 좋게 몇 개를 다듬는다
  ip = info['eth1'] if info['eth1'][:3] not in ('', '169') else ''
  if not ip and info['wlan0'][:3] not in ('', '169'):
    ip = info['wlan0']
  info['ip'] = ip.strip()
  info['board'] = BOARD.name
  info['board_label'] = BOARD.label

  try:
    info['mem_used_percent'] = round(
      (int(info['mem_total']) - int(info['mem_avail'])) / int(info['mem_total']) * 100)
  except (ValueError, ZeroDivisionError):
    info['mem_used_percent'] = None

  return info


async def forward(method, path, **kw):
  """booting.py 로 넘긴다. 와이파이가 거기 있다."""

  async with httpx.AsyncClient(timeout=20) as client:
    resp = await client.request(method, f'{BOOTING}{path}', **kw)
    resp.raise_for_status()
    return resp.json()


class Hooks:
  """
  허브가 들고 있는 상태를 읽는 통로.

  run_ide 의 전역(``ps``, ``record``)을 여기서 직접 만지지 않으려고 함수로 받는다.
  전역을 두 파일이 같이 만지기 시작하면 어디서 바뀌었는지 못 찾는다.
  """

  def __init__(self, code_running, record, halt):
    self.code_running = code_running   # () -> bool
    self.record = record               # () -> str
    self.halt = halt                   # () -> None (MCU 전원 차단 등)


def register(app, services, proxy, hooks):
  """라우트를 붙인다."""

  from fastapi import Body
  from fastapi.responses import StreamingResponse
  import json

  @app.get('/api/system/info')
  async def system_info():
    with Envelope('system.info') as e:
      try:
        return e.ok(read_system())
      except Exception as ex:
        logger.warning('[system] info 실패: %r', ex)
        return e.from_exception(ex, '시스템 정보를 읽지 못했습니다.')

  @app.get('/api/system/status')
  async def system_status():
    """
    상태 배지가 쓰는 값. **자원을 누가 잡고 있는지**를 항상 드러낸다
    (00-decisions.md 5.2).
    """

    with Envelope('system.status') as e:
      try:
        svc = {n: await services.status(n) for n in proxy.UPSTREAMS}
        # 카메라는 tools 와 classify 가 독점한다. 둘 중 떠 있는 쪽이 주인이다.
        camera_owner = next(
          (n for n in ('tools', 'classify') if svc[n]['ready']), None)
        return e.ok({
          'services': svc,
          'code_running': bool(hooks.code_running()),
          'camera_owner': camera_owner,
          'model_loading': any(s['active'] and not s['ready'] for s in svc.values()),
          'board': BOARD.name,
        })
      except Exception as ex:
        return e.from_exception(ex, '상태를 읽지 못했습니다.')

  @app.get('/api/system/events')
  async def system_events():
    """상태를 계속 흘려보낸다. 배지가 이걸 보고 바뀐다."""

    async def stream():
      last = None
      while True:
        try:
          svc = {n: await services.status(n) for n in proxy.UPSTREAMS}
          payload = {
            'services': svc,
            'code_running': bool(hooks.code_running()),
            'camera_owner': next(
              (n for n in ('tools', 'classify') if svc[n]['ready']), None),
            'model_loading': any(s['active'] and not s['ready'] for s in svc.values()),
          }
        except Exception as ex:
          payload = {'error': str(ex)}

        blob = json.dumps(payload, ensure_ascii=False)
        # 안 바뀌었으면 보내지 않는다. 교실에서 파이 여러 대가 붙으면
        # 2초마다 쏘는 것만으로도 부담이 된다.
        if blob != last:
          last = blob
          yield f'data: {blob}\n\n'
        else:
          yield ': keep-alive\n\n'      # 프록시가 끊지 않게
        await asyncio.sleep(2)

    return StreamingResponse(stream(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache',
                                      'X-Accel-Buffering': 'no'})

  @app.get('/api/system/wifi/scan')
  async def wifi_scan():
    with Envelope('system.wifi.scan') as e:
      try:
        return e.ok(await forward('GET', '/wifi_scan'))
      except Exception as ex:
        return e.from_exception(ex, '주변 와이파이를 찾지 못했습니다.')

  @app.get('/api/system/wifi')
  async def wifi_get():
    with Envelope('system.wifi') as e:
      try:
        data = await forward('GET', '/wifi')
        data.pop('psk', None)       # 비밀번호는 돌려주지 않는다
        return e.ok(data)
      except Exception as ex:
        return e.from_exception(ex, '와이파이 정보를 읽지 못했습니다.')

  @app.post('/api/system/wifi')
  async def wifi_set(payload: dict = Body(...)):
    with Envelope('system.wifi.set') as e:
      if not payload.get('ssid'):
        return e.fail('와이파이 이름(SSID)을 입력하세요.', status=400)
      try:
        # booting.py 가 접속 후 재부팅한다. 응답을 못 받을 수 있다.
        return e.ok(await forward('POST', '/wifi', json=payload))
      except Exception as ex:
        return e.from_exception(ex, '와이파이 설정에 실패했습니다.')

  @app.get('/api/system/log')
  async def system_log():
    with Envelope('system.log') as e:
      return e.ok({'record': hooks.record()})

  @app.post('/api/system/power/{action}')
  async def system_power(action: str):
    with Envelope(f'system.power.{action}') as e:
      if action not in ('off', 'restart'):
        return e.fail(f'알 수 없는 동작입니다: {action}', status=400)
      try:
        if action == 'off':
          hooks.halt()
          subprocess.Popen(['shutdown', '-h', 'now'])
        else:
          subprocess.Popen(['shutdown', '-r', 'now'])
        return e.ok({'action': action})
      except Exception as ex:
        return e.from_exception(ex, '전원 명령을 보내지 못했습니다.')
