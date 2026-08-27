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
ide/               허브 — SPA shell + IDE + 리버스 프록시 (:80)
  proxy.py           /tools /classify /llm 를 같은 origin 으로 중계
  services.py        서비스 켜고 끄고, 뜰 때까지 지켜보기
  system_api.py      /api/system/* — 설정 모달이 쓰는 것들
  envelope.py        응답 봉투 {type, result, data, elapsed_ms, device}
  static/shell.js    탭 라우팅 · 전환 · 설정 · 배지
tools/             체험 도구 (:50000, /tools/ 로 접근)
  launch.py        보드를 보고 아래 둘 중 하나를 띄운다
  run_tools.py     파이보용   — socket.io, 장치/모션/비전/음성/시뮬
  pibrain/         파이브레인용 — REST+SSE, 버튼/LED/카메라/음성/LCD
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

## 화면 — 탭 하나로 다닌다

```
┌─ 상단바 ──────────────────────────────────────────────────────┐
│ ⬤ openpibo [파이브레인]  홈 체험 코딩 학습 대화 │ 앱조작  ●배지 ⚙ │
└───────────────────────────────────────────────────────────────┘
```

**디자인 시스템은 `ide/static/theme.css` 한 파일이다.** 셸과 세 앱이 같은
토큰(`--t-*`)을 보고, 앱들의 옛 변수(`--yellow`, `--teal` …)를 재정의해
한 벌로 갈아입힌다. 셸과 iframe 안 앱의 바탕색이 픽셀 단위로 같아
경계가 보이지 않는다(시험이 이를 지킨다). `tools/static/theme.css`,
`tools/pibrain/static/theme.css`, `classifier/static/theme.css` 는 **복사본**이다 —
원본을 고치고 복사할 것, `test/run.sh` 가 4벌의 동일함을 검사한다.

- 탭 전환에 **페이지 리로드가 없다.** 주소는 `/app/<탭>` 으로 진짜로 남아서
  새로고침해도 그 탭이 열리고, 뒤로가기가 탭 사이를 오간다.
- **⚙ 설정은 어느 탭에서든 열린다** — 시스템 정보 / 와이파이 / 실행 기록 / 전원.
- **상태 배지**가 자원 점유를 항상 드러낸다: 카메라 사용중(어느 화면이 쓰는지까지) /
  코드 실행중 / 모델 로딩중.
- 좁은 화면(교실 태블릿·폰)에서는 상단 탭이 **하단 탭바**로 내려간다.
360px 폰까지 가로 스크롤 없이 들어가고, 노치·홈 인디케이터(`safe-area-inset`)와
모바일 주소창 높이 변화(`100dvh`)를 처리한다.

셸 안(iframe)에서 열리면 앱이 **자기 로고와 제목을 감춘다** — 셸이 이미 금색 바에
로고와 화면 이름을 보여주므로 두 번 나올 이유가 없다. 기능 버튼(메뉴, 전체화면,
언어)은 그대로 있고, 포트로 직접 열면 예전 그대로다.

**단, 셸 안쪽 앱은 별개다.** `tools` 는 자체 모바일 스타일이 있어 폰에서 쓸 만하지만
한 요소가 600px 로 넘쳐 가로 스크롤이 생기고, `user-scalable=no` 로 확대를 막아 뒀다.
`classifier` 는 확인하지 않았다. 셋 다 이번 개편 이전부터 있던 것이다.

프레임워크를 쓰지 않았다. 교실 파이는 인터넷이 없을 수 있어 CDN 을 못 쓰고,
탭 셸 하나에 번들을 얹을 이유가 없다 — 번들이 곧 SD 카드 I/O 다.
바닐라 JS, 빌드 단계 없음.

```bash
bash test/ui/run.sh     # 진짜 브라우저로 셸을 몬다. 하드웨어 불필요
```

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
- **설정 모달의 "초기화"** — 되돌릴 수 없는 동작이라 확인 절차를 따로 설계해야 한다.
  지금 `handle_restore` 는 와이파이까지 되돌리고 바로 종료한다.
- **블록/파이썬 탭 분리** — 현재 IDE 가 둘을 한 화면에 띄운다. 나누려면 IDE 를
  다시 짜야 한다. 같은 페이지를 가리키는 탭 두 개는 나뉜 척만 하는 것이라 안 했다.
- **`/landing`** — 예전 화면. 셸이 실기에서 확인되면 지운다.

로드맵은 [`docs/plan/02-roadmap.md`](docs/plan/02-roadmap.md).

---

## 문서

- 라이브러리 가이드: <https://themakerrobot.github.io/openpibo-os.pibo/build/html/index.html>
- 원 레포: `themakerrobot/openpibo-os.pibo`, `themakerrobot/openpibo-os.pibrain` (아카이브 예정)
