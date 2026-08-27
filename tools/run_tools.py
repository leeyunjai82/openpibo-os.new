from fastapi_socketio import SocketManager
from fastapi import FastAPI,Request,UploadFile,File,Body
from fastapi.responses import HTMLResponse,FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import time,os,json,shutil,logging
from urllib import parse
import argparse
from threading import Timer

pibo = None

def init_pibo():
  global pibo
  from lib import Pibo
  pibo = Pibo(emit)
  os.system('/home/pi/.pyenv/bin/python3 /home/pi/openpibo-os/system/network_disp.py')

@asynccontextmanager
async def lifespan(app: FastAPI):
  logging.basicConfig(level=logging.ERROR, format='%(asctime)s [%(levelname)s] %(message)s')
  t = Timer(0, init_pibo)
  t.daemon = True
  t.start()
  yield

try:
  app = FastAPI(lifespan=lifespan)
  app.mount("/static", StaticFiles(directory="static"), name="static")
  app.mount("/webfonts", StaticFiles(directory="webfonts"), name="webfonts")
  app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
  templates = Jinja2Templates(directory="templates")
  socketio = SocketManager(app=app, cors_allowed_origins=[], mount_location="/socket.io", socketio_path="")
except Exception as ex:
  logging.error(f'Server Error:{ex}')

# REST API
@app.get('/', response_class=HTMLResponse)
async def f(request:Request):
  #await emit('onoff', False if pibo is None else True)
  return templates.TemplateResponse("index.html", {"request": request})

@app.post('/import_motion')
async def import_motion(data:UploadFile = File(...)):
  data.filename = "custom_motion.json"

  with open(f"/home/pi/{data.filename}", 'wb') as f:
    content = await data.read()
    f.write(content)

  try:
    with open(f'/home/pi/{data.filename}', 'rb') as f:
      content = json.load(f)
  except Exception as ex:
    logging.error(f'[import_motion] Error: {ex}')
    pass

  pibo.motion_j.update(content)
  with open('/home/pi/mymotion.json', 'w') as f:
    json.dump(pibo.motion_j, f)
  shutil.chown('/home/pi/mymotion.json', 'pi', 'pi')

  try:
    await emit('disp_motion', {'record':pibo.motion_j})
    return JSONResponse(content={"filename":data.filename}, status_code=200)
  except Exception as ex:
    return JSONResponse(content={'result':'파일에 문제가 있습니다.'}, status_code=500)

@app.get('/export_motion/{name}', response_class=FileResponse)
async def export_motion(name="all"):
  try:
    with open('/home/pi/mymotion.json', 'rb') as f:
      tmp = json.load(f)
  except Exception as ex:
    logging.error(f'[export_motion] Error: {ex}')
    return JSONResponse(content={'result':'저장된 모션이 없습니다.'}, status_code=500)

  if name == "all":
    j = tmp  
  elif name in tmp:
    j = dict()
    j[name] = tmp[name]
  else:
    return JSONResponse(content={'result':'선택한 모션이 없습니다.'}, status_code=500)

  with open('/home/pi/.motion.json', 'w') as f:
    json.dump(j, f)
  shutil.chown('/home/pi/.motion.json', 'pi', 'pi')
  return FileResponse(path="/home/pi/.motion.json", media_type="application/json", filename=f"{name}.json")

@app.get('/download_img', response_class=FileResponse)
async def download_img():
  pibo.imwrite('/home/pi/capture.jpg')
  return FileResponse(path="/home/pi/capture.jpg", media_type="image/jpeg", filename="capture.jpg")

@app.post('/upload_oled')
async def upload_oled(data:UploadFile = File(...)):
  if pibo.onoff == False:
    return JSONResponse(content={'result':'OFF 상태입니다.'}, status_code=500)

  data.filename = "tmp.jpg"
  filepath = f"/home/pi/{data.filename}"
  with open(filepath, 'wb') as f:
    content = await data.read()
    f.write(content)
  pibo.set_oled_image(filepath)
  os.remove(filepath)
  return JSONResponse(content={"filename":data.filename}, status_code=200)

