# 00. 확정 사항

openpibo-os 통합 및 개편 계획의 결정 사항. 각 항목에 **근거**를 함께 적는다.
근거 없이 뒤집지 말 것. 뒤집으려면 `01-measurements.md`의 실측으로 반박할 것.

최종 갱신: 2026-08-27

---

## 0. 전제

| 항목 | 값 |
|---|---|
| 하드웨어 | Raspberry Pi 4B **RAM 2GB** (파이보 / 파이브레인 공통) |
| OS | Raspberry Pi OS Bookworm |
| 실행 | **온디바이스**. 클라우드 API 전제 금지 |
| 파이썬 | `/home/pi/.pyenv/bin/python3` (3.11) |
| 모델 경로 | `/home/pi/.model/` |
| 코드 경로 | `/home/pi/openpibo-os/` |
| 디스크 | 28G 중 16G 사용, **12G 여유** |

**2GB가 모든 판단의 제약이다.** 어떤 결정이든 "AI PC에서는 되는데"는 근거가 아니다.

---

## 1. 레포 통합

### 1.1 통합한다

**결정**: `openpibo-os.pibo` + `openpibo-os.pibrain` → `openpibo-os` 단일 레포.

**근거**: 두 레포 실측 차이의 대부분이 로직이 아니라 **보드 상수**다.

| 파일 | diff 라인 | 성격 |
|---|---|---|
| `openpibo/device.py` | **0** | 완전 동일. 이미 `Device` / `DeviceByPiBrain` 보유 |
| `openpibo/audio.py` | 10 | `Headphones` vs `MAX98357A`, 샘플레이트 — 상수 |
| `openpibo/vision_camera.py` | 7 | `640x480 flip` vs `480x640 rot90ccw` — 상수 |
| `openpibo/oled.py` | 276 | 핀 상수 + pibo에만 `Oled7735` 존재 |
| `openpibo/pibo_graphics.py` | 118 | `320x240` vs `240x320` + pibrain에 `__main__` 잔류 |
| `openpibo/motion.py` | 44 | pibo에만 `move(vx, vy)` — **정당한 차이(다리)** |
| `ide/customblock_*.js` | 996 | 블록 정의 — 실질 차이 |
| `tools/` | ~4000 | pibo=socket.io / pibrain=REST+SSE — **아키텍처가 갈라짐** |

`device.py`가 이미 보드 분기 패턴(`Device` / `DeviceByPiBrain`)을 갖고 있다.
**패턴은 있는데 안 쓰고 있었다.** pibrain 쪽은 `Oled7735`를 선택하지 않고 삭제해 버렸다.

### 1.2 기준 레포는 pibo

**근거**: `Oled7735` 클래스가 pibo에만 있다. pibrain을 기준으로 병합하면 **보존하기로 한 클래스가 사라진다**.

### 1.3 분기 지점은 `openpibo/board.py` 하나

프로파일은 `/home/pi/.board` 파일 또는 `config.json`의 `board` 키로 결정.

```
PROFILES = {
  'pibo':    { audio_card, mic_rate, mic_format, cam_size, cam_transform,
               display, display_size, display_rst, has_legs, has_mcu },
  'pibrain': { ... },
}
```

**블록 툴박스도 같은 플래그로 필터링한다.** 서버가 `window.__BOARD__`를 주입하고,
`has_legs`가 거짓이면 모션 카테고리를 빼는 식. 이러면 "같은 수정 2번"이 사라지고
정당한 차이(`motion.move`)만 남는다.

### 1.4 `tools/`는 지금 병합하지 않는다 — 대신 보드가 고른다

**근거**: 2단계 SPA shell에서 어차피 새로 만든다. 지금 무리해서 병합할 이유가 없다.

**갱신 (2026-08-27)**: 병합은 그대로 미룬다. 다만 **어느 쪽을 띄울지는 보드가 고른다.**

미루기만 했더니 파이브레인에서 체험 화면이 파이보 것으로 떴다. 파이보 화면의
"모션" 탭은 다리 12축 서보가 있어야 뜻이 있는데 파이브레인에는 다리가 없다.
아이가 명령을 보내 놓고 아무 일도 안 일어나는 것을 보면 그건 "미룬 것"이 아니라
**고장난 것**이다. 시험 한 번 하기 전에 이미 막힌다.

    tools/launch.py   보드 -> 폴더 (이것 하나가 갈림길이다)
      pibo    -> tools/            socket.io,  :50000
      pibrain -> tools/pibrain/    REST + SSE, :50000

`tools/legacy_pibrain/` 은 `tools/pibrain/` 으로 이름을 바꿨다 — 더 이상
"보존만 하는 옛 코드"가 아니라 파이브레인의 현역 화면이다. 셸 뒤에서 열리도록
정적 경로·`__BASE__`·`html.embedded`·`theme.css` 만 맞췄고, 기능은 손대지 않았다.

