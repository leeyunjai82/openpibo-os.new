"""프록시 시험용 가짜 뒤쪽 서비스. tools 앱 흉내를 낸다."""
import asyncio, sys
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

app = FastAPI()
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 50000

@app.get('/', response_class=HTMLResponse)
async def root():
    # 실제 tools/templates/index.html 과 같은 상대 경로를 쓴다
    return '''<html><head><title>fake tools</title>
<link rel="stylesheet" href="../static/index.css?ver=1"/>
<script src="../static/index.js"></script>
</head><body>FAKE-TOOLS-BODY</body></html>'''

@app.get('/static/index.js')
async def js():
    return HTMLResponse(content="console.log('upstream js')", media_type='application/javascript')

@app.get('/control_cam')
async def control(d: str = 'on'):
    return JSONResponse({'cam': d, 'from': 'upstream'})

@app.get('/camera_stream')
async def stream():
    async def gen():
        for i in range(3):
            yield f'data: tick{i}\n\n'.encode()
            await asyncio.sleep(0.05)
    return StreamingResponse(gen(), media_type='text/event-stream')

@app.websocket('/socket.io/')
async def ws(websocket: WebSocket):
    await websocket.accept()
    while True:
        try:
            msg = await websocket.receive_text()
        except Exception:
            break
        await websocket.send_text(f'echo:{msg}')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=PORT, log_level='error')
