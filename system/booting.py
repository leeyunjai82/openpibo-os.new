from openpibo.board import BOARD
from openpibo.oled import get_display
from openpibo.audio import Audio
from fastapi import FastAPI, Body, Request
from fastapi.responses import JSONResponse,HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from threading import Timer
from collections import Counter
import json,time,os,shutil
import wifi
import network_disp
import uart_ctrl
import argparse

SYSTEM_DIR = os.path.dirname(os.path.abspath(__file__))

# 파이보에만 MCU(ATmega328P)가 있다. 파이브레인에서는 import 자체를 하지 않는다.
# mcu_control 은 /dev/ttyS0 을 여는데 파이브레인에는 그 장치가 없다.
device_control = None
if BOARD.features.has_mcu:
  from mcu_control import DeviceControl

@asynccontextmanager
async def lifespan(app: FastAPI):
  global winfo, ole, aud, device_control
  ole = get_display()
  aud = Audio()

  if BOARD.features.has_mcu:
    device_control = DeviceControl()
    device_control.send_raw("#20:150,150,150!")   # 부팅 중 — 눈 LED 켜기

  winfo = ['','','','','','']
  uart_ctrl.start()
  boot()

  if BOARD.features.has_mcu:
    device_control.send_raw("#20:0,0,0!")         # 부팅 끝 — 눈 LED 끄기

  yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
apmode = False

templates = Jinja2Templates(directory="/home/pi/openpibo-os/docs")
app.mount("/build", StaticFiles(directory="/home/pi/openpibo-os/docs/build"), name="build")

@app.get('/', response_class=HTMLResponse)
async def read_root(request: Request):
  return templates.TemplateResponse("index.html", {"request": request})

@app.get("/device/{pkt}")
async def device_command(pkt: str):
  # 시리얼 프록시. run_ide.py 가 /dev/ttyS0 을 직접 열지 않고 여기로 우회한다.
  if not BOARD.features.has_mcu:
    return JSONResponse(
      content=f'"{BOARD.label}"({BOARD.name}) 에는 MCU 가 없습니다.',
      status_code=501,
    )
  try:
    if pkt == "#15:!":
      return JSONResponse(content=device_control.system_data.get('battery', ''), status_code=200)
    elif pkt == "#40:!":
      return JSONResponse(content=device_control.system_data.get('system', ''), status_code=200)
    else:
      response = device_control.send_raw(pkt)
      return JSONResponse(content=response, status_code=200)
  except Exception as ex:
    return JSONResponse(content=f"Error: {str(ex)}", status_code=500)

@app.get('/wifi_scan')
async def f():
  return JSONResponse(content=wifi.wifi_scan(), status_code=200)

@app.get('/wifi')
async def f():
  return JSONResponse(content={'result':'ok', 'ssid':winfo[2], 'psk':winfo[3], 'ipaddress':winfo[0], 'eth1': winfo[1], 'identity':winfo[4], 'key-mgmt':winfo[5]}, status_code=200)

@app.post('/wifi')
async def f(data: dict = Body(...)):
  print(data)
  if data['ssid'] == "": # error
    return JSONResponse(content=f"Error: {str(ex)}", status_code=500)
  elif data['psk'] == "": # open
    os.system(f"sudo {SYSTEM_DIR}/conwifi.sh open '{data['ssid']}'")
  elif data['psk'] != "": # wpa or wpa-e
    if len(data['psk']) < 8:
      return JSONResponse(content={'result':'fail', 'data':'psk must be at least 8 digits.'}, status_code=200)
    elif data['identity'] == "": # wpa
      os.system(f"sudo {SYSTEM_DIR}/conwifi.sh wpa-psk '{data['ssid']}' '{data['psk']}'")
    else: #wpa-e
      os.system(f"sudo {SYSTEM_DIR}/conwifi.sh wpa-enterprise '{data['ssid']}' '{data['identity']}' '{data['psk']}'")
  else:
    return JSONResponse(content=f"Error: {str(ex)}", status_code=500)
  os.system('shutdown -r now &') 
  return JSONResponse(content="ok", status_code=200)

def wifi_update():
  global winfo, apmode
  tmp = os.popen(f'{SYSTEM_DIR}/system.sh').read().strip('\n').split(',')
  if (tmp[6] != '' and tmp[6][0:3] != '169') or (tmp[7] != '' and tmp[7][0:3] != '169'):
    if apmode == True:
      #os.system("sudo ip link set ap0 down")
      os.system(f"{SYSTEM_DIR}/hotspot.sh stop")
      print(f'ap0 up->down')
    apmode = False
  else:
    if apmode == False:
      #os.system("sudo ip link set ap0 up")
      os.system(f"{SYSTEM_DIR}/hotspot.sh start")
      print(f'ap0 down->up')
    apmode = True
  if winfo != tmp[6:12]:
    print(f'Network Change {winfo} -> {tmp[6:12]}')
    network_disp.run()
  winfo = tmp[6:12]
  _ = Timer(10, wifi_update)
  _.daemon = True
  _.start()

## boot
def boot():
  try:
    with open('/home/pi/.OS_VERSION', 'r') as f:
      os_version = str(f.readlines()[0].split('\n')[0])
  except Exception as ex:
    os_version = "OS (None)"
    pass

  try:
    with open('/home/pi/config.json', 'r') as f:
      tmp = json.load(f)
  except Exception as ex:
    pass

  aud.play(f"{SYSTEM_DIR}/opening.mp3", 70)
  ole.clear()
  # 스플래시는 화면 크기가 달라 보드마다 다른 파일이다.
  # 파이브레인 스플래시는 240x320 을 꽉 채워서 버전 글자를 겹쳐 쓰지 않는다.
  ole.draw_image(f"{SYSTEM_DIR}/{BOARD.boot.splash}")
  if BOARD.boot.show_version:
    ole.draw_text((5,0), os_version)
  ole.show()
  time.sleep(5)
  for i in range(1,10):
    tmp = os.popen(f'{SYSTEM_DIR}/system.sh').read().strip('\n').split(',')
    if (tmp[6] != '' and tmp[6][0:3] != '169') or (tmp[7] != '' and tmp[7][0:3] != '169'):
      #os.system("/home/pi/openpibo-os/system/hotspot.sh stop")
      break
    ole.draw_text((5,5), BOARD.boot.progress_sep.join(["" for _ in range(i+1)]))
    ole.show()
    time.sleep(3)
  network_disp.run()
  _ = Timer(10, wifi_update)
  _.daemon = True
  _.start()

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--port', help='set port number', default=8080)
  args = parser.parse_args()

  import uvicorn
  uvicorn.run('booting:app', host='0.0.0.0', port=args.port, access_log=False)