포트는 둘 다 50000 이다 (파이브레인 원본은 50040 이었다). 셸 프록시가 `/tools/` 를
50000 으로 보내므로 어느 보드든 셸에서는 같은 주소다.

### 1.5 기존 레포는 아카이브

바로 지우지 않는다. 통합 과정에서 빠뜨린 것을 대조할 원본이 필요하다.

---

## 2. 하드웨어 / 드라이버

### 2.1 SSD1306 — 유지

**근거**: `oled.py`의 기본 클래스 `Oled`가 실제로 `ssd1306.SSD1306_SPI`를 쓴다.
파이보 현역 디스플레이(128×64 흑백). `booting.py`가 이걸 사용한다.

### 2.2 ILI9341 — 유지

**근거**: `OledByPiBrain`이 사용. 파이브레인 2.4인치 240×320.

### 2.3 ST7735 — **소스 보존**

**결정**: 사용하지 않지만 `Oled7735` 클래스와 `adafruit_rgb_display.st7735` 의존을 남긴다.

**근거**: 나중에 다른 장치 테스트에 쓸 수 있다.

**주의**:
- pibrain 레포에는 이 클래스가 없다. **pibo 기준으로 병합해야 살아남는다.**
- 생성자가 `w=128, h=64`인데 ST7735S는 통상 128×160 또는 80×160
- `bl=cs_pin` — 백라이트를 CS 핀에 물려 놨다. **의도인지 미검증.**
  의도가 아니면 SPI 트랜잭션마다 백라이트가 흔들린다
- `rst_pin = None`

→ **소스에 "미검증" 주석을 남길 것.** 나중에 기억나지 않는다.

### 2.4 확인 필요 — 추측 금지

다음은 데이터시트/실기로 확정하기 전까지 프로파일에 하드코딩하지 않는다.

- `rst_pin`: pibo는 `None`, pibrain은 `board.D24`
- `bl=cs_pin` 의도 여부 (위 2.3)
- WS2812 데이터 라인 레벨 시프터 유무 (Pi GPIO 3.3V 출력 → WS2812 5V 로직)
- LCD 백라이트 + MAX98357A 스피커 + WS2812 동시 최대 부하 시 3.3V/5V 레일 여유
- CMA 예약량 (`/proc/meminfo`의 `CmaTotal`)

---

## 3. 비전 모델 / 런타임

### 3.1 YOLO — yolo11 계열로 통일

| 용도 | 현재 | 변경 |
|---|---|---|
| detect | `yolo26s.onnx` | **`yolo11s`** |
| pose | movenet Lightning (tflite) | **`yolo11s-pose`** |

**근거**:
- 현재 `yolo26s`가 "쓸 만하다" → 급수를 내릴 이유 없음. **s 유지**
- 계열 통일 시 vapi-od(yolo11m)와 **COCO 17점 키포인트 규격이 동일** → 특징 벡터 호환 전제 충족
- COCO 80 클래스 그대로 → 라벨 매핑/인덱스 무변경.
  vapi-od의 `COCO_KO` 한글 라벨 80종을 그대로 재사용 가능
- 속도가 모자라면 **모델 급수보다 `imgsz`를 먼저 줄인다** (640→320은 연산량 1/4,
  n↔s 차이 3배보다 지렛대가 크다)

**부수 효과**: 현재 불일치가 해소된다.
- `vision_detect.py:145` → `yolo26s.onnx`
- `vision_detect.py:233` `load_object_model()` 기본값 → `yolo11s.onnx`

### 3.2 movenet — 제거 (단, 마지막에)

**결정**: 최종 목표는 제거. 3단계에서 yolo11s-pose와 잠깐 공존, **4단계에서 제거**.

**근거**:
- 같은 COCO 17점을 뽑는 모델을 둘 들고 있을 이유가 없다
- 결과가 "완전히 틀린" 게 아니라 **"조금 어긋난"** 형태로 달라서,
  학습은 movenet / 추론은 yolo로 섞이면 원인 추적이 매우 어렵다
- movenet Lightning은 **단일 인물**. yolo-pose는 다중 인물 → "가장 큰 사람" 선택 가능
- movenet 래퍼는 `self._crop_region`을 프레임 간 유지한다.
  **학습 사진을 연속 처리할 때 이전 crop이 남아 오작동한다** (`reset_crop_region=True` 필요).
  yolo-pose로 가면 이 함정이 사라진다

**단, 3단계 실측에서 yolo11s-pose가 파이 4에서 감당이 안 되면 movenet 유지로 되돌린다.**
그 경우 vapi-od 특징 호환은 포기한다.

