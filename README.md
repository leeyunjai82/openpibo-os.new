# openpibo-os

**파이보(pibo)와 파이브레인(pibrain) 통합 레포.**
두 보드가 같은 코드를 쓰고, 차이는 보드 프로파일 한 곳에만 둔다.

대상 하드웨어: Raspberry Pi 4B **RAM 2GB**, Bookworm, **온디바이스 실행**.
2GB가 모든 판단의 제약이다.

---

## 먼저 읽을 것

**[`docs/plan/03-discarded.md`](docs/plan/03-discarded.md)** — 추정으로 내렸다가
실측으로 뒤집힌 판단들. "안 쓰는 패키지 정리해줘" 같은 지시를 받고 `dlib` 이나
`adafruit_ssd1306` 을 지우려 들기 전에 반드시 읽는다. 둘 다 **현역**이다.

그 다음 [`docs/plan/README.md`](docs/plan/README.md) 가 나머지 문서의 읽는 순서를 안내한다.

---

## 이 기기가 어느 보드인가

```bash
bash system/set_board.sh                # 확인
sudo bash system/set_board.sh pibrain   # 설정
```

`/home/pi/.board` 한 줄이 전부다. 코드는 전부 이 값을 통해서만 보드를 안다.

```python
from openpibo.board import BOARD

BOARD.name                 # 'pibo' | 'pibrain'
BOARD.audio.card           # 'Headphones' | 'MAX98357A'
BOARD.camera.transform     # 'flip_both' | 'rot90ccw'
BOARD.features.has_legs    # True | False
```

값의 출처는 [`openpibo/profiles/pibo.toml`](openpibo/profiles/pibo.toml) 과
[`pibrain.toml`](openpibo/profiles/pibrain.toml) 이다.

> **`if board == 'pibo'` 를 새로 쓰지 말 것.**
> 그렇게 시작해서 두 레포로 갈라졌다. 값이 모자라면 프로파일에 키를 추가한다.

### 두 보드가 실제로 다른 곳

| | 파이보 | 파이브레인 |
|---|---|---|
| 디스플레이 | SSD1306 128x64 흑백 | ILI9341 240x320 컬러 |
| 오디오 | Headphones | MAX98357A |
| 마이크 | 16000 / S32_LE | 44100 / S16_LE |
| 카메라 | 640x480 (상하좌우 반전) | 480x640 (반시계 90도) |
| MCU | ATmega328P (`/dev/ttyS0`) | 없음 |
| 눈 / LED | MCU 경유 눈 LED | GPIO 12 WS2812 직결 |
| 버튼 | MCU 경유 | GPIO 4, 17, 27, 26 |
| 다리 | 있음 (`motion.move`) | 없음 |

블록 툴박스도 같은 플래그로 걸러진다 —
파이브레인에서는 모션 카테고리가 통째로 안 보인다.
(`ide/static/board_filter.js`)

---

## 레포 구조

```
openpibo/          라이브러리 (wheel 로 배포)
  board.py           ← 보드 분기의 유일한 지점
  profiles/*.toml    ← 보드 상수
system/            부팅할 때 도는 것들 + systemd 유닛   → system/README.md
ide/               허브 — 블록/파이썬 IDE + 리버스 프록시 (:80)
  proxy.py           /tools /classify /llm 를 같은 origin 으로 중계
  services.py        서비스 켜고 끄고, 뜰 때까지 지켜보기
tools/             체험 도구 (:50000, /tools/ 로 접근)
classifier/        학습 도구 (:50010, /classify/ 로 접근)
examples/pibo/     보드별 블록 예제
examples/pibrain/
requirements/      의존성 명세                        → requirements/README.md
docs/plan/         통합·개편 계획                     → docs/plan/README.md
tools/measure/     실측 스크립트                      → tools/measure/README.md
test/               하드웨어 없이 도는 시험 (bash test/run.sh)
```

---

## 설치 / 빌드

```bash
# 라이브러리 wheel 만들기 (개발 머신)
bash system/build_wheel.sh

# 기기에 설치 (wheel + systemd 유닛 + 보드 확인)
sudo bash system/install.sh

# 의존성까지 새로 (기기)
/home/pi/.pyenv/bin/pip install -r requirements/device-all.txt
```

PyPI 에 올리지 않는다. `dist/*.whl` 을 기기로 옮겨 설치한다.

### 개발 머신에서 확인

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements/base.txt -r requirements/server.txt

mkdir -p .tmp
OPENPIBO_HOME=$PWD/.tmp OPENPIBO_BOARD=pibrain python3 -c \
  "from openpibo.board import BOARD; print(BOARD.name, BOARD.label)"

bash test/run.sh                           # 시험 전부 (하드웨어 불필요)
bash requirements/check.sh base server     # 명세와 환경이 맞는지
```

`requirements/device.txt` 와 `vision.txt` 는 **라즈베리파이가 아니면 대부분
설치되지 않는다** (picamera2, RPi.GPIO, tflite-runtime). 기기에서 확인한다.

---

## 하나의 주소로 다닌다

예전에는 카드를 누르면 3초 기다렸다가 다른 포트를 **새 창**으로 열었다.
세션도 뒤로가기도 끊겼고, 3초는 근거 없는 추측이었다.

```
:80  허브
  ├─ /              랜딩 + IDE
  ├─ /tools/*    ──중계──▶ :50000
  ├─ /classify/* ──중계──▶ :50010
  └─ /llm/*      ──중계──▶ :50020
```

전환할 때 진행 상태를 SSE 로 흘려보낸다.

```
starting → active(유닛이 떴다) → ready(포트가 응답한다)
```

`systemctl is-active` 는 **uvicorn 이 포트를 잡기 전에 이미 active** 를 준다.
그래서 두 단계를 나눠 보고, `ready` 에서만 화면을 넘긴다.
몇 초가 걸리든 그대로 보여준다 — 지연을 숨기지 않는다.

**프로세스 통합은 아니다.** 2GB라 셋이 동시에 못 떠서 systemd가 서로를 죽이는
구조는 그대로다. origin만 합쳤다. 나중에 프로세스를 합쳐도 **프론트는 안 바뀐다.**

---

## 아직 안 된 것

- **`system/units/llama-server.service` 가 비어 있다.**
  `-c`(컨텍스트) 값이 코드 어디에도 없다. RAG 청크 상한을 정하는 숫자라
  추측으로 채우지 않았다.
  → `sudo bash system/units/capture-from-device.sh`
- **실측이 안 됐다.** `bash tools/measure/run.sh` 후
  `docs/plan/01-measurements.md` A절 채우기.
- **두 보드 실기 확인.** 부팅 화면 / LED / 카메라 1프레임.
- **프록시 실기 확인.** 세 서비스가 `/tools/` `/classify/` `/llm/` 너머로 도는지.
  특히 tools 의 socket.io 와 classifier 의 카메라 스트림.
- **2단계 SPA shell** — 탭 전환, 설정 모달. 아직 시작 안 함.

로드맵은 [`docs/plan/02-roadmap.md`](docs/plan/02-roadmap.md).

---

## 문서

- 라이브러리 가이드: <https://themakerrobot.github.io/openpibo-os.pibo/build/html/index.html>
- 원 레포: `themakerrobot/openpibo-os.pibo`, `themakerrobot/openpibo-os.pibrain` (아카이브 예정)
