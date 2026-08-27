import os
import sys
import asyncio
import shutil
import base64
import datetime
import subprocess
import requests
from pathlib import Path
from typing import List, Union

from fastapi import FastAPI, Request, UploadFile, File, Form, Body, Depends, WebSocket
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi_socketio import SocketManager
from starlette.websockets import WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

import httpx

from openpibo.board import BOARD

import proxy
import services
import system_api

@asynccontextmanager
async def lifespan(app: FastAPI):
  asyncio.create_task(periodic_system_update())
  # 중계용 클라이언트 한 벌을 오래 들고 쓴다. 요청마다 새로 만들면
  # 연결을 매번 새로 여느라 전환이 더 느려진다.
  # timeout=None: SSE 와 MJPEG 는 원래 안 끊기는 응답이다.
  app.state.http = httpx.AsyncClient(timeout=None, follow_redirects=False)
  try:
    yield
  finally:
    await app.state.http.aclose()

try:
  app = FastAPI(lifespan=lifespan)
  socket_manager = SocketManager(app=app, mount_location='/socket.io')
  templates = Jinja2Templates(directory="templates")

  app.mount("/static", StaticFiles(directory="static"), name="static")
  app.mount("/svg", StaticFiles(directory="svg"), name="svg")
  app.mount("/webfonts", StaticFiles(directory="webfonts"), name="webfonts")
except Exception as ex:
  print(f'Server error{ex}')

# CORS 미들웨어를 뺀다.
#
# 1) 뒤쪽 서비스가 전부 /tools /classify /llm 로 같은 origin 아래 들어왔다.
#    교차 출처 요청 자체가 없어졌다.
# 2) 원래 설정이 스펙상 무효였다 — allow_origins=["*"] 와 allow_credentials=True 는
#    같이 못 쓴다. 브라우저가 거부한다. 즉 지금까지도 실제로 동작하지 않았다.
#    (docs/plan/04-known-issues.md 8)

codeExec = {
  'python': 'python3',
  'shell': 'sh',
}

# 프론트로 넘길 보드 정보. openpibo/profiles/<board>.toml 이 원본이다.
# board_filter.js 가 features 를 보고 툴박스에서 없는 블록을 걷어낸다.
# 서버가 주는 것만 프론트가 안다 — 브라우저가 보드를 짐작하게 두지 않는다.
BOARD_INFO = {
  'name': BOARD.name,
  'label': BOARD.label,
  'features': dict(BOARD.features),
  'display': {'width': BOARD.display.width, 'height': BOARD.display.height},
  'camera': {'width': BOARD.camera.width, 'height': BOARD.camera.height},
}

def servo_init():
  """서보(다리) 초기화. 다리가 없는 보드에는 servo 데몬 자체가 없다."""

  if BOARD.features.has_legs:
    subprocess.Popen(['servo', 'init'])


def mcu_halt():
  """
  MCU 에 전원 차단을 알린다. MCU 가 없는 보드에서는 할 일이 없다.

  .. note::
     /dev/ttyS0 에 직접 쓴다. 평소 device 명령은 booting.py 의 시리얼 프록시
     (127.0.0.1:8080/device/...)를 거치는데, 여기만 직접 쓴다.
     종료 직전이라 프록시가 이미 내려갔을 수 있어서다. 원래 동작 그대로 뒀다.
  """

  if BOARD.features.has_mcu:
    os.system('echo "#11:!" > /dev/ttyS0')


protectList = [
  '/home/pi/openpibo-',
  '/home/pi/node_modules',
  '/home/pi/package.json',
  '/home/pi/package-lock.json',
  '/home/pi/config.json',
]

ENV_PATH = '/home/pi/.pyenv/bin'
record = ''
ps = None
PATH = '/home/pi/code'
codeText = ''
codePath = ''

mutex = asyncio.Lock()

def is_protect(p):
  # 문자열 in 매칭이라 ../ 가 정규화되지 않아
  # /home/pi/code/../openpibo-os/... 같은 경로가 통과했다.
  # (docs/plan/04-known-issues.md 6)
  real = os.path.realpath(p)
  for protected_path in protectList:
    prot = os.path.realpath(protected_path)
    if real == prot:
      return True
    try:
      if os.path.commonpath([real, prot]) == prot:
        return True
    except ValueError:      # 드라이브가 다르면(윈도우) 비교 불가
      pass
    # protectList 에는 '/home/pi/openpibo-' 처럼 접두사로 쓰는 항목이 있다.
    if real.startswith(protected_path):
      return True
  return False