**제거 시 딸려오는 것**:
- `openpibo/modules/pose/` (movenet.py, data.py, utils.py)
- `openpibo_detect_models`의 `movenet_lightning.tflite`
- `detect_pose()` 반환 타입 변경 → **`Person` NamedTuple 어댑터를 넣어 기존 예제·블록 코드 보호**
- `detect_pose_vis()`는 어댑터로 그대로 살릴 수 있음
- `tflite_runtime`은 **남긴다** (`TeachableMachine` 이관 예정)

### 3.3 dlib — 유지

**근거**: **얼굴 인식(구분)의 핵심**이다. 제거 대상이 아니다.

| 용도 | 호출 | 사용 메서드 |
|---|---|---|
| 68점 랜드마크 | `dlib.shape_predictor` | `landmark_face()` |
| **얼굴 임베딩 128-d** | `dlib.face_recognition_model_v1` | `train_face()`, `recognize()` |
| 박스 변환 | `dlib.rectangle` | 3곳 |
| 객체 추적 | `dlib.correlation_tracker` | `vision_detect.py` |

얼굴 **탐지**는 이미 dlib에서 떠났다 (`get_frontal_face_detector()` 주석 처리 →
OpenVINO `face-detection-retail-0004`). 랜드마크와 임베딩만 dlib에 남긴 합리적 구조.

`facedb`(128차원 벡터 pickle)가 물려 있어 **교체 시 기존 등록 얼굴이 전부 무효화된다.**

### 3.4 face-reidentification 교체 — 장기 과제, 지금은 아님

**결정**: 지금 하지 않는다. **경계만 맞춰둔다.**

가능성은 확인됨:

| | 현재 (dlib) | 교체 후 |
|---|---|---|
| 모델 | ~122 MB (**미실측**) | 5~6 MB |
| 런타임 | dlib | OpenVINO (이미 있음) |
| 정확도 | LFW 99.4%대 | LFW 99.3%대 |

유지되는 것: `train_face` / `recognize` / DB 함수 **시그니처 그대로**.

깨지는 것 3가지:
1. `score` 방향 — 유클리드 거리(낮을수록 유사) → 코사인(높을수록 유사).
   `1 - cosine`으로 반환하면 의미 보존 가능하나 **임계값 0.4 재튜닝 필수**
2. `landmark_face()` 68점 → 5점. 반환 shape `(68,2)` → `(5,2)`.
   → mediapipe 기반 재구현(478점)이 더 나은 선택일 수 있음
3. **facedb 128-d → 256-d. 기존 얼굴 전부 재등록 필요.** DB 버전 필드 추가 필요

새로 필요한 것: `landmarks-regression-retail-0009`(5점) + **정렬(similarity transform) 직접 구현**.
dlib의 `compute_face_descriptor`가 내부적으로 해주던 `get_face_chip` 정렬(150×150, padding 0.25)을
직접 짜야 한다. **정렬 품질이 인식률을 그대로 좌우한다.**

**우선순위 근거**: 117MB는 큰 숫자지만 torch 제거가 먼저다. 운영 비용(현장 얼굴 재등록)도 붙는다.

### 3.5 랜드마크 두 개 — 둘 다 유지, 지연 로딩으로 해결

**결정**: dlib 68점과 mediapipe 478점 **둘 다 유지**. 제거하지 않는다.
대신 `Face.__init__()`의 무조건 로드를 지연 로딩으로 바꾼다.

**근거**: 의존 관계를 뽑아보니 **한 번도 겹치지 않는다.**

| 메서드 | 필요 모델 |
|---|---|
| `detect_face` | OpenVINO face-detection |
| `analyze_face` | OpenVINO age-gender + emotion |
| `landmark_face` | dlib predictor |
| `train_face` / `recognize` | dlib predictor + encoder |
| `detect_mesh` | MediaPipe face_landmarker |

현재 `Face()` 하나를 만들면 **모델 6개가 전부 올라온다.**
얼굴 위치만 알고 싶어도 나이·성별·감정·메시 모델까지 적재된다.

### 3.6 지연 로딩 그룹

```
A. 탐지     face-detection             ~2.3 MB   → 상시 (거의 모든 흐름의 진입점)
B. 분석     age-gender + emotion       ~17.7 MB  → analyze_face 첫 호출
C. 얼굴인식 dlib predictor + encoder   ~122 MB   → train/recognize/landmark 첫 호출
D. 메시     mediapipe face_landmarker  ~4 MB     → detect_mesh 첫 호출
```

**C를 한 덩어리로 묶는 이유**: `shape_predictor_68`은 dlib 인코더의 **정렬 전제**다.
인코더는 68점으로 정렬된 얼굴을 입력으로 학습됐고, 정렬을 건너뛰면 임베딩 품질이 무너진다.
분리 불가능한 쌍이므로 통째로 지연 로딩한다.

**C는 동시에 3.4의 교체 단위이기도 하다.** 나중에 face-reidentification으로 가면
이 그룹 전체가 통으로 빠진다.

