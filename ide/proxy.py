"""
허브가 뒤쪽 서비스를 **같은 origin 으로** 중계한다.

지금까지는 카드를 누르면 3초 기다렸다가 다른 포트를 새 창으로 열었다.

    fetch(`http://${location.hostname}/tools?enable=on`)
      .then(() => setTimeout(() => {
          window.open(`http://${location.hostname}:50000`);   // 다른 origin, 새 창
      }, 3000))

세션도 뒤로가기도 다 끊기고, 3초는 근거 없는 추측이었다.
(docs/plan/00-decisions.md 5.1)

이제 전부 ``http://<ip>/`` 하나 아래로 들어온다.

    /tools/*     -> 127.0.0.1:50000
    /classify/*  -> 127.0.0.1:50010
    /llm/*       -> 127.0.0.1:50020

**프로세스 통합이 아니다.** systemd 가 서로를 죽이는 구조는 그대로다
(2GB 라 셋이 동시에 못 뜬다). origin 만 하나로 합친 것이고,
나중에 프로세스를 합쳐도 **프론트는 안 바뀐다** — 프록시 경로가 내부 라우팅으로
바뀔 뿐이다.

중계할 때 손봐야 하는 것 두 가지
--------------------------------
1. **자산 경로.** 뒤쪽 앱의 템플릿이 ``../static/...`` 을 쓴다. ``/tools/`` 아래에서
   그대로 두면 브라우저가 허브의 ``/static/`` 을 찾아간다. HTML 을 지나갈 때
   ``/tools/static/`` 으로 바꿔 준다.
2. **JS 안의 절대 URL.** ``fetch(`http://${location.host}/control_cam`)`` 같은 것들이
   허브 루트로 간다. HTML 에 ``window.__BASE__`` 를 심어 주고, 앱 JS 가 그걸
   앞에 붙이게 했다. 직접 포트로 접속하면 ``__BASE__`` 가 없어 '' 가 되므로
   예전처럼 그대로 돈다.
"""

import logging

import httpx
import websockets
from fastapi import Request, WebSocket
from fastapi.responses import Response, StreamingResponse
from starlette.websockets import WebSocketDisconnect

logger = logging.getLogger(__name__)

#: 경로 앞머리 -> 뒤쪽 서비스. systemd 유닛 이름도 같이 들고 있다.
UPSTREAMS = {
  'tools':    {'port': 50000, 'unit': 'tools.service'},
  'classify': {'port': 50010, 'unit': 'classify.service'},
  'llm':      {'port': 50020, 'unit': 'llama-server.service'},
}

HOST = '127.0.0.1'

# 중계하면 안 되는 헤더. 홉 단위(hop-by-hop) 헤더와 길이/인코딩 관련이다.
# 특히 content-length 를 그대로 넘기면 본문을 고쳐 쓴 뒤에 길이가 안 맞는다.
_DROP = {
  'content-length', 'content-encoding', 'transfer-encoding',
  'connection', 'keep-alive', 'upgrade',
  'proxy-authenticate', 'proxy-authorization', 'te', 'trailer',
}

# 스트리밍으로 넘겨야 하는 것. 버퍼에 모으면 화면이 안 움직인다.
_STREAM_TYPES = ('text/event-stream', 'multipart/x-mixed-replace')


def upstream_of(request_path):
  """'/tools/foo' -> ('tools', '/foo'). 해당 없으면 (None, None)."""

  parts = request_path.lstrip('/').split('/', 1)
  name = parts[0]
  if name not in UPSTREAMS:
    return None, None
  return name, '/' + (parts[1] if len(parts) > 1 else '')


def _rewrite_html(body, name):
  """
  뒤쪽 앱의 HTML 을 ``/<name>/`` 아래에서도 열리게 고친다.

  - ``../static/`` -> ``/<name>/static/``  (템플릿이 상대 경로를 쓴다)
  - ``window.__BASE__`` 주입          (JS 가 절대 URL 을 만들 때 앞에 붙인다)
  """

  text = body.decode('utf-8', errors='replace')
  text = text.replace('"../static/', f'"/{name}/static/')
  text = text.replace("'../static/", f"'/{name}/static/")

  inject = (
    '<script>'
    f'window.__BASE__="/{name}";'
    '</script>'
  )
  if '<head>' in text:
    text = text.replace('<head>', '<head>\n' + inject, 1)
  else:
    text = inject + text

  return text.encode('utf-8')


def _clean_headers(headers):
  return {k: v for k, v in headers.items() if k.lower() not in _DROP}


def _without_multi(headers):
  """set-cookie 는 _apply_multi_headers 가 따로 붙인다. 여기서는 뺀다."""

  return {k: v for k, v in headers.items() if k.lower() != 'set-cookie'}


def _rewrite_location(value, name):
  """
  뒤쪽 앱이 준 Location 을 프록시 경로로 옮긴다.

  뒤쪽은 자기가 루트에 있는 줄 알고 ``/landed`` 를 준다. 그대로 넘기면
  브라우저가 **허브 루트**의 /landed 로 가버린다. ``/tools/landed`` 로 고친다.

  절대 URL(https://...)이나 프로토콜 상대(//host/...)는 바깥을 가리키는
  것이므로 건드리지 않는다.
  """

  if not value or value.startswith('//') or '://' in value:
    return value
  if value.startswith('/'):
    return f'/{name}{value}'
  return value                      # 상대 경로는 브라우저가 알아서 푼다


