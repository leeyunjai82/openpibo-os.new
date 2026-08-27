# 04. 발견된 문제

코드 검토 중 발견한 버그와 개선점.
**리팩터링 전에 높음 등급을 먼저 고칠 것.** 리팩터링 중에 섞이면 원인 추적이 어려워진다.

최종 갱신: 2026-08-27

> **상태 표시**
> `[고침]` 이 붙은 항목은 코드가 수정됐다. 커밋 메시지에 어느 항목인지 적어 뒀다.
> `[확인함]` 은 들여다봤지만 고치지 않기로 한 것 — 이유를 항목에 적었다.
> 표시가 없으면 그대로 남아 있는 것이다.

---

## 높음 — **7건 전부 [고침]**

### 0. `socket.io.min.js` — `navigator.userAgent` 가 통째로 `userAgentData` 로 치환돼 있음  `[고침]`

세 앱이 같은 번들을 쓰고(md5 동일), 그 안에 `navigator.userAgent` 가 **0 번**,
`navigator.userAgentData` 가 **19 번** 나온다. 잘못된 일괄 치환의 흔적이다.
`userAgentData` 는 문자열이 아니라 `NavigatorUAData` 객체라 `.toLowerCase()` 에서 던진다.

```js
"undefined"!=typeof navigator && navigator.userAgentData && navigator.userAgentData.toLowerCase()...
//                               ^^^ 객체라 truthy            ^^^ 여기서 TypeError
```

번들 평가 중에 던지므로 `io` 가 아예 정의되지 않는다. **socket.io 가 통째로 안 뜬다.**
IDE 는 `socket.on('init')` 로 블록/파이썬 중 하나를 감추는데 그게 안 와서
두 편집기가 위아래로 겹쳐 보이고, tools 는 `handleMenu("device")` 까지 못 가서
탭 5 개가 한꺼번에 펼쳐진다. "CSS 가 깨진" 것처럼 보이지만 CSS 문제가 아니다.

**왜 여태 안 걸렸나**: `navigator.userAgentData` 는 크로미움 계열의 **보안 컨텍스트**
(https 또는 localhost)에서만 정의된다. 교실에서 쓰던 `http://192.168.x.x:50000` 은
보안 컨텍스트가 아니라 `undefined` → 앞의 `&&` 에서 끊겨 조용히 넘어갔다.
파이어폭스/사파리에는 이 속성 자체가 없다. **https 를 켜거나 localhost 로 여는 순간
전부 죽는다.** 셸을 붙이면서 localhost 로 열어 보다가 드러났다.

세 벌 다 `navigator.userAgent` 로 되돌렸다. `test/test_tools_launch.py` 가 재발을 막는다.

### 0-1. IDE — 편집기 초기 상태가 socket 응답에 매달려 있음  `[고침]`

`blocklyDiv` 와 `codeDiv` 둘 다 아무 초기 상태 없이 그려지고, `codetype` 전환 버튼도
`checked` 없이 시작한다. 어느 쪽을 감출지는 `socket.on('init')` 이 와야 정해진다.
뒤쪽이 늦거나(0번처럼) 안 오면 **두 편집기가 겹쳐 보인다.**

템플릿에서 블록을 기본으로 정했다 — `<button name="block" class="checked">` +
`<div id="codeDiv" style="display:none">`. `init` 이 오면 지금까지처럼 덮어쓴다.
파일을 안 열었을 때의 기본값도 블록이라(`index.js` 227~232) 뜻이 바뀌지 않는다.


### 1. `run_ide.py` — `raise JSONResponse` → TypeError  `[고침]`

`download_item()`:
```python
if not os.path.exists(full_path):
    raise JSONResponse(content={'error':"파일 또는 폴더를 찾을 수 없습니다."}, status_code=404)
```

`JSONResponse`는 `Exception`이 아니다. `raise`하면 TypeError가 난다.
**파일이 없을 때 404 대신 500이 난다.** `return`이어야 한다.

같은 함수 안에 하나 더 있다 (`올바른 파일 또는 폴더가 아닙니다`).

### 2. `run_ide.py` — `handle_restore`의 `sio` NameError  `[고침]`

```python
except Exception as e:
    await sio.emit('update', {'dialog': f'초기화 오류: {str(e)}'}, room=sid)
```

`sio`가 정의되지 않았다. `app.sio`여야 한다.
**초기화가 실패하면 에러 메시지 대신 예외가 삼켜진다.**

### 3. `speech.py` `call_llm()` — 스트리밍 없음  `[고침]`

```python
payload = {
  "model": "llm-model.gguf",
  "messages": messages,
  "temperature": temperature,
  "top_p": 0.95,
  "max_tokens": max_tokens
}
```

`stream: true`가 없어 완전 블로킹이다.
파이 4에서 첫 토큰까지 수 초~수십 초인데 그동안 완전히 멈춰 있다.

**같은 총 시간이어도 체감이 완전히 다르다.** 스트리밍은 필수다.

### 4. `speech.py` `call_llm()` — 타임아웃 없음  `[고침]`