**올바른 패턴이 이미 같은 파일에 있다**: `vision_detect.py`의
`self.hand_gesture_recognizer = None` + `load_hand_gesture_model()`.
이 방식을 나머지에 적용하면 된다.

### 3.7 런타임 — 3종으로 수렴

| 런타임 | 용도 | 판단 |
|---|---|---|
| **onnxruntime** | TTS(speech, mtts) | 유지 + YOLO 흡수 후보 |
| **openvino** | 얼굴 스위트 | 유지 + CustomClassifier 백본 후보 |
| **mediapipe** | 손·얼굴 랜드마크 | 유지 — 대안 없음, 자체 C++ 런타임(TF/torch 불필요) |
| tflite_runtime | movenet → TeachableMachine | 유지 |
| tensorflow | vision_classify 3곳 | 단계적 제거 (**우선순위 낮음** — 상시 점유 아님) |
| ultralytics + torch | YOLO 래퍼 | **제거 목표** (7단계) |

---

## 4. LLM / RAG

### 4.1 Gemma 3 1B Q4 — 유지

**근거**: 이미 파이에서 구동 중. Gemma 3는 로컬/글로벌 어텐션 5:1(sliding window 512)이라
KV 캐시가 동급 모델보다 작다.

실행 인자는 `llama-server.service` 유닛에 있고 **레포에 없다** → 편입 대상.
포트는 **50020** (tools 50000, classifier 50010과 같은 대역).

### 4.2 온디바이스 LLM 용도 — 짧고 형식이 정해진 출력만

| 용도 | 판단 |
|---|---|
| 자연어 → 블록 생성 (GBNF 문법 제약) | **가능** — 출력 수십 토큰 |
| 코드 오류를 아이 눈높이로 번역 | **가능** — 짧은 출력 |
| 자유 대화 페르소나 | **불가** — 1B급 한국어 품질이 수업에 못 나감 |
| VLM (사진 보고 답하기) | **불가** |
| LLM + 비전 모델 동시 상주 | **불가** (아래 4.3) |

**대화형으로 포장하지 말 것.** 기대치만 올라가고 실물이 못 따라간다.

### 4.3 LLM과 비전은 절대 공존 불가

```
Detect()      789 MB  (실측)
Gemma 3 1B    800~950 MB (추정)
──────────────────────────
합            1.6 GB+   → OS·허브 빼면 이미 초과
```

**`ModelSlot` 교대가 선택이 아니라 필수.** 현재 `systemctl stop llama-server`로
서로 죽이는 구조는 우연히 옳았다.

llama-server는 systemd 별도 프로세스이므로 슬롯은 **프로세스 start/stop만 관리**하면 된다.
파이썬 객체를 들었다 놨다 할 필요가 없어 메모리 회수가 확실하다.

### 4.4 RAG — vapi-od `db_routes.py` 이식

**결정**: e5-small 기반. **BM25 대안은 폐기** (아래 `03-discarded.md` 참조).

**근거**: 사내에서 이미 검증되고 실기 튜닝까지 끝났다. 다시 만들 이유가 없다.

그대로 가져올 것:

| 항목 | 값 |
|---|---|
| 임베딩 | multilingual-e5-small, 384dim, INT8 |
| `split_text()` | 문단 → 문장부호 → 짧은 조각 병합 |
| 저장 포맷 | `data/db/<slug>.json`, 벡터 b64 + dim |
| 검색 | 정규화 벡터 내적 = 코사인, numpy (**벡터DB 불필요**) |
| `MIN_SCORE` 0.60 | 실기 튜닝값. 0.72는 맞는 질문까지 걸러냈음 |
| `SURE_SCORE` 0.80 | 닮았는데 "못 찾음" 하면 재시도 |
| `kind="query"` / `"passage"` | e5 계열 필수 프리픽스 |

**반드시 바꿔야 할 것**:

```
CHUNK = 350   →  180~200   (한국어 350자 ≈ 180~230 토큰)
OVERLAP = 60  →  35        (비율 유지)
TOP_K = 4     →  검색은 4 유지, 주입은 1~2개만
```

나머지 2~3개는 화면 "찾은 곳"에 점수와 함께 **표시만** 한다.
검색 정확도는 유지하고 생성 비용만 줄이는 절충. vapi-od UI가 이미 점수를 보여주므로
화면 구조 변경 불필요.

**청크 길이가 바뀌면 점수 분포가 이동하므로 `MIN_SCORE` 재확인 필요.**

### 4.5 병목은 메모리가 아니라 prefill

토큰 생성은 메모리 대역폭 바운드지만 **프롬프트 처리(prefill)는 연산 바운드**다.

| 주입 컨텍스트 | prefill 추정 | 판단 |
|---|---|---|
| 1000 토큰 (vapi-od 현재 설정) | 25~50 초 | **못 씀** |
| 400 토큰 | 10~20 초 | 경계 |
| 200 토큰 | 5~10 초 | 견딜 만함 |

