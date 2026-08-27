import openpibo_models
from openpibo.vision_camera import Camera
from openpibo.vision_face import Face
from openpibo.vision_detect import Detect
from openpibo.vision_classify import CustomClassifier
from openpibo.audio import Audio
from openpibo.oled import get_display
from openpibo.speech import Speech, Dialog
from openpibo.motion import Motion
from openpibo.device import get_device
from openpibo.board import BOARD
import asyncio
import numpy as np
import time,datetime
import base64
import cv2,dlib,logging
import os,json,shutil,csv
from PIL import Image,ImageDraw,ImageFont,ImageOps
from queue import Queue
from threading import Thread, Timer

logging.basicConfig(level=logging.ERROR, format='%(asctime)s [%(levelname)s] %(message)s')

OFFLINE_VOICES = {"m1","m2","m3","m4","m5","f1","f2","f3","f4","f5"}

def to_base64(im):
  im = cv2.resize(im, (320, 240))
  _, buffer = cv2.imencode('.jpg', im, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
  return base64.b64encode(buffer).decode('utf-8')

class Pibo:
  def __init__(self, emit_func=None, logger=None):
    logging.info('Class INIT')
    self.emit = emit_func
    self.mymodel_path = "/home/pi/mymodel"
    self.trackX, self.trackY = 0, 0
    self.imgX, self.imgY = 0, 0
    self.marker_length = 2
    self.motion_d = [0, 0, -80, 0, 0, 0, 0, 0, 80, 0]
    self.motion_p = []
    self.motion_j = {}
    self._speech_od = None  # lazy init for SpeechOnDevice

    try:
      with open('/home/pi/mymotion.json', 'rb') as f:
        self.motion_j = json.load(f)
    except Exception as ex:
      logging.error(f'[motion_start] Error: {ex}')

    asyncio.run(self.emit('onoff', True, callback=None))
    # 파이보/파이브레인에 맞는 클래스. 두 클래스는 API 가 같지 않다 —
    # 파이브레인에는 배터리도 PIR 도 없다 (openpibo.device 모듈 docstring 참고).
    self.dev = get_device()
    self.device_start()
    self.ole = get_display()
    self.vision_type = "camera"
    self.vision_sleep = True
    self.chat_list = []

    self.mot = Motion()
    self.aud = Audio()
    self.speech = Speech()
    self.cam = Camera()
    self.fac = Face()
    self.det = Detect()
    self.dialog = Dialog()

    if BOARD.features.has_legs:
      self.mot.set_motors(self.motion_d, movetime=1000)   # 기본 자세
    self.det.load_hand_gesture_model()
    Thread(name='vision_loop', target=self.vision_loop, args=(), daemon=True).start()

  # ──────────────────────────────────────────────
  # Vision
  # ──────────────────────────────────────────────

  def vision_loop(self):
    while True:
      if self.vision_sleep == True:
        time.sleep(1)
        continue

      try:
        self.frame = self.cam.read()
        if self.vision_type == 'grayscale':
          img, res = cv2.cvtColor(self.frame.copy(), cv2.COLOR_BGR2GRAY), ''
        elif self.vision_type == 'canny':
          img, res = cv2.Canny(cv2.cvtColor(self.frame.copy(), cv2.COLOR_BGR2GRAY), 200, 200), ''
        elif self.vision_type == 'edgePreservingFilter':
          img, res = cv2.edgePreservingFilter(self.frame.copy()), ''
        elif self.vision_type == "cartoon":
          img, res = self.cam.stylization(self.frame.copy()), ''
        elif self.vision_type == "sketch_rgb":
          img, res = self.cam.pencilSketch(self.frame.copy())[1], ''
        elif self.vision_type == "detail":
          img, res = self.cam.detailEnhance(self.frame.copy()), ''
        elif self.vision_type == "qr":
          img, res = self.qr_detect()
        elif self.vision_type == "face":
          img, res = self.face_detect()
        elif self.vision_type == "face_landmark":
          img, res = self.face_landmark()
        elif self.vision_type == "object":
          img, res = self.object_detect()
        elif self.vision_type == "hand":
          img, res = self.hand_detect()
        elif self.vision_type == "pose":
          img, res = self.pose_detect()
        elif self.vision_type == "track":
          img, res = self.track_object()
        elif self.vision_type == "marker":
          img, res = self.detect_marker()
        else:
          img, res = self.frame, ""
      except Exception as ex:
        logging.error(f'[vision_loop] Error: {ex}')
        img, res = self.frame, str(ex)

      self.res_img = img.copy()
      if self.cam:
        self.cam.putText(img, '+', (self.imgX-5, self.imgY), 0.6, (100, 100, 200), 3)
      asyncio.run(self.emit('stream', {'img': to_base64(img), 'data': res}, callback=None))
      time.sleep(0.5)

  def face_detect(self):
    im = self.frame.copy()
    items = self.fac.detect_face(im)
    res = ''
    if len(items) > 0:
      x1, y1, x2, y2 = items[0]
      face = self.fac.analyze_face(im, items[0])
      colors = (200, 100, 0) if face['gender'] == 'Male' else (100, 200, 0)
      self.cam.rectangle(im, (x1, y1), (x2, y2), colors, 3)
      self.cam.putText(im, f"{face['gender']}, {face['age']}, {face['emotion']}", (x1+10, y1+20), 0.6, colors, 2)
      res += f"{face['gender']}, {face['age']}, {face['emotion']} ({x1}, {y1})"
    return im, res

  def face_landmark(self):
    im = self.frame.copy()
    res = self.fac.detect_mesh(im)
    self.fac.detect_mesh_vis(im, res)
    return im, ",".join([f"{d['distance']} cm / {d['direction']}" for d in res])

  def object_detect(self):
    im = self.frame.copy()
    items = self.det.detect_object(im)
    res = ''
    for obj in items:
      x1, y1, x2, y2 = obj['box']
      colors = (100, 100, 200)
      self.cam.rectangle(im, (x1, y1), (x2, y2), colors, 3)
      (text_width, text_height), baseline = cv2.getTextSize(f'{obj["name"]} {obj["score"]}', cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
      cv2.rectangle(im, (x1, y1 - text_height - baseline), (x1 + text_width, y1), colors, -1)
      self.cam.putText(im, f'{obj["name"]} {obj["score"]}', (x1, y1 - baseline), 0.5, (255, 255, 255), 2)
      res += '[{}-({},{})] '.format(obj['name'], x1, y1)
    return im, res

  def hand_detect(self):
    im = self.frame.copy()
    res = self.det.recognize_hand_gesture(im)
    self.det.recognize_hand_gesture_vis(im, res)
    return im, ",".join([f"{d['name']} / {d['score']}" for d in res])

  def qr_detect(self):
    im = self.frame.copy()
    items = self.det.detect_qr(im)
    res = ''
    for item in items:
      if item['type'] != '':
        x1, y1, x2, y2 = item['box']
        colors = (100, 0, 200)
        self.cam.rectangle(im, (x1, y1), (x2, y2), colors, 3)
        self.cam.putText(im, 'QR', (x1+10, y1+20), 0.6, colors, 2)
        res += '[{}-{} / ({},{})] '.format(item['data'], item['type'], x1, y1)
    return im, res

  def pose_detect(self):
    im = self.frame.copy()
    self.det.detect_pose_vis(im, self.det.detect_pose(im))
    return im, ''

  def object_tracker_init(self, d):
    im = self.frame.copy()
    if self.det.tracker is not None:
      del self.det.tracker
    self.det.object_tracker_init(im, (d['x1'], d['y1'], d['x2'], d['y2']))

  def track_object(self):
    im = self.frame.copy()
    colors = (100, 0, 200)
    if self.det.tracker is not None:
      x1, y1, x2, y2 = self.det.track_object(im)
      self.cam.rectangle(im, (x1, y1), (x2, y2), colors, 3)
    return im, ""

  def detect_marker(self):
    im = self.frame.copy()
    res = self.det.detect_marker(im, self.marker_length)
    self.det.detect_marker_vis(im, res)
    return im, " ".join([f'({d["id"]})-{d["distance"]}cm' for d in res])

  def imwrite(self, name):
    self.cam.imwrite(name, self.res_img.copy())

  # ──────────────────────────────────────────────
  # Audio / TTS
  # ──────────────────────────────────────────────

  def mic(self, d):
    self.aud.record(filename="/home/pi/myaudio/mic.wav", timeout=d['time'])

  def tts(self, d):
    voice_type = d['voice_type']
    volume = d['volume']
    text = d['text']

    if voice_type in OFFLINE_VOICES:
      filename = "/home/pi/myaudio/tts.wav"
      try:
        if self._speech_od is None:
          from openpibo.speech import SpeechOnDevice
          self._speech_od = SpeechOnDevice()
        self._speech_od.tts(text=text, filename=filename, voice=voice_type, lang="ko")
        self.aud.play(filename=filename, volume=volume)
      except Exception as ex:
        logging.error(f'[tts offline] Error: {ex}')
      return

    filename = "/home/pi/myaudio/tts.mp3"
    try:
      lang = "en" if "e_" in voice_type else "ko"
      self.speech.tts(text=text, filename=filename, voice=voice_type, lang=lang)
      self.aud.play(filename=filename, volume=volume)
    except Exception as ex:
      logging.error(f'[tts] Error: {ex}')

  def play_audio(self, filename, volume, background):
    self.aud.play(filename=filename, volume=volume, background=background)

  def stop_audio(self):
    self.aud.stop()

  # ──────────────────────────────────────────────
  # Speech / Dialog
  # ──────────────────────────────────────────────

  def load_csv(self, d):
    with open(d, 'r', encoding='utf-8') as f:
      items = csv.reader(f)
      res = []
      for item in items:
        if len(item) == 2:
          res.append(item)
      if len(res) == 0:
        return False
    self.dialog.load(d)
    return True

  def reset_csv(self, d):
    if d['lang'] == 'en':
      self.dialog.load(openpibo_models.filepath('dialog_en.csv'))
    else:
      self.dialog.load(openpibo_models.filepath('dialog.csv'))

  def question(self, d):
    q = d['question']
    voice_type = d['voice_type']
    volume = d['volume']
    n = d['n']
    ans = self.dialog.get_dialog(q, n)
    self.chat_list.append([str(datetime.datetime.now()).split('.')[0], q, ans])
    if len(self.chat_list) > 10:
      self.chat_list.pop(0)
    if d['voice_en'] == 'off':
      return ans
    try:
      self.tts({'text': ans, 'voice_type': voice_type, 'volume': volume})
    except Exception as ex:
      logging.error(f'[question] Error: {ex}')
    return ans

  def translate(self, d):
    res = self.dialog.translate(d['text'], d['langtype'])
    if d['voice_en'] == 'off':
      return res
    filename = "/home/pi/myaudio/tts.mp3"
    self.speech.tts(text=res, filename=filename, voice="gtts", lang=d['langtype'])
    self.aud.play(filename=filename, volume=d['volume'])
    return res

  # ──────────────────────────────────────────────
  # Motion
  # ──────────────────────────────────────────────

  def make_raw(self):
    if len(self.motion_p) == 0:
      return {}
    return {'init_def': 1, 'init': self.motion_p[0]['d'], 'pos': self.motion_p[1:]} \
      if self.motion_p[0]['seq'] == 0 else {'init_def': 0, 'pos': self.motion_p[:]}

  def get_motor_info(self):
    return self.motion_d, self.motion_p, self.motion_j

  def set_motor(self, idx, pos):
    self.motion_d[idx] = pos
    self.mot.set_speed(idx, 50)
    self.mot.set_acceleration(idx, 0)
    self.mot.set_motor(idx, pos)

  def set_motors(self, pos_lst, movetime=1000):
    self.motion_d = pos_lst
    self.mot.set_motors(pos_lst, movetime)

  def add_frame(self, seq):
    seq = int(seq)
    _check = False
    for idx, pos in enumerate(self.motion_p):
      if pos['seq'] == seq:
        self.motion_p[idx] = {'d': self.motion_d[:], 'seq': int(seq)}
        _check = True
        break
    if not _check:
      self.motion_p.append({'d': self.motion_d[:], 'seq': int(seq)})
      self.motion_p.sort(key=lambda x: x['seq'])
    return self.motion_p

  def delete_frame(self, seq):
    for idx, pos in enumerate(self.motion_p):
      if pos['seq'] == seq:
        del self.motion_p[idx]
        break
    return self.motion_p

  def init_frame(self):
    self.motion_p = []
    return self.motion_p

  def play_frame(self, cycle):
    raw = self.make_raw()
    Thread(name='play_frame', target=self.mot.set_motion_raw, args=(raw, int(cycle)), daemon=True).start()

  def stop_frame(self):
    self.mot.stop()

  def add_motion(self, name):
    self.motion_j[name] = self.make_raw()
    with open('/home/pi/mymotion.json', 'w') as f:
      json.dump(self.motion_j, f)
    shutil.chown('/home/pi/mymotion.json', 'pi', 'pi')
    return self.motion_j

  def load_motion(self, name):
    if name in self.motion_j:
      a = self.motion_j[name]
    elif name in self.mot.get_motion():
      a = self.mot.get_motion(name)
    else:
      return self.motion_p
    self.motion_p = []
    if 'init_def' in a and 'init' in a:
      self.motion_p.append({'d': a['init'], 'seq': 0})
    if 'pos' in a:
      for item in a['pos']:
        self.motion_p.append(item)
    return self.motion_p

  def delete_motion(self, name):
    if name in self.motion_j:
      del self.motion_j[name]
    with open('/home/pi/mymotion.json', 'w') as f:
      json.dump(self.motion_j, f)
    shutil.chown('/home/pi/mymotion.json', 'pi', 'pi')
    return self.motion_j

  def reset_motion(self):
    self.motion_j = {}
    with open('/home/pi/mymotion.json', 'w') as f:
      json.dump(self.motion_j, f)
    shutil.chown('/home/pi/mymotion.json', 'pi', 'pi')
    return self.motion_j

  # ──────────────────────────────────────────────
  # Device
  # ──────────────────────────────────────────────

  def device_start(self):
    self.devque = Queue()
    self.system_value = ['', '', '', '', '', '']
    self.battery = '0%'
    with open('/home/pi/config.json', 'r') as f:
      tmp = json.load(f)
      self.neopixel_value = tmp['eye'].split(',') if 'eye' in tmp else [0, 0, 0, 0, 0, 0]

    # 아래는 전부 MCU 패킷(#30 #14 #23 #40)이다. MCU 가 없는 보드에서는
    # 시리얼이 없어 device_loop 이 예외로 계속 돈다. 아예 띄우지 않는다.
    if not BOARD.features.has_mcu:
      logging.info(f'[device_start] {BOARD.label}: MCU 없음 — device_loop 생략')
      return

    Thread(name='device_loop', target=self.device_loop, args=(), daemon=True).start()
    self.send_message("30", 'on')
    time.sleep(0.1)
    self.send_message("14")
    time.sleep(0.1)
    self.send_message("23", ','.join([str(_) for _ in self.neopixel_value]))

  def device_stop(self):
    pass

  def send_message(self, code, data=""):
    self.devque.put(f'#{code}:{data}!')

  def decode_pkt(self, pkt):
    pkt = pkt.split(":")
    code, data = pkt[0], pkt[1]
    if code == '40':
      item = data.split("-")
      item[2] = self.system_value[2] if item[2] == '' else item[2]
      self.system_value = item
      asyncio.run(self.emit('update_device', self.system_value, callback=None))

  def device_loop(self):
    system_check_time = time.time()
    while True:
      try:
        if time.time() - system_check_time > 1:
          self.decode_pkt(self.dev.send_raw("#40:!"))
          system_check_time = time.time()
        elif self.devque.qsize() > 0:
          data = self.dev.send_raw(self.devque.get())
          self.decode_pkt(data)
      except Exception as ex:
        pass
      time.sleep(0.1)

  def set_neopixel(self, d):
    if type(d) is dict and 'idx' in d and 'value' in d:
      self.neopixel_value[d['idx']] = d['value']
    if type(d) is list and len(d) == 6:
      self.neopixel_value = d
    self.send_message("23", ','.join([str(_) for _ in self.neopixel_value]))

  def set_oled_image(self, filepath):
    img = self.cam.imread(filepath)
    self.ole.draw_data(cv2.resize(img, (128, 64)))
    self.ole.show()

  def set_oled(self, d):
    self.ole.clear()
    self.ole.set_font(size=d['size'])
    x = d['x']
    y = d['y']
    for item in d['text'].split('\\n'):
      _, _, _, h = self.ole.font.getbbox(item)
      self.ole.draw_text((x, y), item)
      y += h
    self.ole.show()

  # ──────────────────────────────────────────────
  # Simulate
  # ──────────────────────────────────────────────

  def sim_motion(self, name, cycle=1, path=None, log=True):
    self.mot.set_motion(name, cycle, path)
    if log:
      asyncio.run(self.emit('sim_result', {'motion': 'stop'}, callback=None))

  def async_sim_motion(self, name, cycle=1, path=None, log=True):
    self.mot.stop()
    try:
      self.mot.simT.join()
    except Exception:
      pass
    self.mot.simT = Thread(name='sim_motion', target=self.sim_motion, args=(name, cycle, path, log), daemon=True)
    self.mot.simT.start()

  def sim_audio(self, filename, volume, log=True):
    self.stop_audio()
    self.play_audio(filename, volume, False)
    if log:
      asyncio.run(self.emit('sim_result', {'audio': 'stop'}, callback=None))

  def async_sim_audio(self, filename, volume, log=True):
    Thread(name='sim_audio', target=self.sim_audio, args=(filename, volume, log), daemon=True).start()

  def set_simulate(self, item):
    logging.info(item)
    if 'eye' in item:
      self.set_neopixel(item['eye']['content'])
    if 'motion' in item:
      d = item['motion']
      path = "/home/pi/mymotion.json" if d['type'] == 'mymotion' else None
      self.async_sim_motion(d['content'], d['cycle'], path, log=False)
    if 'audio' in item:
      d = item['audio']
      self.async_sim_audio(d["type"] + d["content"], d["volume"], log=False)
    if 'oled' in item:
      d = item['oled']
      if d['type'] == 'text':
        self.set_oled({'x': d['x'], 'y': d['y'], 'size': d['size'], 'text': d['content']})
      else:
        self.set_oled_image(d['content'])
    if 'tts' in item:
      d = item['tts']
      self.tts({'text': d['content'], 'voice_type': d['type'], 'volume': d['volume']})

  def start_simulate(self, items):
    self.stop_simulate()
    self.timers = []
    for item in items:
      timer = Timer(item['time'], self.set_simulate, args=(item,))
      timer.daemon = True
      timer.start()
      self.timers.append(timer)

  def stop_simulate(self):
    try:
      for timer in self.timers:
        timer.cancel()
      self.stop_frame()
      self.stop_audio()
      self.set_motors([0, 0, -80, 0, 0, 0, 0, 0, 80, 0])
    except Exception as ex:
      logging.error(ex)