def read_directory(d):
  dlst = []
  flst = []
  try:
    for p in os.scandir(d):
      if p.is_dir(follow_symlinks=False) or p.is_symlink():
        dlst.append({
          'name': p.name,
          'type': 'folder',
          'protect': is_protect(f"{d}/{p.name}")
        })
      else:
        flst.append({
          'name': p.name,
          'type': 'file',
          'protect': is_protect(d) or is_protect(f"{d}/{p.name}")
        })
  except Exception as err:
    print(err)
    return False
  return sorted(dlst, key=lambda x:x['name'])  + sorted(flst, key=lambda x:x['name'])


def file_extension_check(filename):
  return filename.split('.')[-1].lower()


@app.get('/dir')
async def get_directory(folderName: str):
  files = []
  try:
    for p in os.scandir(folderName):
      if not p.is_dir() and not p.is_symlink() and not p.name.startswith('.'):
        files.append(p.name)
  except Exception as err:
    files = []
  return files


# ── SPA shell ────────────────────────────────────────────────
#
# 상단바 + 탭 + 설정 모달을 셸이 들고, 각 화면은 iframe 으로 붙는다.
# 1단계에서 뒤쪽 서비스가 전부 같은 origin 으로 들어와서 가능해진 구조다.
#
# /app/<탭> 을 전부 셸로 돌려준다. 클라이언트 라우팅이지만 주소가 진짜로 남아서
# 새로고침해도 그 탭이 열리고 뒤로가기가 탭 사이를 오간다.

@app.get('/', response_class=HTMLResponse)
async def read_shell(request: Request):
  return templates.TemplateResponse(request, "shell.html", {"board": BOARD_INFO})


@app.get('/app', response_class=HTMLResponse)
@app.get('/app/{tab:path}', response_class=HTMLResponse)
async def read_shell_tab(request: Request, tab: str = ''):
  return templates.TemplateResponse(request, "shell.html", {"board": BOARD_INFO})


@app.get('/landing', response_class=HTMLResponse)
async def read_landing(request: Request):
  """
  예전 랜딩 화면. 셸이 기기에서 확인될 때까지 남겨 둔다.

  현장 기기가 있는 상태에서 진입점을 한 번에 갈아치우면, 셸에 문제가 있을 때
  돌아갈 곳이 없다. 2단계가 실기에서 확인되면 지운다.
  """

  return templates.TemplateResponse(request, "landing.html", {"board": BOARD_INFO})

# ── IDE ───────────────────────────────────────────────────────
@app.get('/ide', response_class=HTMLResponse)
async def read_ide(request: Request):
  return templates.TemplateResponse(request, "index.html", {"board": BOARD_INFO})


@app.get('/api/board')
async def read_board():
  """이 기기가 어느 보드인지. 프론트/도구/시험 스크립트 공용."""
  return JSONResponse(content=BOARD_INFO, status_code=200)


@app.get("/download")
async def download_item(filename: str):
  full_path = os.path.join(PATH, filename)

  if is_protect(full_path):
    await socket_manager.emit('update', {'dialog': '파일 다운로드 오류: 보호 디렉토리입니다.'})
    return JSONResponse(content={'error': '파일 다운로드 오류: 보호 디렉토리입니다.'}, status_code=403)

  if not os.path.exists(full_path):
    # JSONResponse 는 Exception 이 아니다. raise 하면 TypeError 가 나서
    # 404 대신 500 이 떨어진다. (docs/plan/04-known-issues.md 1)
    return JSONResponse(content={'error':"파일 또는 폴더를 찾을 수 없습니다."}, status_code=404)

  if os.path.isfile(full_path):
    return FileResponse(full_path, filename=filename)

  elif os.path.isdir(full_path):
    zip_path = "/tmp/download.zip"
    if os.path.exists(zip_path):
      os.remove(zip_path)
    base_name = "/tmp/download"
    shutil.make_archive(base_name, 'zip', root_dir=full_path)
    return FileResponse(zip_path, media_type="application/zip", filename="download.zip")

  else:
    return JSONResponse(content={'error':"올바른 파일 또는 폴더가 아닙니다."}, status_code=403)