설계 원칙:
- 주입 총량 **200~300 토큰 이내**
- 시스템 프롬프트 최소화 + `--prompt-cache`로 고정 프리픽스 재사용
- **스트리밍 필수** (현재 `call_llm()`은 안 함 → `04-known-issues.md`)
- 대기 중 파이보 눈 LED로 "생각 중" 표현

**`llama-bench`의 `pp` 수치가 청크 상한을 결정하는 유일한 숫자다.**

### 4.6 `/find`와 `/rag` 분리 — 파이에서 더 중요

vapi-od 원 주석: "아이에게 RAG는 두 단계다. ① 비슷한 문장 찾기 ② 그걸 보고 답 만들기.
①만 따로 볼 수 있어야 'AI가 어디서 가져왔는지'를 가르칠 수 있다."

파이에서는 **성능 근거가 하나 더 붙는다**:

| 단계 | 파이 4 지연 |
|---|---|
| ① 찾기 (`/find`) | **0.1~0.3초** — 질의 임베딩 1회 + numpy 내적 |
| ② 답하기 (`/rag`) | 10~20초 |

**수업의 무게중심을 ①에 두면 하드웨어 제약이 교육 설계와 맞아떨어진다.**
제약을 감추는 게 아니라 원래 설계가 그쪽이었다.

### 4.7 T5 계열 — 추가하지 않음

| 용도로 생각했다면 | 판단 |
|---|---|
| 임베딩 (sentence-T5) | **한국어 성능 약함.** e5-small이 같은 크기에서 낫다 |
| 생성 (mT5-small) | **중복.** Gemma 3 1B이 그 자리다. 둘 다 올릴 여유 없음 |
| 리랭커 | 후보마다 forward pass → 파이 4에서 지연 감당 불가 |

### 4.8 프롬프트는 재튜닝 필요

vapi-od 생성기는 Qwen2.5-1.5B-INT4, 파이는 Gemma 3 1B. **`prompts.py`를 그대로 못 쓴다.**

- `SURE_SCORE` 재시도 로직은 Qwen 거동에 맞춰 만든 것. 구조는 살리되 문구·임계값 재튜닝
- Gemma 3는 **시스템 롤이 없다.** 첫 user 턴에 지시를 넣어야 함
- 프롬프트가 길수록 prefill이 늘어난다 → 짧게 유지가 성능에 직결

### 4.9 AI PC 연동 — 제외

**결정**: 온디바이스 전제. 로드맵에서 제거.

---

## 5. UX / UI

### 5.1 리버스 프록시 우선 — 프로세스 통합은 나중

**결정**: 프로세스는 그대로 두고 **origin만 하나로** 합친다.

```
:80  허브 (기존 run_ide 확장)
  ├─ /              SPA shell
  ├─ /api/system/*  직접 처리
  ├─ /tools/*    ──proxy──▶ :50000
  ├─ /classify/* ──proxy──▶ :50010
  └─ /llm/*      ──proxy──▶ :50020
```

**근거**: 프로세스 통합 없이 UX의 대부분을 확보할 수 있고,
**나중에 통합해도 프론트는 안 바뀐다** (프록시 경로가 내부 라우팅으로 바뀔 뿐).

| | 지금 | 프록시 후 | 프로세스 통합 후 |
|---|---|---|---|
| 새 창 뜸 | O | **X** | X |
| origin 갈림 | O | **X** | X |
| 뒤로가기 | 깨짐 | **동작** | 동작 |
| 3초 blind sleep | O | **X (헬스체크)** | X |
| 설정 어디서나 | X | **O** | O |
| 전환 지연 | 3초+ | 수 초~십수 초 | 거의 없음 |
| 동시 사용 | X | X | O |

현재 문제 코드 (`landing.html`):
```
fetch(`http://${location.hostname}/tools?enable=on`)
  .then(() => setTimeout(() => {
      window.open(`http://${location.hostname}:50000`);   // 다른 origin, 새 창
  }, 3000))
```
3초 blind sleep 후 다른 포트를 새 창으로 연다. 세션·상태·뒤로가기가 모두 끊긴다.

**전환 지연은 숨기지 말고 정직하게 보여준다.** `systemctl is-active` 폴링 +
진행 표시로 3초 추측을 대체하고, 파이보 눈 LED를 같이 쓴다.

### 5.2 정보 구조

```
┌─ 상단바 ────────────────────────────────────────┐
│ [로고]  체험  블록  파이썬  학습  대화     🔋 📶 ⚙ │
└─────────────────────────────────────────────────┘
   상태 배지: ● 카메라 사용중  ● 코드 실행중  ● 모델 로딩중
