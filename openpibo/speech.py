"""
번역, 형태소 분석, 자연어 인식 및 합성, 챗봇 등 다양한 자연어 처리를 합니다.

Class:
:obj:`~openpibo.speech.Speech`
:obj:`~openpibo.speech.SpeechOnDevice`
:obj:`~openpibo.speech.Dialog`
"""

import csv
import random
import json
import os
import time
import requests
from . import napi_host, sapi_host
from .board import BOARD
from .modules.speech.mtranslate import translate

import numpy as np
import onnxruntime as ort
import soundfile as sf
from .modules.speech.mtts import (
    load_text_to_speech,
    load_voice_style,
    TextToSpeech,
)
import openpibo_models


def _arecord(timeout):
  """
  보드에 맞는 arecord 명령을 만든다.

  파이보 16000/S32_LE, 파이브레인 44100/S16_LE — 마이크 하드웨어가 다르다.
  openpibo.audio.Audio.record() 와 같은 값을 쓴다. 두 군데에 적으면 어긋난다.
  """

  mic = BOARD.mic
  return (f'arecord -D {mic.device} -c{mic.channels} -r {mic.rate} '
          f'-f {mic.format} -d {timeout} -t wav -q')
#current_path = os.path.dirname(os.path.realpath(__file__))

os.environ["ORT_LOGGING_LEVEL"] = "3"

def speech_api(mode, type, params={}, json_data={}):
  """
  인공지능 보이스 API를 호출합니다.

  example::

    from openpibo.speech import speech_api

    res = speech_api(...)
  """
  if type == "GET":
    return requests.get(f"{napi_host}/{mode}", params=params)
  elif type == "POST":
    return requests.post(f"{napi_host}/{mode}", params=params, json=json_data)

class Speech:
  """
Functions:
:meth:`~openpibo.speech.Speech.tts`
:meth:`~openpibo.speech.Speech.stt`

  * TTS (Text to Speech)
  * STT (Speech to Text)

  example::

    from openpibo.speech import Speech

    speech = Speech()
    # 아래의 모든 예제 이전에 위 코드를 먼저 사용합니다.
  """

  def __init__(self):
    self.SAPI_HOST = sapi_host

  def tts(self, text, filename="tts.mp3", voice="main", lang="ko"):
    """
    TTS(Text to Speech)

    Text(문자)를 Speech(말)로 변환하여 파일로 저장합니다.

    example::

      speech.tts('안녕하세요! 만나서 반가워요!', 'main', 'ko', '/home/pi/tts.mp3')

    :param str text: 변환할 문장구

    :param str voice: 목소리 타입(espeak | gtts | main | boy | girl | man1 | woman1)

    :param str lang: 사용할 언어(ko | en)

    :param str filename: 변환된 음성파일의 경로 (mp3)
    """

    if type(text) is not str:
      raise Exception(f'"{text}" must be str type')

    if voice == "espeak":
      os.system(f'espeak "{text}" -w {filename}')
      return
    elif voice in ["gtts", "e_gtts"]:
      data = {
        "client":"tw-ob",
        "q":text,
        "tl":lang
      }
      url = 'https://translate.google.com/translate_tts'
    else:
      data = {
        "text":text,
        "hash":"",
        "voice":voice, # ['main', 'boy', 'girl', 'man1', 'woman1']
        "lang":lang, # ['ko', 'en']
        "type":"mp3"
      }
      url = self.SAPI_HOST + '/tts'

    res = requests.get(url, params=data)
    if res.status_code != 200:
      raise Exception(f'response error: {res}')

    with open(filename, 'wb') as f:
      f.write(res.content)

  def stt(self, filename="stream.wav", timeout=5, verbose=True):
    """
    STT(Speech to Text)

    목소리를 녹음한 후 파일로 저장하고, 그 파일의 Speech(말)를 Text(문자)로 변환합니다.

    녹음 파일은 ``timeout`` 초 동안 녹음되며, ``filename`` 의 경로에 저장됩니다.

    example::

      speech.stt('/home/pi/stt.wav', 5)

    :param str filename: 녹음한 파일이 저장 될 경로. ``wav`` 확장자를 사용합니다.

    :param int timeout: 녹음 시간(s)

    :returns: 인식된 문자열
    """

    if verbose == True:
      os.system(f'{_arecord(timeout)} -vv -V stereo stream.raw;sox stream.raw -c 1 -b 16 {filename};rm stream.raw')
    else:
      os.system(f'{_arecord(timeout)} stream.raw;sox stream.raw -q -c 1 -b 16 {filename};rm stream.raw')

    res = requests.post("https://o-vapi.circul.us/stt" + '/stt', files={'uploadFile':open(filename, 'rb')})

    if res.status_code != 200:
      raise Exception(f'response error: {res}')

    if res.json()['result'] == False:
      raise Exception(f'result error: {res.json()}')

    return res.json()['data']