@app.post('/upload')
async def upload_file(files: List[UploadFile] = File(...)):
  if is_protect(PATH):
    await socket_manager.emit('update', {'dialog': '파일 업로드 오류: 보호 디렉토리입니다.'})
    return JSONResponse(content={'error': '파일 업로드 오류: 보호 디렉토리입니다.'}, status_code=403)
  for file in files:
    file_location = os.path.join(PATH, file.filename)
    with open(file_location, "wb") as f:
      content = await file.read()
      f.write(content)
  directory_data = read_directory(PATH)
  await socket_manager.emit('update_file_manager', {'data': directory_data})
  try:
    shutil.chown(PATH, user='pi', group='pi')
  except Exception as err:
    print(err)
  return JSONResponse(content={"message": "파일 업로드 완료"}, status_code=200)


@app.post('/show')
async def show_file(data: UploadFile = File(...)):
  try:
    tmp_path = '/home/pi/.tmp.jpg'
    with open(tmp_path, 'wb') as f:
      content = await data.read()
      f.write(content)
    with open(tmp_path, 'rb') as f:
      image_data = f.read()
      encoded_image = base64.b64encode(image_data).decode('utf-8')
      await socket_manager.emit('update', {'image': encoded_image, 'filepath': tmp_path})
  except Exception as err:
    print(err)
    await socket_manager.emit('update', {'dialog': f'보기 오류: {str(err)}'})
  return JSONResponse(content={"message": "이미지 표시 완료"}, status_code=200)

@app.sio.on('connection')
async def handle_connection(sid, *args, **kwargs):
  pass  # Placeholder for any connection initialization

@app.sio.on('init')
async def handle_init(sid):
  global codeText, codePath
  try:
    system_info = subprocess.check_output(['/home/pi/openpibo-os/system/system.sh']).decode().strip().split(',')
    await app.sio.emit('system', system_info)
  except Exception as err:
    print(err)
    await app.sio.emit('update', {'dialog': '초기화: 시스템 파일 오류입니다.'})

  try:
    with open(codePath, 'r') as f:
      codeText = f.read()
  except Exception as err:
    codeText = ''
  await app.sio.emit('init', {'codepath': codePath, 'codetext': codeText, 'path': PATH})

# ── 뒤쪽 서비스 제어 ──────────────────────────────────────────
#
# 예전 /tools?enable=on, /classifier?enable=on, /llm?enable=on 을 그대로 둔다.
# 기존 화면과 학생 코드가 이 주소를 쓰고 있다. 다만 안에서 하는 일이 달라졌다:
# 배타 서비스 정리를 services.start() 가 맡고, **여기서 기다리지 않는다.**
# 언제 다 떴는지는 /api/service/{name}/events 가 알려준다.

def _toggle(name, enable):
  # enable 이 없으면 켜고 끄라는 게 아니라 그 서비스 화면으로 가겠다는 뜻이다.
  # /tools 와 /llm 은 토글 주소이면서 동시에 프록시 앞머리라, 이 구분이 필요하다.
  # (이 라우트가 아래 catch-all 보다 먼저 등록되므로 여기서 갈라야 한다)
  if enable is None:
    return RedirectResponse(url=f'/{name}/', status_code=307)
  if enable == 'on':
    services.start(name)
  elif enable == 'off':
    services.stop(name)
  return HTMLResponse(content='', status_code=200)


@app.get('/tools')
async def toggle_tools(enable: str = None):
  return _toggle('tools', enable)


@app.get('/classifier')
async def toggle_classifier(enable: str = None):
  # 앞머리는 /classify 인데 토글 주소는 /classifier 다. 기존 화면과 학생 코드가
  # 이 주소를 쓰고 있어 그대로 둔다. 겹치지 않으므로 문제되지 않는다.
  return _toggle('classify', enable)


@app.get('/llm')
async def toggle_llm(enable: str = None):
  return _toggle('llm', enable)


@app.get('/api/service')
async def list_services():
  """뒤쪽 서비스 셋의 현재 상태."""

  return JSONResponse(content={
    n: await services.status(n) for n in proxy.UPSTREAMS
  }, status_code=200)