```

- 탭 전환은 클라이언트 라우팅. 페이지 리로드 없음, `window.open` 없음
- ⚙ 설정은 **모달**. 와이파이·시스템 정보·로그·초기화·전원.
  지금은 landing.html에 섞여 있는데 어느 탭에서든 열려야 한다
- 상태 배지가 자원 점유를 항상 노출
- 교실 태블릿 접속을 상정해 상단 탭 → 하단 탭바 브레이크포인트

**vapi-od `view_project`의 라우팅 규약을 이식한다**:
`/<묶음>/<기능>`, 응답 봉투 `{type, result, data, elapsed_ms, device}`.

### 5.3 기술 스택

파이에서 빌드 툴체인을 돌릴 필요 없다. **개발 머신에서 빌드해 정적 파일만 배포.**
번들 크기가 SD 카드 I/O에 직결되므로 React 풀 스택은 과하다.
Preact + htm(빌드 없이 CDN)도 충분한 선택지.

### 5.4 학생 코드 실행 중 카메라 미리보기 — **하지 않음**

**결정**: 명시적 `show()` 호출 시에만 화면에 표시. 라이브 스트림 없음.

**근거**:
- **네트워크 부담.** 교실 와이파이에 파이 여러 대가 붙으면 MJPEG 상시 스트림은 무리
- **인과가 흐려진다.** "카메라 켜기" 블록을 안 넣었는데 영상이 나오면
  아이가 그 블록의 필요성을 알 수 없다
- CPU 낭비 (JPEG 인코딩 2벌)

기존 `/show` 엔드포인트 패턴을 그대로 유지하면 예제·교재도 안 바뀐다.
브로커에 팬아웃 능력은 두되 **기본 정책은 쓰지 않는다.**

---

## 6. 5모드 학습 이식 (vapi-od `train_routes.py`)

### 6.1 이식한다

| kind | 특징 | 차원 | 파이 추출기 | 추가 비용 |
|---|---|---|---|---|
| pose (손) | MediaPipe 손 랜드마크 21점 정규화 | **63** | `gesture_recognizer.task` | **0** |
| face (표정) | MediaPipe 블렌드셰이프 | **52** | `face_landmarker.task` | **0** |
| body_up (상반신) | 11점 × xy | **22** | yolo11s-pose | 0 |
| body (전신) | 17점 × xy | **34** | yolo11s-pose | 0 |
| image | MobileNetV2 임베딩 | 1280 | **백본 이관 필요** | 백본 1개 |

**근거**: 손·표정·상반신·전신 4개 모드는 **백본 모델이 아예 필요 없다.**
랜드마크 좌표를 정규화한 수십 차원 벡터가 특징의 전부다.

`vision_face.py:149`가 이미 `output_face_blendshapes=True`로 되어 있다.
**표정 학습에 필요한 52차원이 지금도 나오고 있는데 안 쓰고 있었다.**

- 학습: 브라우저 TF.js. `Dense(D→128, relu) → Dense(128→N, softmax)`
- 추론: **numpy matmul 2번 + relu + softmax.** 프레임워크 불필요

### 6.2 특징 호환 — 모드별로 다르다

| 모드 | 학습 | 추론 | 일치 요구 |
|---|---|---|---|
| image (1280) | 브라우저 TF.js MobileNet | 서버 OpenVINO | **필수** — 전처리까지 |
| pose/face/body | 서버 `_embed()` | 서버 `_embed()` | 같은 기기 안에서만 |

특징이 **기하학적 좌표**라 검출기가 달라도 물리적 의미가 유지된다.
face 모드(52차원 블렌드셰이프)는 **양쪽 다 같은 mediapipe**라 애초에 동일하다.

yolo11 계열로 통일하면 vapi-od(yolo11m)와 COCO 17점 규격이 같아
**PC↔파이 모델 이동의 전제가 충족된다.** 단 m↔s 노이즈 차이는 실기 확인 필요.

### 6.3 이식 시 주의

- **전처리 일치.** image 모드는 `fromPixels(RGB) → resizeNearestNeighbor([224,224]) →
  toFloat() → div(255)`. 브라우저와 서버가 어긋나면 정확도가 **조용히** 무너진다.
  `_preprocess()`의 nearest-neighbor 인덱싱 방식을 그대로 옮길 것
- `KP_CONF = 0.5` — 흐린 관절 처리 규칙도 함께 가져와야 재현된다
- `_embed_body()`의 정규화: 전신은 엉덩이 중심 원점 + 몸통 길이 스케일,
  상반신은 어깨 중심 원점 + 어깨 너비 스케일. 인덱스 **5, 6, 11, 12**만 사용
- 파이 `BodyPart` enum이 COCO 17점 표준 순서와 일치함을 확인함 (5/6 어깨, 11/12 엉덩이)

### 6.4 image 모드 백본 이관 = TF 제거

vapi-od는 `mobilenetv2_feat.xml`(OpenVINO IR)을 쓴다.
파이 `CustomClassifier`는 `tf.keras.applications.MobileNetV2`를 쓴다.

**이걸 OpenVINO IR로 통일하면 이미지 모드 이식과 TF 제거가 동시에 끝난다.**
따로 할 일이 아니라 하나다.

---

## 7. 의존성 정리

### 7.1 제거 명분은 RAM 하나뿐

**디스크 논거는 폐기.** 28G 중 12G 여유. tensorflow 1.1G + torch 400M을 다 빼도
전체의 5%다. 이미지 굽는 시간도 체감 차이 없다.

"실수로 import할까 봐"도 제거 명분에서 뺀다.

### 7.2 우선순위가 뒤집힌다

| 패키지 | 디스크 | 실제 import | RAM 영향 |
|---|---|---|---|
| **tensorflow** | **1.1 G** | 변환 시 subprocess로만 | **거의 없음** |
| **torch** | **400 M** | `ultralytics` → **상시** | **큼** |
| mediapipe | 60 M | 상시 | 있음 |
| cv2 | 58 M | 상시 | 있음 |
| onnxruntime | 37 M | 상시 | 있음 |
| ultralytics | 6.4 M | 상시 | 껍데기, torch가 본체 |
| openvino | 96 M | 상시 | 있음 |

**tensorflow가 디스크 1위인데 RAM 영향은 거의 없고, torch는 디스크 3위인데 RAM 1위다.**

`ultralytics` 6.4M이 400M을 끌고 온다. ONNX 추론을 onnxruntime으로 직접 돌리면
6.4M을 잃고 400M을 버는 거래.

### 7.3 두 축을 혼동하지 말 것

| 축 | 선택지 | 영향 |
|---|---|---|
| **A. 래퍼** | ultralytics vs 직접 구현 | **torch 400MB** |
| **B. 백엔드 형식** | ONNX+onnxruntime vs OpenVINO IR | 속도, 일관성 |

**B만 바꾸면 400MB는 그대로 남는다.**

vapi-od도 ultralytics를 쓴다 (`engines.py:61` `class Yolo`).
`box.xyxy[0].cpu().numpy()` — `.cpu()`는 torch 텐서 메서드다.
**백엔드가 OpenVINO여도 결과는 torch 텐서로 나온다.**

→ "vapi-od와 동일하게"를 문자 그대로 하면 메모리가 똑같다.

### 7.4 OpenVINO vs onnxruntime — 실측으로 정한다

OpenVINO CPU 플러그인은 x86(oneDNN/AVX) 최적화가 본체다.
ARM에서는 ARM Compute Library 경로를 타는데 x86만큼 성숙하다고 보기 어렵다.

파이에서 OpenVINO가 도는 건 확인됨(얼굴 모델 3종). 하지만
**"돈다"와 "YOLO에서 onnxruntime보다 빠르다"는 다른 얘기다.** 추측 금지.

권장 순서: **ultralytics 제거 → 백엔드 갈아끼워 벤치 → 빠른 쪽 확정.**
전처리·후처리를 직접 갖고 있으면 백엔드 교체가 몇 줄 문제가 된다.

### 7.5 제거 목록 (RAM 기준 우선순위)

**높음** — 실제 RAM 이득
- `torch`, `torchvision`, `torchaudio` (= `ultralytics` 제거와 동시)

**중간** — 변환 시 RAM 스파이크(300~500MB 추정)가 허브와 겹치면 OOM 위험
- `tensorflow`, `keras`, `tf-keras`, `tensorflow-estimator`, `h5py`
- 완화책: **변환 중 허브 모델 슬롯을 비우는 처리**만 넣어도 당분간 충분

**낮음** — import 0건, 사고 방지 목적
- mecab 계열(`mecab-python3`, `python-mecab-ko`, `python-mecab-ko-dic`), `konlpy`, `jamo`
  → 코드 import 0건. 유일한 흔적이 `speech.py:311`의 주석 `#self.mecab = Mecab()`