def _apply_multi_headers(response, headers, name):
  """
  중복될 수 있는 헤더(Set-Cookie)를 살려서 붙인다.

  dict 로 모으면 같은 이름이 하나로 접혀 **쿠키가 조용히 사라진다.**
  지금 앱들은 쿠키를 안 쓰지만, 쓰기 시작하는 순간 원인을 찾기 어려운 버그가 된다.
  """

  for key, value in headers.multi_items():
    low = key.lower()
    if low in _DROP:
      continue
    if low == 'set-cookie':
      response.raw_headers.append((b'set-cookie', value.encode('latin-1')))
    elif low == 'location':
      # 이미 dict 로 한 번 들어갔으므로 값을 바꿔 넣는다
      response.headers['location'] = _rewrite_location(value, name)


async def proxy_http(request: Request, name: str, path: str, client: httpx.AsyncClient):
  """
  HTTP 한 건을 뒤쪽으로 넘긴다.

  SSE 와 MJPEG 는 스트리밍으로, 나머지는 통째로 받는다.
  HTML 이면 자산 경로를 고쳐서 돌려준다.
  """

  port = UPSTREAMS[name]['port']
  # 쿼리를 원문 그대로 URL 에 붙인다.
  # httpx 의 params= 로 넘기면 같은 키가 여러 번 온 것(x=1&x=2)이 하나로 접힌다.
  query = request.url.query
  url = f'http://{HOST}:{port}{path}' + (f'?{query}' if query else '')

  headers = _clean_headers(request.headers)
  headers['host'] = f'{HOST}:{port}'
  # 뒤쪽 앱이 원래 경로를 알아야 할 때를 위해 남겨 둔다.
  headers['x-forwarded-prefix'] = f'/{name}'

  body = await request.body()

  req = client.build_request(
    request.method, url,
    headers=headers,
    content=body or None,
  )

  try:
    resp = await client.send(req, stream=True)
  except httpx.ConnectError:
    return Response(
      content=(f'{name} 서비스가 아직 뜨지 않았습니다. '
               f'시작 상태는 /api/service/{name} 에서 볼 수 있습니다.'),
      status_code=503, media_type='text/plain; charset=utf-8',
    )
  except httpx.RequestError as ex:
    logger.warning('[proxy] %s %s 실패: %r', request.method, url, ex)
    return Response(content=f'{name} 중계 실패: {ex}', status_code=502,
                    media_type='text/plain; charset=utf-8')

  ctype = resp.headers.get('content-type', '')
  out_headers = _clean_headers(resp.headers)

  if any(t in ctype for t in _STREAM_TYPES):
    async def relay():
      try:
        # aiter_raw() 가 아니라 aiter_bytes() 다.
        # 위에서 content-encoding 을 떼어 냈으므로 압축을 푼 바이트를 보내야 한다.
        # raw 를 그대로 흘리면 브라우저가 gzip 인 줄 모르고 깨진 글자를 받는다.
        async for chunk in resp.aiter_bytes():
          yield chunk
      finally:
        await resp.aclose()

    out = StreamingResponse(relay(), status_code=resp.status_code,
                            headers=_without_multi(out_headers), media_type=ctype)
    _apply_multi_headers(out, resp.headers, name)
    return out

  try:
    content = await resp.aread()
  finally:
    await resp.aclose()

  if 'text/html' in ctype:
    content = _rewrite_html(content, name)

  out = Response(content=content, status_code=resp.status_code,
                 headers=_without_multi(out_headers), media_type=ctype)
  _apply_multi_headers(out, resp.headers, name)
  return out


async def proxy_websocket(ws: WebSocket, name: str, path: str):
  """
  WebSocket 을 뒤쪽으로 잇는다. tools 의 socket.io 가 이걸 탄다.

  양방향이라 두 방향을 각각 돌려야 한다. 한쪽이 끊기면 다른 쪽도 닫는다.
  """

  import asyncio

  port = UPSTREAMS[name]['port']
  query = ws.url.query
  target = f'ws://{HOST}:{port}{path}' + (f'?{query}' if query else '')

  await ws.accept()

  try:
    upstream = await websockets.connect(target, open_timeout=10, max_size=None)
  except Exception as ex:
    logger.warning('[proxy] websocket %s 연결 실패: %r', target, ex)
    await ws.close(code=1011)
    return

  async def client_to_upstream():
    try:
      while True:
        msg = await ws.receive()
        if msg['type'] == 'websocket.disconnect':
          break
        if msg.get('text') is not None:
          await upstream.send(msg['text'])
        elif msg.get('bytes') is not None:
          await upstream.send(msg['bytes'])
    except (WebSocketDisconnect, RuntimeError):
      pass

  async def upstream_to_client():
    try:
      async for msg in upstream:
        if isinstance(msg, bytes):
          await ws.send_bytes(msg)
        else:
          await ws.send_text(msg)
    except Exception:
      pass

  a = asyncio.create_task(client_to_upstream())
  b = asyncio.create_task(upstream_to_client())
  done, pending = await asyncio.wait({a, b}, return_when=asyncio.FIRST_COMPLETED)

  for t in pending:
    t.cancel()
  await upstream.close()
  try:
    await ws.close()
  except RuntimeError:
    pass