@app.get('/api/service/{name}')
async def read_service(name: str):
  if name not in proxy.UPSTREAMS:
    return JSONResponse(content={'error': f'알 수 없는 서비스: {name}'}, status_code=404)
  return JSONResponse(content=await services.status(name), status_code=200)


@app.post('/api/service/{name}/start')
async def start_service(name: str):
  """
  켜기만 하고 바로 돌아온다. 뜰 때까지 기다리는 것은 /events 가 한다.

  이렇게 나눈 이유: 요청 하나를 수십 초 붙잡고 있으면 그 사이 화면이
  아무것도 못 한다. 진행 상태를 보여줄 수가 없다.
  """

  if name not in proxy.UPSTREAMS:
    return JSONResponse(content={'error': f'알 수 없는 서비스: {name}'}, status_code=404)
  services.start(name)
  return JSONResponse(content=await services.status(name), status_code=202)


@app.post('/api/service/{name}/stop')
async def stop_service(name: str):
  if name not in proxy.UPSTREAMS:
    return JSONResponse(content={'error': f'알 수 없는 서비스: {name}'}, status_code=404)
  services.stop(name)
  return JSONResponse(content={'name': name, 'stopped': True}, status_code=200)


@app.get('/api/service/{name}/events')
async def watch_service(name: str):
  """
  뜰 때까지의 진행 상태를 SSE 로 흘려보낸다.

    starting -> active(유닛이 떴다) -> ready(포트가 응답한다)

  `systemctl is-active` 는 uvicorn 이 포트를 잡기 전에 이미 active 를 준다.
  그래서 active 와 ready 를 나눠 본다. 화면은 ready 에서 넘어간다.
  """

  if name not in proxy.UPSTREAMS:
    return JSONResponse(content={'error': f'알 수 없는 서비스: {name}'}, status_code=404)

  return StreamingResponse(
    services.watch(name),
    media_type='text/event-stream',
    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
  )


@app.sio.on('init_lcd')
async def handle_init_lcd(sid):
  subprocess.Popen([f'{ENV_PATH}/python3', '/home/pi/openpibo-os/system/network_disp.py'])


@app.sio.on('reset_log')
async def handle_reset_log(sid):
  global record
  record = f'[{datetime.datetime.now()}]: \n\n'
  subprocess.Popen([f'{ENV_PATH}/python3', '/home/pi/openpibo-os/system/network_disp.py'])
  servo_init()


@app.sio.on('poweroff')
async def handle_poweroff(sid):
  mcu_halt()
  subprocess.Popen(['shutdown', '-h', 'now'])

@app.sio.on('restart')
async def handle_restart(sid):
  subprocess.Popen(['shutdown', '-r', 'now'])


@app.sio.on('load_directory')
async def handle_load_directory(sid, p):
  global PATH
  res = read_directory(p)
  if res is not False:
    PATH = p
  else:
    res = read_directory(PATH)
  await app.sio.emit('update_file_manager', {'data': res, 'path': PATH})

@app.sio.on('view')
async def handle_view(sid, p):
  try:
    with open(p, 'rb') as f:
      data = f.read()
      encoded_image = base64.b64encode(data).decode('utf-8')
      await app.sio.emit('update', {'image': encoded_image, 'filepath': p})
  except Exception as err:
    await app.sio.emit('update', {'dialog': f'보기 오류: {str(err)}'})


@app.sio.on('play')
async def handle_play(sid, p):
  try:
    with open(p, 'rb') as f:
      data = f.read()
      encoded_audio = base64.b64encode(data).decode('utf-8')
      await app.sio.emit('update', {'audio': encoded_audio, 'filepath': p})
  except Exception as err:
    await app.sio.emit('update', {'dialog': f'재생 오류: {str(err)}'})


@app.sio.on('load')
async def handle_load(sid, p):
  global codeText, codePath
  if is_protect(p) :
    await app.sio.emit('update', {'dialog': '파일 불러오기 오류: 보호 파일입니다.'})
    return
  try:
    with open(p, 'r') as f:
      codeText = f.read()
      codePath = p
      await app.sio.emit('update', {'code': codeText, 'filepath': codePath})
  except Exception as err:
    await app.sio.emit('update', {'dialog': f'파일 불러오기 오류: {str(err)}'})