@app.post('/upload_file/{directory}')
async def upload_file(directory="myaudio", data:UploadFile = File(...)):
  if directory not in ["myaudio", "myimage"]:
    return JSONResponse(content={'result':'myaudio, myimage로 업로드만 가능합니다.'}, status_code=500)

  os.system(f"mkdir -p '/home/pi/{directory}'")
  filepath = f"/home/pi/{directory}/{data.filename}"
  with open(filepath, 'wb') as f:
    content = await data.read()
    f.write(content)
  return JSONResponse(content={"filename":data.filename}, status_code=200)

@app.post('/upload_csv')
async def upload_csv(data:UploadFile = File(...)):
  data.filename = "mychat.csv"
  filepath = f"/home/pi/{data.filename}"
  with open(filepath, 'wb') as f:
    content = await data.read()
    f.write(content)

  res = pibo.load_csv(filepath)
  os.remove(filepath)
  if res:
    return JSONResponse(content={}, status_code=200)
  else:
    return JSONResponse(content={'result':'csv 파일 에러'}, status_code=500)

## socktio
@app.sio.on('onoff')
async def onoff(sid, d=None):
  await emit('onoff', False if pibo is None else True)

# vision
@app.sio.on('disp_vision')
async def disp_vision(sid, d=None):
  if pibo is None:
    return
  await emit('disp_vision', pibo.vision_type)

@app.sio.on('detect')
async def detect(sid, d=None):
  if pibo is None:
    return
  pibo.vision_type=d

@app.sio.on('marker_length')
async def marker_length(sid, d=None):
  if pibo is None:
    return
  pibo.marker_length=d

@app.sio.on('object_tracker_init')
async def object_tracker_init(sid, d=None):
  if pibo is None:
    return
  if pibo.vision_type == "track":
    pibo.object_tracker_init(d)

@app.sio.on('update_img_pointer')
async def update_img_pointer(sid, d=None):
  if pibo is None:
    return
  pibo.imgX, pibo.imgY = d['x'], d['y']
# device
@app.sio.on('set_neopixel')
async def set_neopixel(sid, d=None):
  if pibo is None:
    return
  pibo.set_neopixel(d)

@app.sio.on('set_oled')
async def set_oled(sid, d=None):
  if pibo is None:
    return
  pibo.set_oled(d)

@app.sio.on('oled_path')
async def oled_path(sid, d=None):
  return await emit('oled_path', os.listdir(d))

@app.sio.on('set_oled_image')
async def set_oled_image(sid, d=None):
  if pibo is None:
    return
  pibo.set_oled_image(d)

@app.sio.on('clear_oled')
async def clear_oled(sid, d=None):
  os.system('/home/pi/.pyenv/bin/python3 /home/pi/openpibo-os/system/network_disp.py')

@app.sio.on('mic')
async def mic(sid, d=None):
  if pibo is None:
    return
  pibo.mic(d)
  await emit('mic', '')
  pibo.aud.play("/home/pi/myaudio/mic.wav", d['volume'])

@app.sio.on('mic_replay')
async def mic_replay(sid, d=None):
  if pibo is None:
    return
  pibo.aud.play("/home/pi/myaudio/mic.wav", d['volume'])

@app.sio.on('tts')
async def tts(sid, d=None):
  if pibo is None:
    return
  pibo.tts(d)
@app.sio.on('play_audio')
async def play_audio(sid, d=None):
  if pibo is not None:
    pibo.stop_audio()
    pibo.play_audio(d["filename"], d["volume"], True)

@app.sio.on('stop_audio')
async def stop_audio(sid, d=None):
  if pibo is not None:
    pibo.stop_audio()

# speech
@app.sio.on('question')
async def question(sid, d=None):
  if pibo is None:
    return
  res = pibo.question(d)
  await emit('disp_speech', {'answer':res, 'chat_list':list(reversed(pibo.chat_list))})

@app.sio.on('translate')
async def translate(sid, d=None):
  if pibo is None:
    return
  res = pibo.translate(d)
  await emit('disp_translate', res)

