# requirements/ — 의존성 명세

`test/` 에 `requirements.txt`, `.bak`, `-260309`, `.260313`, `.tf`, `.sphnix` 여섯 변종이
있었고 어느 게 진짜인지 알 수 없었다. 310줄인데 실제 import 는 40개 남짓 —
의존성 명세가 아니라 `pip freeze` 덤프였다 (`docs/plan/04-known-issues.md` 20).

여기서는 **코드가 실제로 import 하는 것**만 적는다.
버전 고정본은 `frozen/` 에 따로 둔다.

## 파일

| 파일 | 언제 쓰나 | 기기에 들어가나 |
|---|---|---|
| `base.txt` | 순수 파이썬 + 어디서나 설치되는 것 | O |
| `device.txt` | 라즈베리파이 하드웨어 (GPIO, 카메라, SPI) | O |
| `vision.txt` | 비전/음성 모델 런타임 | O |
| `server.txt` | 허브·IDE·tools·classifier 웹 서버 | O |
| `models.txt` | openpibo_*_models 데이터 패키지 | O |
| `optional.txt` | 없어도 대부분 동작. 있으면 기능이 늘어난다 | 선택 |
| `build.txt` | wheel 빌드 / 모델 변환 도구 | **X** |
| `docs.txt` | Sphinx 문서 빌드 | **X** |
| `dev.txt` | 위를 전부 + 시험 도구 | **X** |
| `frozen/pibo-260827.txt` | 마지막으로 동작이 확인된 기기의 `pip freeze` 원본 | 참고용 |

`-r` 로 엮여 있다. 기기 전체는:

```bash
pip install -r requirements/device-all.txt
```

## 새 가상환경에서 확인하기

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements/base.txt -r requirements/server.txt
OPENPIBO_HOME=$PWD/.tmp OPENPIBO_BOARD=pibo python3 -c "import openpibo.board as b; print(b.BOARD.name)"
```

`device.txt` / `vision.txt` 는 **라즈베리파이가 아니면 대부분 설치되지 않는다.**
picamera2, RPi.GPIO, rpi_ws281x, tflite-runtime 이 그렇다.
PC 에서는 `base + server` 까지만 확인하고, 나머지는 기기에서 본다.

## 왜 이 패키지가 여기 있나 — 지우기 전에 읽을 것

`docs/plan/03-discarded.md` 를 먼저 볼 것. 아래는 그중 자주 오해받는 것들이다.

- **dlib** — 얼굴 **인식(구분)** 의 핵심이다. 68점 랜드마크와 128차원 임베딩이
  전부 dlib 이다. `facedb` 가 여기 물려 있어 빼면 **등록된 얼굴이 전부 무효**가 된다.
  "import 가 안 보인다"는 잘못된 grep 결과였다.
- **adafruit-circuitpython-ssd1306** — 구형이 아니다. **파이보 현역 디스플레이**다.
- **adafruit-circuitpython-rgb-display** — 파이브레인 ILI9341 + 보존용 ST7735 둘 다.
- **tensorflow** — 디스크 1위(1.1G)지만 상시 import 가 아니라 RAM 영향이 거의 없다.
  급하지 않다. 로드맵 5단계에서 OpenVINO 백본으로 갈아타며 빠진다.
- **ultralytics / torch** — RAM 1위다(상시 import, 400MB). 제거 대상이지만
  로드맵 7단계다. 지금 빼면 YOLO 가 안 돈다.

## 제거한 것과 이유

`frozen/pibo-260827.txt` 310줄 중 이 명세에 없는 것들.

| 뺀 것 | 이유 |
|---|---|
| `opencv-python` | `opencv-contrib-python` 과 **같은 `cv2` 네임스페이스**를 제공한다. 둘 다 깔면 버전이 어긋날 때 깨진다 (04-known-issues 11). contrib 만 남긴다 |
| `rpi-lgpio` | `RPi.GPIO` 의 드롭인 대체품이라 **같은 `RPi.GPIO` 모듈**을 제공한다. 위와 같은 문제 |
| `openvino-dev` | 메타패키지(본체 없음, dist-info 356K). 변환 도구라 기기에 필요 없다 → `build.txt` |
| `onnx`, `onnxslim`, `tensorflowjs`, `tensorflow-hub` | 모델 변환 도구. 기기에서 추론에는 안 쓴다 → `build.txt` |
| mecab 계열, `konlpy`, `jamo` | 코드 import **0건**. 유일한 흔적이 `speech.py` 의 주석 `#self.mecab = Mecab()` |
| `pandas`, `scipy`, `matplotlib`, `seaborn`, `sympy`, `nltk`, `transformers` | import 0건 |
| `numba`, `llvmlite`, `boto3`, `botocore`, `google-*` | import 0건. 다른 패키지가 끌고 온 것 |
| `h5py`, `keras`, `tf-keras`, `tensorflow-estimator` | tensorflow 가 필요한 만큼 알아서 끌어온다 |

**주의**: `openvino-dev` 가 의존성으로 `scipy`, `opencv-python` 등을 끌어왔을 수 있다.
`pip show openvino-dev | grep Requires` 로 확인하고 **openvino-dev 를 먼저 빼야**
그것들을 안전하게 지울 수 있다. 순서가 있다 (`00-decisions.md` 7.5).

## 기기에서 검증하는 법

`frozen/` 의 freeze 와 이 명세가 어긋나는지 본다.

```bash
bash requirements/check.sh
```

빠진 것(import 하는데 안 깔린 것)과 남는 것(깔렸는데 명세에 없는 것)을 보여준다.