@app.sio.on('delete')
async def handle_delete(sid, d):
  global codeText, codePath
  if is_protect(d):
    await app.sio.emit('update', {'dialog': '파일 삭제 오류: 보호 파일입니다.'})
    return
  if d == codePath:
    codePath = ""
    codeText = ""
  try:
    if os.path.isdir(d):
      shutil.rmtree(d)
    else:
      os.remove(d)
  except Exception as err:
    print(err)
    await app.sio.emit('update', {'dialog': '파일 삭제 오류: 파일명 파싱 에러입니다.'})
    return
  directory_data = read_directory(PATH)
  await app.sio.emit('update_file_manager', {'data': directory_data})


@app.sio.on('rename')
async def handle_rename(sid, d):
  global codeText, codePath
  oldpath = d['oldpath']
  newpath = d['newpath']
  if is_protect(oldpath) or is_protect(newpath):
    await app.sio.emit('update', {'dialog': '파일 이름 변경 오류: 보호 파일입니다.'})
    return
  try:
    os.rename(oldpath, newpath)
  except Exception as err:
    await app.sio.emit('update', {'dialog': '파일 이름 변경 오류: 파일명 파싱 에러입니다.'})
    return
  directory_data = read_directory(PATH)
  await app.sio.emit('update_file_manager', {'data': directory_data})
  if oldpath == codePath:
    try:
      with open(newpath, 'r') as f:
        codeText = f.read()
        codePath = newpath
        await app.sio.emit('update', {'code': codeText, 'filepath': codePath})
    except Exception as err:
      await app.sio.emit('update', {'dialog': f'파일 불러오기 오류: {str(err)}'})

@app.sio.on('restore')
async def handle_restore(sid):
    try:
        os.system("rm -rf /home/pi/code/*")
        os.system("rm -rf /home/pi/myimage/*")
        os.system("rm -rf /home/pi/mymodel/*")
        os.system("rm -rf /home/pi/myaudio/*")
        # 예제는 보드별로 나뉘어 있다 (examples/pibo, examples/pibrain).
        # examples/* 를 그대로 복사하면 폴더 두 개가 통째로 들어간다.
        os.makedirs('/home/pi/examples', exist_ok=True)
        os.system("rm -rf /home/pi/examples/*")
        os.system(f"cp -rf /home/pi/openpibo-os/examples/{BOARD.name}/* /home/pi/examples/")
        os.system("sudo /home/pi/openpibo-os/system/conwifi.sh wpa-psk 'pibo' '!pibo0314'")
        mcu_halt()
        subprocess.Popen(['shutdown', '-h', 'now'])
    except Exception as e:
        # sio 는 정의되지 않은 이름이었다. 초기화가 실패하면 에러 메시지 대신
        # NameError 가 나서 화면에 아무것도 안 뜬다. (docs/plan/04-known-issues.md 2)
        await app.sio.emit('update', {'dialog': f'초기화 오류: {str(e)}'}, room=sid)

@app.sio.on('add_file')
async def handle_add_file(sid, p):
  global codeText, codePath
  if is_protect(PATH):
    await app.sio.emit('update', {'dialog': '파일 생성 오류: 보호 디렉토리입니다.'})
    return
  if not os.path.exists(p):
    try:
      os.makedirs(os.path.dirname(p), exist_ok=True)
      open(p, 'a').close()
      shutil.chown(os.path.dirname(p), user='pi', group='pi')
      directory_data = read_directory(PATH)
      await app.sio.emit('update_file_manager', {'data': directory_data})
    except Exception as err:
      await app.sio.emit('update', {'dialog': f'파일 생성 오류: {str(err)}'})
      return
  codePath = p
  try:
    with open(p, 'r') as f:
      codeText = f.read()
      await app.sio.emit('update', {'code': codeText, 'filepath': p})
  except Exception as err:
    await app.sio.emit('update', {'dialog': f'파일 불러오기 오류: {str(err)}'})

@app.sio.on('add_directory')
async def handle_add_directory(sid, p):
  if is_protect(PATH):
    await app.sio.emit('update', {'dialog': '디렉토리 생성 오류: 보호 폴더입니다.'})
    return
  try:
    os.makedirs(p, exist_ok=True)
    shutil.chown(p, user='pi', group='pi')
    directory_data = read_directory(PATH)
    await app.sio.emit('update_file_manager', {'data': directory_data})
  except Exception as err:
    await app.sio.emit('update', {'dialog': f'디렉토리 생성 오류: {str(err)}'})