@app.sio.on('disp_speech')
async def disp_speech(sid, d=None):
  if pibo is None:
    return
  await emit('disp_speech', {'chat_list':list(reversed(pibo.chat_list))})

@app.sio.on('reset_csv')
async def reset_csv(sid, d=None):
  if pibo is None:
    return
  pibo.reset_csv(d)

# motion
@app.sio.on('disp_motion')
async def disp_motion(sid, d=None):
  if pibo is None:
    return
  res = pibo.get_motor_info()
  await emit('disp_motion', {'pos':res[0], 'table':res[1], 'record':res[2]})

@app.sio.on('set_motor')
async def set_motor(sid, d=None):
  if pibo is None:
    return
  pibo.set_motor(d['idx'], d['pos'])

@app.sio.on('set_motors')
async def set_motors(sid, d=None):
  if pibo is None:
    return
  pibo.set_motors(d['pos_lst'])

@app.sio.on('add_frame')
async def add_frame(sid, d=None):
  if pibo is None:
    return
  res = pibo.add_frame(d)
  await emit('disp_motion', {'table':res})

@app.sio.on('delete_frame')
async def delete_frame(sid, d=None):
  if pibo is None:
    return
  res = pibo.delete_frame(d)
  await emit('disp_motion', {'table':res})

@app.sio.on('init_frame')
async def init_frame(sid, d=None):
  if pibo is None:
    return
  res = pibo.init_frame()
  await emit('disp_motion',{'table':res})

@app.sio.on('play_frame')
async def play_frame(sid, d=None):
  if pibo is None:
    return
  pibo.play_frame(d)

@app.sio.on('stop_frame')
async def stop_frame(sid, d=None):
  if pibo is None:
    return
  pibo.stop_frame()

@app.sio.on('add_motion')
async def add_motion(sid, d=None):
  if pibo is None:
    return
  res = pibo.add_motion(d)
  await emit('disp_motion', {'record':res})

@app.sio.on('load_motion')
async def load_motion(sid, d=None):
  if pibo is None:
    return
  res = pibo.load_motion(d)
  await emit('disp_motion', {'table':res})

@app.sio.on('delete_motion')
async def delete_motion(sid, d=None):
  if pibo is None:
    return
  res = pibo.delete_motion(d)
  await emit('disp_motion', {'record':res})

@app.sio.on('reset_motion')
async def reset_motion(sid, d=None):
  if pibo is None:
    return
  res = pibo.reset_motion()
  await emit('disp_motion', {'record':res})

@app.sio.on('vision_sleep')
async def vision_sleep(sid, d='off'):
  if pibo is None:
    return
  pibo.vision_sleep = True if d == 'on' else False
  return await emit('vision_sleep', 'on' if pibo.vision_sleep else 'off')

@app.sio.on('audio_path')
async def audio_path(sid, d=None):
  return await emit('audio_path', os.listdir(d))

@app.sio.on('eye_update')
async def eye_update(sid, d=None):
  value = [0,0,0,0,0,0] if d == None else d.split(",")
  pibo.set_neopixel(value)

############################################################################################
@app.sio.on('sim_play_item')
async def sim_play_item(sid, d=None):
  key = d['key']
  content = d['content']
  if pibo is not None:
    if key == 'eye':
      pibo.set_neopixel(content)
      return await emit('sim_result', {'eye':'stop'})
    elif key == 'motion':
      if d['type'] == 'default':
        pibo.async_sim_motion(content, d['cycle'])
      if d['type'] == 'mymotion':
        pibo.async_sim_motion(content, d['cycle'], "/home/pi/mymotion.json")
    elif key == 'audio':
      pibo.async_sim_audio(d["type"]+content, d["volume"])
    elif key == 'oled':
      if d['type'] == 'text':
        pibo.set_oled({'x':d['x'], 'y': d['y'], 'size': d['size'], 'text': content})
      else:
        pibo.set_oled_image(content)
      return await emit('sim_result', {'oled':'stop'})
    elif key == 'tts':
      pibo.tts({'text': content, 'voice_type': d['type'], 'volume': d['volume']})
      return await emit('sim_result', {'tts':'stop'})
    else:
      return await emit('sim_result', "sim_play_item error: " + d)