- `transformers`, `pandas`, `scipy`, `matplotlib`, `seaborn`, `sympy`, `nltk`
- `numba`, `llvmlite`, `boto3`, `botocore`, `google-*`
- `openvino-dev`, `openvino-telemetry`, `tensorflowjs`, `tensorflow-hub`,
  `tensorflow-io-gcs-filesystem`, `onnx`, `onnxslim`

**순서 주의**: `openvino-dev`는 메타패키지(dist-info 356K만 존재)라 지워도 356K다.
그러나 **의존성으로 `scipy`, `opencv-python` 등을 끌어왔을 가능성이 크다.**
`pip show openvino-dev | grep Requires`로 확인 후, **openvino-dev를 먼저 빼야**
그것들을 안전하게 지울 수 있다.

**중복 설치 — 실제 위험**
- `opencv-python` + `opencv-contrib-python` 둘 다 설치됨.
  같은 `cv2` 네임스페이스를 두 패키지가 제공한다. 버전이 어긋나면 깨진다.
  **contrib 하나만 남길 것.**

### 7.6 근본 대책

`test/requirements.txt`가 **310줄인데 실제 import는 40개 남짓**이다.
의존성 명세가 아니라 `pip freeze` 덤프다.
`setup.py`의 `install_requires`는 `openpibo_*_models` 4개만 남기고 전부 주석 처리.