```python
response = requests.post(url, json=payload)
```

모델 로딩 중이거나 서버가 뻗으면 **무한 대기**. 학생 코드가 그대로 멈춘다.

### 5. `speech.py` `start_llm()` — 모델 로딩을 안 기다림  `[고침]`

```python
os.system(f"systemctl start llama-server")
print("Connect to http:{Device IP}:50020 for LLM Web-UI")
```

`systemctl start` 직후 리턴한다. 1B Q4 적재에 수 초 이상 걸리므로
**바로 `call_llm()`을 부르면 연결 거부**가 난다. 헬스체크 폴링이 필요하다.

(참고: `print`의 f-string이 아니라 그냥 문자열이라 `{Device IP}`가 그대로 출력된다)

---

## 중간

### 6. `run_ide.py` — 경로 보호가 문자열 `in` 매칭  `[고침]`

```python
def is_protect(p):
    for protected_path in protectList:
        if protected_path in p:
            return True
```

`../` 정규화가 없다. `/home/pi/code/../openpibo-os/...` 같은 경로가 통과한다.

수업용 로컬 기기라 위협 모델은 낮지만,
`os.path.realpath()` 정규화 후 `os.path.commonpath` 비교로 바꿨다.
`protectList` 에 `'/home/pi/openpibo-'` 같은 접두사 항목이 있어 startswith 도 함께 본다.

### 7. `run_ide.py` — 전역 가변 상태

```python
PATH = '/home/pi/code'
codeText = ''
codePath = ''
```

socket.io 세션 구분 없이 모듈 전역이다.
**교실에서 두 명이 같은 파이보에 붙으면 서로의 파일 경로를 덮어쓴다.**
세션별 dict로 바꿀 것.

### 8. `run_ide.py` — CORS 설정이 스펙상 무효

```python
allow_origins=["*"],
allow_credentials=True,
```

이 조합은 브라우저가 거부한다.
**단일 origin으로 합치면(1단계) CORS 미들웨어 자체가 불필요해진다.**

### 9. `call_llm()` — 기본 파라미터가 용도에 안 맞음  `[고침]`

- `temperature=0.8`, `top_p=0.95` — 블록 생성처럼 형식이 정해진 출력에는 너무 높다.
  **0.1~0.3이 적절.** GBNF 문법 제약을 걸면 더 낮춰도 된다
- `max_tokens=100` — RAG 답변에는 짧을 수 있다

**용도별 프리셋이 필요하다.**

### 10. `call_llm()` — `http://0.0.0.0:50020`  `[고침]`

`0.0.0.0`은 바인드 주소지 접속 주소가 아니다.
리눅스에서 우연히 동작하지만(127.0.0.1로 해석) 잘못된 코드다.

### 11. `opencv-python` + `opencv-contrib-python` 중복 설치  `[고침]`

같은 `cv2` 네임스페이스를 두 패키지가 제공한다.
**버전이 어긋나면 깨진다.** contrib 하나만 남길 것.

새 명세(`requirements/vision.txt`)에는 contrib 만 넣었고,
`requirements/check.sh` 가 둘 다 깔려 있으면 `[겹침]` 으로 잡는다.

**같은 종류의 문제가 하나 더 있었다**: `rpi-lgpio` 와 `RPi.GPIO` 가 둘 다 깔려 있다.
rpi-lgpio 는 RPi.GPIO 의 드롭인 대체품이라 **같은 `RPi.GPIO` 모듈**을 제공한다.
check.sh 가 이것도 잡는다.

기기에서 실제로 지우는 것은 아직 안 했다. `00-decisions.md` 7.5 의 순서를 지킬 것
(openvino-dev 를 먼저 빼야 그게 끌어온 것들을 안전하게 지울 수 있다).

### 12. systemd 유닛이 레포에 없음  `[고침 — llama-server 1건 남음]`

`init`이 `booting.service`, `ide.service`를 참조하는데
유닛 파일은 기기의 `/etc/systemd/system/`에만 있다.

**이미지 재현이 불가능하다.** `llama-server.service`의 `-c` 값도 여기 있어서
현재 컨텍스트 설정을 코드에서 알 수 없다.

→ `system/units/` 에 넣고 `system/units/install.sh` 가 심볼릭 링크한다.
`init` 이 링크가 없으면 자동으로 건다.

booting / ide / tools / classify 4개는 **코드에서 재구성**했다. 실물과 다를 수 있다.
`llama-server.service` 는 **재구성하지 않았다** — `-c` 값을 추측할 수 없고,
그게 RAG 청크 상한을 정하는 숫자다.

```bash
sudo bash system/units/capture-from-device.sh   # 기기 실물을 레포로
git diff system/units/                          # 재구성본과 비교
```

떠 오기 전까지 `install.sh` 는 `llama-server.service` 만 건너뛴다.

---

## 낮음

### 13. `run_ide.py` — 세 엔드포인트가 모두 함수명 `classifier`  `[고침]`