@app.sio.on('save')
async def handle_save(sid, d):
  global codeText, codePath
  try:
    if is_protect(d['codepath']) or is_protect(os.path.dirname(d['codepath'])):
      await app.sio.emit('update', {'dialog': '파일 저장 오류: 보호 파일입니다.'})
      return
    codeText = d['codetext']
    codePath = d['codepath']
    os.makedirs(os.path.dirname(codePath), exist_ok=True)
    with open(codePath, 'w') as f:
      f.write(codeText)
    shutil.chown(os.path.dirname(codePath), user='pi', group='pi')
  except Exception as err:
    await app.sio.emit('update', {'dialog': f'파일 저장 오류: {str(err)}'})

async def execute(EXEC, codepath):
  global record, ps
  async with mutex:
    record = f'[{datetime.datetime.now()}]: \n\n'
    await app.sio.emit('update', {'record': record})
    if EXEC == 'python3':
      ps = await asyncio.create_subprocess_exec(
        f"{ENV_PATH}/{EXEC}", '-u', codepath,
        cwd=PATH,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE
      )
    else:
      ps = await asyncio.create_subprocess_exec(
        EXEC, codepath,
        cwd=PATH,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE
      )
    while True:
      line = await ps.stdout.readline()
      if not line:
        break
      record += line.decode()
      await app.sio.emit('update', {'record': record})

    err = await ps.stderr.read()
    if err:
      record += f'\n{err.decode()}'
      await app.sio.emit('update', {'record': record})

    await ps.wait()
    ps = None  # 프로세스가 종료되었으므로 ps를 None으로 설정
    record += "\n종료됨."
    await app.sio.emit('update', {'record': record, 'exit': True})
    directory_data = read_directory(PATH)
    await app.sio.emit('update_file_manager', {'data': directory_data})

@app.sio.on('execute')
async def handle_execute(sid, d):
  global codeText, codePath, ps
  subprocess.Popen(['systemctl', 'stop', 'tools.service'])
  subprocess.Popen(['systemctl', 'stop', 'classify.service'])
  subprocess.Popen(['systemctl', 'stop', 'llama-server.service'])
  try:
    if is_protect(d['codepath']) or is_protect(os.path.dirname(d['codepath'])):
      await app.sio.emit('update', {'dialog': '실행 오류: 보호 파일입니다.', 'exit': True})
      return
    codeText = d['codetext']
    codePath = d['codepath']
    if ps and ps.returncode is None:
      ps.kill()
      await ps.wait()
    os.makedirs(os.path.dirname(codePath), exist_ok=True)
    with open(codePath, 'w') as f:
      f.write(codeText)
    shutil.chown(os.path.dirname(codePath), user='pi', group='pi')
    await execute(codeExec[d["codetype"]], codePath)
  except Exception as err:
    await app.sio.emit('update', {'dialog': f'실행 오류: {str(err)}', 'exit': True})

@app.sio.on('executeb')
async def handle_executeb(sid, d):
  global ps
  subprocess.Popen(['systemctl', 'stop', 'tools.service'])
  subprocess.Popen(['systemctl', 'stop', 'classify.service'])
  subprocess.Popen(['systemctl', 'stop', 'llama-server.service'])
  try:
    if ps and ps.returncode is None:
      ps.kill()
      await ps.wait()
    os.makedirs(os.path.dirname(d['codepath']), exist_ok=True)
    with open(d['codepath'], 'w') as f:
      f.write(d['codetext'])
    shutil.chown(os.path.dirname(d['codepath']), user='pi', group='pi')
    await execute(codeExec[d["codetype"]], d['codepath'])
  except Exception as err:
    await app.sio.emit('update', {'dialog': f'실행 오류: {str(err)}', 'exit': True})

# stop 핸들러 수정
@app.sio.on('stop')
async def handle_stop(sid):
  global ps
  subprocess.Popen(['pkill', 'play'])
  subprocess.Popen(['pkill', 'llama-server'])
  servo_init()
  if ps and ps.returncode is None:
    ps.kill()
    await ps.wait()

@app.sio.on('prompt')
async def handle_prompt(sid, s):
  global ps
  if ps and ps.stdin:
    ps.stdin.write((s + "\n").encode())
    await ps.stdin.drain()