1. `setup.py`의 `install_requires`를 **실제 import 기준**으로 채운다
2. `test/requirements*.txt` 6개 변종(`.txt`, `.bak`, `-260309`, `.260313`, `.tf`, `.sphnix`)을
   하나로 정리. **지금은 어느 게 진짜인지 알 수 없다**
3. 런타임 / 빌드 / 개발 도구 분리 — `openvino-dev`, `onnx`, `tensorflowjs` 같은
   변환 도구는 기기에 안 들어간다
4. 깨끗한 Bookworm에서 새 명세로 설치해 이미지 재생성 후 **실제로 뜨는지 검증**

### 7.7 유지 목록

`opencv-contrib-python`, `numpy`, `pillow`, `mediapipe`, `onnxruntime`, `openvino`,
`tflite_runtime`, `dlib`, `openpibo-dlib-models`, `picamera2`, `fastapi`, `uvicorn`,
`fastapi_socketio`, `requests`, `pyserial`, `RPi.GPIO`, `rpi_ws281x`,
`adafruit_ssd1306`, `adafruit_rgb_display`(ili9341 + st7735), `pyzbar`, `bs4`,
`soundfile`, `openpibo_*_models`

---

## 8. 아키텍처 목표 (7단계)

### 8.1 단일 허브 + 자원 중재

**핵심**: 포트가 4개인 게 문제가 아니라 각 서비스가 카메라·오디오·시리얼을
독점하기 때문에 systemd로 서로를 죽이고 있다.

단일 프로세스로 합치면 **cv2/numpy/tflite가 한 벌만 올라간다.**

브로커가 카메라를 부팅 시 한 번 열고 계속 들고 있으면
`/api/vision/stream`과 `/api/train/capture`가 **동시에** 같은 프레임을 볼 수 있다.

### 8.2 이미 부분 적용되어 있다

**시리얼은 이미 프록시다.** `booting.py`의 `uart_ctrl`이 `/dev/ttyS0`를 독점하고,
`run_ide.py`는 직접 열지 않고 HTTP로 우회한다:
```
requests.get('http://127.0.0.1:8080/device/%2315%3A%21')
```

**vapi-od의 `themaker.py`가 같은 물건이다.** "학생 코드용 라이브러리"로,
`main.py` 서버를 HTTP로 호출하는 얇은 클라이언트. Windows에서 검증된 구조.

### 8.3 openpibo 씬 클라이언트화

**IDE에서 학생 코드를 실행할 때 모델이 중복 적재되는 문제**의 해법.

현재 흐름:
1. 허브에 YOLO 적재
2. 학생이 실행 → `from openpibo.vision_detect import Detect` → **또 적재**
3. 2GB에서 둘 다 불가 → 허브가 자기 걸 내림 → 학생 코드는 처음부터 로딩 → **10~20초**
4. 코드 끝나면 허브가 다시 로딩 → **또 10~20초**

메모리 문제이면서 동시에 **체감 속도 문제**다.

| 모듈 | 성격 | 처리 |
|---|---|---|
| `vision_detect`, `vision_face`, `vision_classify` | 무거움 + 모델 상주 | **프록시** |
| `vision_camera` | 장치 배타 | **프록시** |
| `speech`, `mtts` | 무거움 + 오디오 배타 | **프록시** |
| `audio` | ALSA 배타 | **프록시** |
| `device` | 시리얼 배타 | **프록시** (이미 그러함) |
| `motion` | 시리얼 배타 | **프록시** |
| `oled`, `pibo_graphics` | SPI 배타 | **프록시** |
| `collect` (Wikipedia/Weather/News) | 순수 네트워크 | 로컬 유지 |
| `utils` | 순수 계산 | 로컬 유지 |

**클래스 이름과 시그니처를 유지하면** 기존 예제·교재·블록리 생성 코드가 그대로 돈다.

감수할 것:
- 파이 밖에서 openpibo 단독 실행 불가 → `OPENPIBO_HUB` 환경변수 폴백 필요
- 이미지 왕복 비용 → **Unix domain socket** 권장, 더 줄이려면 `/dev/shm` 공유 버퍼
- 허브가 죽으면 학생 코드도 죽음
- traceback이 프로세스 경계를 넘음 → 에러 응답에 허브 측 예외 요약 필요

미해결 설계 질문:
- 무한 루프 학생 코드가 정지 없이 방치되면 자원을 계속 잡음 → 타임아웃 또는 실행 상태 배지