```python
@app.get('/tools')
async def classifier(enable: str): ...

@app.get('/classifier')
async def classifier(enable: str): ...

@app.get('/llm')
async def classifier(enable: str): ...
```

FastAPI는 경로로 라우팅하니 동작은 하지만 **스택트레이스를 못 읽는다.**

### 14. `speech.py` `start_llm(port=50020)` — 인자가 안 쓰임  `[고침]`

시그니처에 `port`가 있는데 함수 본문에서 무시된다.
실제 포트는 유닛 파일이 정한다.

인자를 지우거나, 유닛을 `Environment=` 방식으로 바꿔 인자가 먹게 하거나 택일.

### 15. `call_llm()` — 모델명 하드코딩  `[고침]`

```python
"model": "llm-model.gguf",  # 모델명 (환경에 맞게 수정)
```

주석에 "환경에 맞게 수정"이라 되어 있다.
llama.cpp는 모델이 하나면 이 필드를 무시하지만 정리 대상.

### 16. `vision_detect.py` — 모델 경로 불일치

```python
145: self.object_detector = YOLO("/home/pi/.model/object/yolo26s.onnx", task="detect")
233: def load_object_model(self, modelpath='/home/pi/.model/object/yolo11s.onnx'):
```

생성자는 `yolo26s`, 기본값은 `yolo11s`. **의도인지 확인 필요.**
3단계에서 yolo11s로 통일하면 해소된다.

### 17. `urllib2` import — Python 2 모듈  `[확인함 — 안 고침]`

import 목록에 `urllib2`가 있다. Python 3에는 없는 모듈이므로
**어딘가 죽은 코드가 있다.** 실행되지 않는 경로일 것.

**확인 결과**: `openpibo/modules/speech/mtranslate.py` 의
`if sys.version_info[0] < 3:` 분기 안이다. 파이썬 3에서는 실행되지 않는다.
죽은 코드가 맞지만 **vendored 외부 코드(MIT)** 라 손대지 않았다.

### 18. `speech.py` `analysis()` — 클라우드 호출

```python
res = requests.post(self.NAPI_HOST + '/' + mode, params={"sentence":string})
```

`https://oe-napi.circul.us`를 호출한다. 요약·감정·NER 등이 온디바이스가 아니다.

**온디바이스 전제와 충돌.** 의도된 잔존인지 정리 대상인지 확인 필요.
Gemma 3 1B으로 대체 가능한 항목(summary, sentiment)과
어려운 항목(vector, ner)이 섞여 있다.

### 19. `pibrain/openpibo/pibo_graphics.py` — `__main__` 예제 잔류  `[고침]`

파일 하단에 실행용 예제가 남아 있다. 0단계 통합 시 정리.

**pibo 기준으로 병합해서 애초에 딸려오지 않았다.** 덤으로 이 파일의
첫 줄 docstring 이 "USB UART 통신을 위한 클래스"라고 잘못 적혀 있던 것도 고쳤다.

### 20. `test/requirements*.txt` 6개 변종  `[고침]`

`requirements.txt`, `.bak`, `-260309`, `.260313`, `.tf`, `.sphnix`.
**어느 게 진짜인지 알 수 없다.** 310줄인데 실제 import는 40개 남짓 —
의존성 명세가 아니라 `pip freeze` 덤프다.

`setup.py`의 `install_requires`는 `openpibo_*_models` 4개만 남기고 전부 주석 처리.

---

## 확인 필요 (버그일 수도 아닐 수도)

### 21. `Oled7735`의 `bl=cs_pin`  `[확인함 — 주석만]`

```python
self.oled = st7735.ST7735S(spi, ..., cs=cs_pin, bl=cs_pin, dc=dc_pin, ...)
```

**백라이트를 CS 핀에 물려 놨다.** 의도가 아니라면
SPI 트랜잭션마다 백라이트가 흔들린다.

생성자가 `w=128, h=64`인데 ST7735S는 통상 128×160 또는 80×160인 것도 함께 확인.

미사용 클래스이므로 급하지 않지만, **소스에 "미검증" 주석을 남길 것.**
나중에 다른 장치 테스트할 때 기억나지 않는다.

**클래스 docstring 과 생성자에 경고를 박아 뒀다.** 세 가지(bl=cs_pin, w/h 128x64,
rst=None)를 명시하고 "확인 없이 다른 보드 프로파일로 옮기지 말 것"이라고 적었다.
동작은 손대지 않았다.

### 22. `Face.__init__()` — 모델 6개 무조건 로드

버그는 아니지만 2GB에서 가장 큰 구조적 문제다.

```
dlib shape_predictor_68
dlib face_recognition_resnet
OpenVINO face-detection-retail-0004
OpenVINO age-gender-retail-0013
OpenVINO emotions-retail-0003
MediaPipe face_landmarker.task
```

얼굴 위치만 알고 싶어도 전부 올라온다.
**올바른 패턴이 같은 파일에 이미 있다**:
`vision_detect.py`의 `self.hand_gesture_recognizer = None` + `load_hand_gesture_model()`.

→ 로드맵 6단계.