# Additional code for the periodic system status updates
async def periodic_system_update():
  while True:
    try:
      system_info = subprocess.check_output(['/home/pi/openpibo-os/system/system.sh']).decode().strip().split(',')
      await app.sio.emit('system', system_info)
    except Exception as err:
      await app.sio.emit('update', {'dialog': '초기화: 시스템 파일 오류입니다.'})

    # 배터리와 충전 감지는 MCU 경유다. MCU 가 없는 보드에는 배터리 자체가 없다.
    # 없는 것을 0% 로 보여주면 "다 됐다"로 읽힌다. 아예 보내지 않고,
    # 프론트가 __BOARD__ 를 보고 배지를 숨긴다.
    if BOARD.features.has_mcu:
      try:
        await app.sio.emit('update_battery', requests.get('http://127.0.0.1:8080/device/%2315%3A%21').json().split(':')[1])
      except Exception as err:
        await app.sio.emit('update_battery', '0%')

      try:
        await app.sio.emit('update_dc', requests.get('http://127.0.0.1:8080/device/%2314%3A%21').json().split(':')[1])
      except Exception as err:
        await app.sio.emit('update_dc', 'off')

    await asyncio.sleep(10)

#@app.on_event('startup')
#async def on_startup():
#  asyncio.create_task(periodic_system_update())


# ── /api/system/* ────────────────────────────────────────────
#
# 설정 모달이 쓰는 것들. 지금까지 socket.io 이벤트와 다른 origin 호출(:8080)로
# 흩어져 있었다. 설정은 어느 탭에서든 열려야 하는데(00-decisions.md 5.2),
# 그러려면 셸이 socket.io 를 또 붙이거나 교차 출처로 나가야 했다. 둘 다 안 한다.
# 전부 같은 origin 의 REST 로 모으고 봉투를 씌운다.
#
# 와이파이는 booting.py(:8080)가 들고 있어 system_api 가 중계한다 —
# **마지막 남은 교차 출처 호출이 여기서 사라진다.**

system_api.register(
  app, services, proxy,
  system_api.Hooks(
    code_running=lambda: ps is not None and ps.returncode is None,
    record=lambda: record,
    halt=mcu_halt,
  ),
)


# ── 리버스 프록시 ─────────────────────────────────────────────
#
# **반드시 파일 맨 아래에 둔다.** FastAPI 는 등록 순서로 라우트를 찾는다.
# 이 catch-all 이 위에 있으면 /tools?enable=on 같은 허브 자기 라우트를 삼킨다.
#
#   /tools/*     -> 127.0.0.1:50000
#   /classify/*  -> 127.0.0.1:50010
#   /llm/*       -> 127.0.0.1:50020
#
# 뒤쪽 앱을 하나도 안 고치고 origin 만 합치는 것이 목적이다.
# 자산 경로 보정과 window.__BASE__ 주입은 proxy.py 가 한다.

@app.websocket('/{name}/{path:path}')
async def proxy_ws(websocket: WebSocket, name: str, path: str):
  """tools 의 socket.io 가 여기를 탄다."""

  if name not in proxy.UPSTREAMS:
    await websocket.close(code=1008)
    return
  await proxy.proxy_websocket(websocket, name, '/' + path)


@app.api_route('/{name}/{path:path}',
               methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'])
async def proxy_any(request: Request, name: str, path: str):
  if name not in proxy.UPSTREAMS:
    return JSONResponse(content={'error': '없는 경로입니다.'}, status_code=404)
  return await proxy.proxy_http(request, name, '/' + path, app.state.http)


@app.get('/{name}')
async def proxy_root(request: Request, name: str):
  """
  /tools -> /tools/ 로 넘긴다.

  끝의 슬래시가 없으면 브라우저가 상대 경로를 루트 기준으로 풀어서
  자산을 전부 놓친다.
  """

  if name not in proxy.UPSTREAMS:
    return JSONResponse(content={'error': '없는 경로입니다.'}, status_code=404)
  return RedirectResponse(url=f'/{name}/', status_code=307)


if __name__ == '__main__':
  import argparse
  import uvicorn

  parser = argparse.ArgumentParser()
  parser.add_argument('--port', help='set port number', default=80)
  args = parser.parse_args()

  uvicorn.run('run_ide:app', host='0.0.0.0', port=int(args.port), access_log=False)