DEFAULT_MODEL_DIR = "/home/pi/.model"

class SpeechOnDevice:
  """
Functions:
:meth:`~openpibo.speech.SpeechOnDevice.tts`

  * TTS (Text to Speech)

  example::

    from openpibo.speech import SpeechOnDevice

    speech_od = SpeechOnDevice()
    # 아래의 모든 예제 이전에 위 코드를 먼저 사용합니다.
  """

  def __init__(
    self,
    onnx_dir: str = f"{DEFAULT_MODEL_DIR}/tts/assets/onnx",
    voice_dir: str = f"{DEFAULT_MODEL_DIR}/tts/assets/voice_styles",
    total_step: int = 5,
    speed: float = 1.05,
  ):
    """
    :param str onnx_dir: ONNX 모델 디렉토리 경로
    :param str voice_dir: 보이스 스타일 JSON 디렉토리 경로
    :param int total_step: 디노이징 스텝 수 (높을수록 품질↑, 속도↓)
    :param float speed: 말하기 속도 (높을수록 빠름)
    """
    self.onnx_dir = onnx_dir
    self.voice_dir = voice_dir
    self.total_step = total_step
    self.speed = speed
    self._model: TextToSpeech = load_text_to_speech(onnx_dir, use_gpu=False)
 
  def tts(
    self,
    text: str,
    filename: str = "tts.wav",
    voice: str = "m1",
    lang: str = "ko",
  ) -> str:
    """
    TTS(Text to Speech) — 텍스트를 음성 파일로 변환합니다.

      example::

        tts.tts(text='안녕하세요! 만나서 반가워요!', filename='/home/pi/tts.wav', voice='m1', lang='ko')

    :param str text: 변환할 문장
    :param str filename: 저장할 음성 파일 경로 (.wav)
    :param str voice: 목소리 종류 (m1~m5/f1~f5)
    :param str lang: 언어 코드 ('ko', 'en', 'es', 'pt', 'fr')
    :returns str: 저장된 파일 경로
    """

    if not isinstance(text, str):
      raise TypeError(f'"{text}" must be str type')
    if voice not in ("m1", "m2", "m3", "m4", "m5", "f1", "f2", "f3", "f4", "f5"):
      raise ValueError(f"voice must be 0~9, got {voice}")
    if lang not in ("ko", "en", "es", "pt", "fr"):
      raise ValueError(f"Unsupported lang: {lang}")

    voice_path = os.path.join(self.voice_dir, f"{voice}.json")
    if not os.path.exists(voice_path):
      raise FileNotFoundError(f"Voice style not found: {voice_path}")

    style = load_voice_style([voice_path])
    wav, duration = self._model(
      text=text,
      lang=lang,
      style=style,
      total_step=self.total_step,
      speed=self.speed,
    )

    out_dir = os.path.dirname(filename)
    if out_dir and not os.path.exists(out_dir):
      os.makedirs(out_dir)

    # wav 저장
    w = wav[0, : int(self._model.sample_rate * duration[0].item())]
    sf.write(filename, w, self._model.sample_rate)

  def stt(self, filename="stream.wav", timeout=5, verbose=False, lang=None):
    """
    STT(Speech to Text)

    목소리를 녹음한 후 faster-whisper로 텍스트로 변환합니다.

    example::

      speech_od.stt(timeout=5)

    :param str filename: 녹음 파일 저장 경로 (.wav)
    :param int timeout: 녹음 시간(s)
    :param bool verbose: 녹음 진행 출력 여부
    :param str lang: 언어 힌트 (None=자동감지, 'ko', 'en' 등)
    :returns: (인식된 문자열, 감지된 언어)
    """
    # 녹음 (Speech 클래스와 동일)
    if verbose:
      os.system(f'{_arecord(timeout)} -vv -V stereo stream.raw;sox stream.raw -c 1 -b 16 {filename};rm stream.raw')
    else:
      os.system(f'{_arecord(timeout)} stream.raw;sox stream.raw -q -c 1 -b 16 {filename};rm stream.raw')

    # 다운로드
    #python3 -c "
    #from huggingface_hub import snapshot_download
    #snapshot_download(
    #    repo_id='Systran/faster-whisper-base',  # 또는 faster-whisper-small
    #    local_dir='/home/pi/.model/stt/whisper-base'
    #)
    #"

    # STT (faster-whisper)
    if not hasattr(self, '_stt_model'):
      from faster_whisper import WhisperModel
      self._stt_model = WhisperModel(
        f"{DEFAULT_MODEL_DIR}/stt/whisper-base",
        device="cpu",
        local_files_only=True,
        compute_type="int8",
      )

    segments, info = self._stt_model.transcribe(filename, vad_filter=True, language=lang)
    text = " ".join([seg.text.strip() for seg in segments])
    return {"text":text, "lang":info.language}
 
