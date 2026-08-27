"""
openpibo-python
"""
import os, sys, json, shutil

__version__ = '0.10.0.0'

#: 기기 밖(개발 PC, CI, 새로 만든 가상환경)에서도 import 는 되어야 한다.
#: 기기에서는 그대로 /home/pi 다.
home = os.environ.get('OPENPIBO_HOME', '/home/pi')

defconfig = {
  "datapath": os.path.join(home, "openpibo-files"),
  "napi_host": "https://oe-napi.circul.us",
  "sapi_host": "https://oe-sapi.circul.us",
  "robotId": "",
  "eye": "0,0,0,0,0,0",
  "board": "",   # 'pibo' | 'pibrain' | '' (비면 /home/pi/.board 를 본다 → openpibo.board)
}
config_path = os.path.join(home, 'config.json')

try:
  if os.path.isfile(config_path) == False:
    config = defconfig
  else:
    with open(config_path, 'r') as f:
      config = json.load(f)
    for k, v in defconfig.items():
      if k not in config:
        config[k] = v
except Exception as ex:
  config = defconfig

# config.json 쓰기는 부수효과일 뿐이다. 못 쓴다고 import 가 죽으면
# 기기 밖에서는 라이브러리를 아예 못 쓰게 된다.
try:
  with open(config_path, 'w') as f:
    json.dump(config, f)
  shutil.chown(config_path, 'pi', 'pi')
except Exception:
  pass

for k, v in config.items():
  globals()[k] = v

current_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_path)
from .modules import *

'''
from .audio import Audio
from .collect import Wikipedia, Weather, News
from .device import Device
from .motion import Motion
from .oled import Oled
from .speech import Speech, Dialog
from .vision import Camera, Face, Detect
from .edu_v1 import Pibo
'''