@app.sio.on('sim_stop_item')
async def sim_stop_item(sid, d=None):
  if pibo is not None:
    if d == 'eye':
      pibo.set_neopixel([0,0,0,0,0,0])
    elif d == 'motion':
      pibo.stop_frame()
      pibo.set_motors([0, 0, -80, 0, 0, 0, 0, 0, 80, 0])
    elif d == 'audio':
      pibo.stop_audio()
    elif d == 'oled':
      os.system('/home/pi/.pyenv/bin/python3 /home/pi/openpibo-os/system/network_disp.py')
    elif d == 'tts':
      pibo.stop_audio()
    return await emit('sim_result', "sim_stop_item ok")

@app.sio.on('sim_update_audio')
async def sim_update_audio(sid, d=None):
  if pibo is not None:
    return await emit('sim_update_audio', os.listdir(d))

@app.sio.on('sim_update_oled')
async def sim_update_oled(sid, d=None):
  if pibo is not None:
    return await emit('sim_update_oled', os.listdir(d))

@app.sio.on('sim_update_motion')
async def sim_update_motion(sid, d=None):
  if pibo is not None:
    return await emit('sim_update_motion', pibo.mot.get_motion() if d == 'default' else pibo.mot.get_motion(path="/home/pi/mymotion.json"))

@app.sio.on('sim_play_items')
async def sim_play_items(sid, d=None):
  if pibo is not None:
    pibo.start_simulate(d)

@app.sio.on('sim_stop_items')
async def sim_stop_items(sid, d=None):
  if pibo is not None:
    pibo.stop_simulate()

@app.sio.on('sim_add_items')
async def sim_add_items(sid, d=None):
  if pibo is not None:
    try:
      res = {}
      with open('/home/pi/mysim.json', 'rb') as f:
        res = json.load(f)
    except Exception as ex:
      logging.error(f'[simulation] Error: {ex}')
      pass

    res[d['name']] = d['data']
    with open('/home/pi/mysim.json', 'w') as f:
      json.dump(res, f)
    return await emit('sim_result', "sim_add_items ok")

@app.sio.on('sim_remove_items')
async def sim_remove_items(sid, d=None):
  if pibo is not None:
    res = {}
    if d != None:
      try:
        res = {}
        with open('/home/pi/mysim.json', 'rb') as f:
          res = json.load(f)
      except Exception as ex:
        logging.error(f'[simulation] Error: {ex}')
        pass

      if d in res:
        del res[d]

    with open('/home/pi/mysim.json', 'w') as f:
      json.dump(res, f)
    shutil.chown('/home/pi/mysim.json', 'pi', 'pi')
    return await emit('sim_result', "sim_remove_items ok")

@app.sio.on('sim_load_items')
async def sim_load_items(sid, d=None):
  if pibo is not None:
    try:
      res = {}
      with open('/home/pi/mysim.json', 'rb') as f:
        res = json.load(f)
    except Exception as ex:
      logging.error(f'[simulation] Error: {ex}')
      pass
    return await emit('sim_load_items', [item for item in res])

@app.sio.on('sim_load_item')
async def sim_load_item(sid, d=None):
  if pibo is not None:
    try:
      res = {}
      with open('/home/pi/mysim.json', 'rb') as f:
        res = json.load(f)
    except Exception as ex:
      logging.error(f'[simulation] Error: {ex}')
      pass
    return await emit('sim_load_item', res[d])
############################################################################################

async def emit(key, data, callback=None):
  try:
    logging.debug(f'{key}')
    await app.sio.emit(key, data, callback=callback)
  except Exception as ex:
    logging.error(f'[emit] Error: {ex}')

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--port', help='set port number', default=50000)
  args = parser.parse_args()

  import uvicorn
  uvicorn.run('run_tools:app', host='0.0.0.0', port=args.port, access_log=False)
