"""셸 + /api/system/* + 프록시를 **하드웨어 없이** 띄운다.

    bash test/ui/run.sh


run_ide.py 전체는 picamera2/dlib 을 끌어와 여기서 못 뜬다.
2단계에서 새로 만든 계층만 run_ide.py 와 같은 방식으로 얹어 확인한다.
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'ide'))

import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import proxy, services, system_api
system_api.SYSTEM_SH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fakedev/system.sh')
from openpibo.board import BOARD

BOARD_INFO = {
    'name': BOARD.name, 'label': BOARD.label,
    'features': dict(BOARD.features),
    'display': {'width': BOARD.display.width, 'height': BOARD.display.height},
    'camera': {'width': BOARD.camera.width, 'height': BOARD.camera.height},
}

# 학생 코드 실행 상태를 흉내낸다
STATE = {'running': False, 'record': '[26-08-27]: 안녕하세요\n실행 완료\n'}

@asynccontextmanager
async def lifespan(app):
    app.state.http = httpx.AsyncClient(timeout=None, follow_redirects=False)
    try: yield
    finally: await app.state.http.aclose()

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=os.path.join(ROOT, 'ide/templates'))
app.mount('/static', StaticFiles(directory=os.path.join(ROOT, 'ide/static')), name='static')

@app.get('/', response_class=HTMLResponse)
async def shell(request: Request):
    return templates.TemplateResponse(request, 'shell.html', {'board': BOARD_INFO})

@app.get('/app', response_class=HTMLResponse)
@app.get('/app/{tab:path}', response_class=HTMLResponse)
async def shell_tab(request: Request, tab: str = ''):
    return templates.TemplateResponse(request, 'shell.html', {'board': BOARD_INFO})

@app.get('/ide', response_class=HTMLResponse)
async def ide():
    return '<html><body>FAKE-IDE</body></html>'

system_api.register(app, services, proxy, system_api.Hooks(
    code_running=lambda: STATE['running'],
    record=lambda: STATE['record'],
    halt=lambda: None,
))

# run_ide.py 와 같은 서비스 라우트
from fastapi.responses import StreamingResponse

# run_ide.py 와 **같은 봉투**를 쓴다. 하니스가 날 dict 를 주면
# UI 시험이 실물과 다른 것을 검증하게 된다.
import envelope

@app.get('/api/service/{name}')
async def read_service(name: str):
    with envelope.Envelope('service.status') as e:
        if name not in proxy.UPSTREAMS:
            return e.fail(f'알 수 없는 서비스입니다: {name}', status=404)
        return e.ok(await services.status(name))

@app.post('/api/service/{name}/start')
async def start_service(name: str):
    with envelope.Envelope('service.start') as e:
        if name not in proxy.UPSTREAMS:
            return e.fail(f'알 수 없는 서비스입니다: {name}', status=404)
        return e.ok(await services.status(name), status=202)

@app.get('/api/service/{name}/events')
async def watch_service(name: str):
    if name not in proxy.UPSTREAMS:
        return JSONResponse({'error': name}, status_code=404)
    return StreamingResponse(services.watch(name, timeout=4), media_type='text/event-stream',
                             headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.post('/_test/running/{on}')
async def set_running(on: str):
    STATE['running'] = (on == 'on'); return JSONResponse({'running': STATE['running']})

@app.websocket('/{name}/{path:path}')
async def pws(websocket: WebSocket, name: str, path: str):
    if name not in proxy.UPSTREAMS: await websocket.close(code=1008); return
    await proxy.proxy_websocket(websocket, name, '/' + path)

@app.api_route('/{name}/{path:path}', methods=['GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'])
async def pany(request: Request, name: str, path: str):
    if name not in proxy.UPSTREAMS: return JSONResponse({'error':'no'}, status_code=404)
    return await proxy.proxy_http(request, name, '/' + path, app.state.http)

@app.get('/{name}')
async def proot(request: Request, name: str):
    if name not in proxy.UPSTREAMS: return JSONResponse({'error':'no'}, status_code=404)
    return RedirectResponse(url=f'/{name}/', status_code=307)

if __name__ == '__main__':
    import uvicorn; uvicorn.run(app, host='127.0.0.1', port=18080, log_level='error')