class Dialog:
  """
Functions:
:meth:`~openpibo.speech.Dialog.load`
:meth:`~openpibo.speech.Dialog.reset`
:meth:`~openpibo.speech.Dialog.ngram`
:meth:`~openpibo.speech.Dialog.diff_ngram`
:meth:`~openpibo.speech.Dialog.get_dialog`
:meth:`~openpibo.speech.Dialog.translate`
:meth:`~openpibo.speech.Dialog.get_dialog_dl`
:meth:`~openpibo.speech.Dialog.nlp_dl`
:meth:`~openpibo.speech.Dialog.start_llm`
:meth:`~openpibo.speech.Dialog.call_llm`
:meth:`~openpibo.speech.Dialog.stop_llm`

  파이보에서 대화와 관련된 자연어처리 기능을 하는 클래스입니다. 다음 기능을 수행할 수 있습니다.

  * 형태소 및 명사 분석
  * 챗봇 기능
  * 한역 번역 / 대화 (Deep Learning) 
  * 자연어 분석 기능 (Deep Learning)

  example::

    from openpibo.speech import Dialog

    dialog = Dialog()
    # 아래의 모든 예제 이전에 위 코드를 먼저 사용합니다.
  """

  def __init__(self):
    self.dialog_db = []
    #self.mecab = Mecab()
    self.NAPI_HOST = napi_host
    self.load(openpibo_models.filepath("dialog.csv"))

  def load(self, filepath):
    """
    대화 데이터를 로드합니다.

    example::

      dialog.load('/home/pi/dialog.csv')

    :param str string: 대화 데이터 파일 경로(csv)

    대화 데이터 파일 형식::

      대화1,답변1
      대화2,답변2
      ...
      대화n,답변n
    """

    self.dialog_path = filepath
    with open(self.dialog_path, 'r', encoding='utf-8') as f:
      self.dialog_db = [item for item in csv.reader(f)]

  def reset(self):
    """
    대화 데이터를 초기화합니다.

    example::

      dialog.reset()

    """

    self.load(openpibo_models.filepath("dialog.csv"))

  def ngram(self, string, n=2):

    """
    N-gram 값을 구합니다.

    exmaple::

      dialog.ngram('아버지가 방에 들어가셨다.')
      # ['아버지가', '방에', '들어가셨다.']

    :param str string: 분석할 문장
    
    :param int n: N-gram에 사용할 n 값 default:2

    :returns: 문장에서 추출한 N-gram 값

      ``list`` 타입 입니다.
    """

    return [string[i:i+n] for i in range(len(string)-n+1)]

  def diff_ngram(self, string_a, string_b, n=2):

    """
    N-gram 방식으로 두 문장을 비교하여 유사도를 구합니다.

    exmaple::

      dialog.diff_ngram('아버지가 방에 들어가셨다.' '어머니가 방에 들어가셨다.')
      # 0.6923076923076923

    :param str string: 비교할 문장A
    
    :param str string: 비교할 문장B
    
    :param int n: N-gram에 사용할 n 값 default:2

    :returns: N-gram 방식으로 비교한 유사도

      ``float`` 타입 입니다.
    """

    n = min(len(string_a), len(string_b), n)
    a = self.ngram(string_a, n)
    b = self.ngram(string_b, n)

    cnt = 0
    for i in a:
      for j in b:
        if i == j:
          cnt += 1
    return cnt / len(a)

  def get_dialog(self, q, n=2):
    """
    일상대화에 대한 답을 추출합니다.

    저장된 데이터로부터 사용자의 질문과 가장 유사한 질문을 선택해 그에 대한 답을 출력합니다.

    example::

      dialog.get_dialog('나랑 같이 놀자')

    :param str string: 질문하는 문장
    
    :param int n: N-gram에 사용할 n 값 default:2

    :returns: 답변하는 문장 (한글)

      ``string`` 타입 입니다.
    """

    max_acc = 0
    max_ans = []
    for line in self.dialog_db:
      acc = self.diff_ngram(q, line[0], n)

      if acc == max_acc:
        max_ans.append(line)

      if acc > max_acc:
        max_acc = acc
        max_ans = [line]

    return random.choice(max_ans)[1]

  def translate(self, string, target="en"):
    """
    문장을 번역합니다.

    example::

      dialog.translate('안녕하세요! 만나서 정말 반가워요!')
      # "Hi! Nice to meet you!"

    :param str string: 번역할 문장

    :param str target: 번역될 언어(ko, en, ja, fr ...)

    :returns: 번역 된 문장
    """

    if type(string) is not str or type(target) is not str:
      raise Exception(f'"{string}, {target}" must be str type')

    return translate(string, target)

  def get_dialog_dl(self, string):
    """
    일상대화에 대한 답을 추출합니다.(Deep Learning)

    example::

      dialog.get_dialog_ml('나랑 같이 놀자')

    :param str string: 질문하는 문장 (한글)

    :returns: 답변하는 문장 (한글)
    """
    res = requests.get(self.NAPI_HOST + '/dialog', params={'input':string})

    if res.status_code != 200:
      raise Exception(f'response error: {res}')

    if res.json()['result'] == False:
      raise Exception(f'result error: {res.json()}')

    ans, score = [], []
    for item in res.json()['data']:
      ans.append(item['answer'])
      score.append(item['score'])

    return ans[score.index(max(score))]

  def nlp_dl(self, string, mode):
    """
    문장을 분석합니다.(Deep Learning)

    문장을 지정한 모드로 분석합니다.

    example::

      dialog.nlp_ml('안녕하세요. 오늘 매우 즐거워요', 'ner')

    :param str string: 분석할 문장

    :param str mode: 분석 모드 `` (summary|vector|sentiment|emotion|ner|wellness|hate) ``

    :returns: 분석 결과
    """
    #if type(mode) is not str or mode not in ('summary', 'vector', 'sentiment', 'emotion', 'ner', 'wellness', 'hate'):
    #  raise Exception(f'"{mode}" must be (summary|vector|sentiment|emotion|ner|wellness|hate)')

    res = requests.post(self.NAPI_HOST + '/' + mode, params={"sentence":string})

    if res.status_code != 200:
      raise Exception(f'response error: {res}')

    if res.json()['result'] == False:
      raise Exception(f'result error: {res.json()}')

    return res.json()['data']

  #: llama-server 가 뜨는 포트. 실제 값은 systemd 유닛이 정한다
  #: (system/units/llama-server.service). 유닛을 기기에서 떠 오면 여기와 맞출 것.
  LLM_PORT = 50020

  #: 용도별 생성 프리셋. (docs/plan/04-known-issues.md 9)
  #: 형식이 정해진 출력(블록 생성, 분류)에 0.8 은 너무 높다.
  LLM_PRESETS = {
    'chat':   {'temperature': 0.8, 'top_p': 0.95, 'max_tokens': 200},
    'rag':    {'temperature': 0.3, 'top_p': 0.90, 'max_tokens': 300},
    'strict': {'temperature': 0.1, 'top_p': 0.80, 'max_tokens': 200},
  }

  def start_llm(self, port=None, timeout=60):
    """
    LLM 서비스를 시작하고 **뜰 때까지 기다립니다.**

    example::

      dialog.start_llm()

    :param int port: 생략하면 ``LLM_PORT``
    :param int timeout: 기다릴 최대 시간(초). 넘으면 예외
    :returns: 걸린 시간(초)

    .. note::
       ``systemctl start`` 는 바로 돌아온다. 1B Q4 를 올리는 데 수 초 이상 걸리므로
       그 직후에 :meth:`call_llm` 을 부르면 연결 거부가 난다.
       그래서 여기서 ``/health`` 를 폴링한다. (docs/plan/04-known-issues.md 5)
    """

    port = port or self.LLM_PORT
    os.system("systemctl start llama-server")

    url = f"http://127.0.0.1:{port}/health"
    start = time.time()

    while time.time() - start < timeout:
      try:
        if requests.get(url, timeout=2).status_code == 200:
          return round(time.time() - start, 1)
      except requests.RequestException:
        pass
      time.sleep(0.5)

    raise Exception(
      f"LLM 서버가 {timeout}초 안에 뜨지 않았습니다 ({url}). "
      f"`systemctl status llama-server` 를 확인하세요."
    )

  def call_llm(self, prompt=None, system_prompt=None, temperature=None,
               max_tokens=None, preset='chat', stream=True, on_token=None,
               timeout=120, port=None):
    """
    LLM 서버(OpenAI 호환 Chat Completions API)를 호출합니다.

    example::

      dialog.call_llm(prompt="안녕하세요", system_prompt="너는 내 스마트한 비서야")

      # 토큰이 오는 대로 받기
      dialog.call_llm(prompt="...", on_token=lambda t: print(t, end='', flush=True))

    :param str prompt: 사용자의 입력 메시지
    :param str system_prompt: 시스템 프롬프트

      .. note::
         Gemma 3 에는 시스템 롤이 없다. 서버가 첫 user 턴에 합쳐 준다.

    :param str preset: ``chat`` | ``rag`` | ``strict``. 용도별 기본 파라미터
    :param float temperature: 주면 프리셋을 덮어쓴다
    :param int max_tokens: 주면 프리셋을 덮어쓴다
    :param bool stream: 스트리밍 수신 여부
    :param on_token: 토큰 조각마다 부를 함수. ``stream=True`` 일 때만
    :param int timeout: 응답 타임아웃(초)
    :return: 생성된 텍스트

    .. note::
       파이 4 에서 첫 토큰까지 수 초~수십 초다. 스트리밍이 없으면 그동안 완전히
       멈춰 있다. 총 시간이 같아도 체감이 다르다.
       (docs/plan/04-known-issues.md 3, 4)
    """

    port = port or self.LLM_PORT
    # 0.0.0.0 은 바인드 주소지 접속 주소가 아니다. (04-known-issues.md 10)
    url = f"http://127.0.0.1:{port}/v1/chat/completions"

    cfg = dict(self.LLM_PRESETS.get(preset, self.LLM_PRESETS['chat']))
    if temperature is not None:
      cfg['temperature'] = temperature
    if max_tokens is not None:
      cfg['max_tokens'] = max_tokens

    messages = []
    if system_prompt:
      messages.append({"role": "system", "content": system_prompt})
    if prompt:
      messages.append({"role": "user", "content": prompt})

    # 모델명은 llama.cpp 가 모델 하나일 때 무시한다. 서버가 고르게 둔다.
    payload = {"messages": messages, "stream": bool(stream), **cfg}

    try:
      # 타임아웃이 없으면 모델 로딩 중이거나 서버가 뻗었을 때 학생 코드가
      # 영원히 멈춘다. (연결 5초, 응답 timeout 초)
      response = requests.post(url, json=payload, stream=bool(stream),
                               timeout=(5, timeout))
      response.raise_for_status()
    except requests.RequestException as e:
      raise Exception(f"LLM 서버 호출 실패: {e}")

    if not stream:
      data = response.json()
      if isinstance(data.get("choices"), list) and data["choices"]:
        return data["choices"][0]["message"]["content"]
      return data

    chunks = []
    for line in response.iter_lines(decode_unicode=True):
      if not line or not line.startswith("data:"):
        continue
      body = line[5:].strip()
      if body == "[DONE]":
        break
      try:
        delta = json.loads(body)["choices"][0].get("delta", {})
      except (ValueError, KeyError, IndexError):
        continue
      piece = delta.get("content")
      if not piece:
        continue
      chunks.append(piece)
      if on_token:
        on_token(piece)

    return "".join(chunks)

  def stop_llm(self):
    """
    LLM 서비스를 중지합니다.

    example::

      dialog.stop_llm()

    """

    os.system("systemctl stop llama-server")
