# 02. 로드맵

각 단계에 **선행 조건**과 **완료 기준**을 적는다.
선행 조건이 안 채워졌으면 건너뛰지 말고 멈출 것.

최종 갱신: 2026-08-27

---

## 개요

```
0. 레포 통합 + board.py 프로파일        ← 코드 작업 완료. 실기 확인 남음
1. 리버스 프록시 + 헬스체크             ← 코드 작업 완료. 실기 확인 남음
2. SPA shell + 설정 모달                ← 코드 작업 완료. 실기 확인 남음
3. yolo11s / yolo11s-pose 전환
4. 5모드 학습 이식
5. image 모드 → OpenVINO 백본 (TF 제거 동시)
6. Face / Detect 지연 로딩
7. (후순위) 프로세스 통합, ultralytics/torch 제거
```

> **진행 상황 (2026-08-27)**
> -1단계와 0단계의 **코드 작업이 끝났다.** 아직 실기에서 돌려보지 않았다.
> 완료 기준(두 보드에서 부팅 화면·LED·카메라 1프레임)은 기기에서 확인해야 한다.
> 각 항목의 상태는 아래에 표시했다.

**0단계를 UX 앞에 두는 이유**: SPA shell(2단계)이 이 로드맵에서 가장 덩치 큰 작업이다.
통합 없이 진행하면 pibo에 한 번, pibrain에 한 번 만들게 되고,
**두 벌이 또 갈라지기 시작한다.** 지금 `tools/`가 socket.io / REST+SSE로
아키텍처까지 달라진 게 정확히 그렇게 벌어진 결과다.

---

## -1. 사전 작업 (0단계 전)

### 회귀 시험 이식 — **일부**

`test/js/board_filter.test.js` 추가. 실제 툴박스를 두 보드 프로파일로 걸러
26개 항목을 확인한다 (`node test/js/board_filter.test.js`).
레포에 실행되는 시험이 하나도 없던 것의 첫 칸이다.

아직 vapi-od 쪽은 안 가져왔다. 가져올 것:
- `tools/schema_test/` — 가짜 엔진으로 서버를 띄워 엔드포인트·라이브러리를 실제 호출
- `tools/e2e/examples_cover.js` — 예제가 블록·함수를 빠짐없이 지나가는지

**큰 리팩터링을 시작하기 전에 안전망이 있어야 한다.**
현재 파이 레포의 `test/`에는 requirements 파일만 있고 실제 테스트가 없다.

### 버그 수정 — **완료 (높음 5건)**

`04-known-issues.md`의 **높음** 5건 + 중간/낮음 6건을 고쳤다.
어느 것이 고쳐졌는지는 그 문서에 표시했다.

### systemd 유닛 편입 — **4/5 완료**

`system/units/` 에 넣고 `system/units/install.sh` 가 `/etc/systemd/system/` 으로
심볼릭 링크한다. `init` 이 링크가 없으면 자동으로 건다.

- `booting.service`   — 코드에서 재구성
- `ide.service`       — 코드에서 재구성
- `tools.service`     — 코드에서 재구성 (+ `Conflicts=`)
- `classify.service`  — 코드에서 재구성 (+ `Conflicts=`)
- `llama-server.service` — **비어 있다.** `-c` 값을 추측할 수 없다.

**기기에서 실물을 떠 와야 한다:**

```bash
sudo bash system/units/capture-from-device.sh
git diff system/units/          # 재구성본과 실물의 차이를 확인
```

떠 오기 전까지 `install.sh` 는 `llama-server.service` 만 건너뛴다.
채워지지 않은 값으로 돌고 있는 설정을 덮어쓰는 것이 제일 나쁘다.

### 실측 — **대기**

`tools/measure/run.sh` 는 레포에 들어와 있다. 아직 실행하지 않았다.
실행 후 `01-measurements.md` A절 채우기.
최소한 B.1(llama-server)과 B.3(789MB 분해)는 3단계 전에 필요하다.

주의사항은 `tools/measure/README.md` 참고.

---

## 0. 레포 통합 + board.py — **코드 완료 / 실기 미확인**

### 선행 조건
- 없음

### 작업

1. ~~**새 레포 `openpibo-os` 생성**~~ — 임시 레포 `openpibo-os.new` 에 pibo 를
   그대로 옮겨 첫 커밋으로 두었다. 이력은 원 레포에 남아 있다.
2. ~~`docs/plan/` + `tools/measure/` 커밋~~ **완료**
3. ~~`openpibo/board.py` 작성~~ **완료**
4. ~~`profiles/pibo.toml`, `profiles/pibrain.toml`~~ **완료**
   — 단 위치가 다르다. `openpibo/profiles/*.toml` 이다.
   레포 루트는 wheel 에 안 들어가서, wheel 만 설치한 환경에서
   `import openpibo.board` 가 바로 죽는다.
   기기별 시험값은 `/home/pi/board.toml` 로 덮어쓸 수 있게 했다.
5. ~~각 모듈에서 상수를 `BOARD`로 치환~~ **완료**
   - `audio.py` — 카드/믹서/기본음량 + 마이크 device·채널·레이트·포맷
   - `vision_camera.py` — 크기 + `read()` 변환 (`flip_both` / `rot90ccw`)
   - `oled.py` — `get_display()` 팩토리 + 폰트/크기
   - `pibo_graphics.py` — 기본 크기
   - `motion.py` — `move()` 를 `has_legs` 로 막음 (삭제 아님)
   - `device.py` — `get_device()` 팩토리 (원 계획에 없던 것. 추가)
   - `booting.py` — `has_mcu` 면에서만 `mcu_control` import
   - `network_disp.py` — 좌표·글자크기 레이아웃 전체 (원 계획에 없던 것. 추가)
6. ~~블록 툴박스 필터링~~ **완료**
   서버가 `BOARD_INFO` 를 만들어 `window.__BOARD__` 로 주입하고,
   `ide/static/board_filter.js` 가 `requires` 플래그로 걷어낸다.
   `has_legs` 거짓이면 모션 카테고리가 통째로 사라진다.
   기능 플래그는 6개: `has_mcu` `has_legs` `has_buttons` `has_ws2812`
   `has_usb_uart` `can_record_audio`.
7. pibrain 레포 아카이브 (삭제 금지) — **아직**

### 주의

- **pibo 기준으로 병합할 것.** `Oled7735`가 pibo에만 있다
- `pibrain/openpibo/pibo_graphics.py` 하단의 `__main__` 예제는 잔재 — 정리
- `tools/`는 **지금 병합하지 않는다.** 2단계에서 새로 만든다
- 커밋을 잘게 나눌 것. 통합은 판단이 들어가는 작업이라 되돌리기 쉬워야 한다
- 핀·정격 관련 값은 **확인 전까지 프로파일에 하드코딩 금지**
  (`00-decisions.md` 2.4 참조)

### 완료 기준

- [ ] 두 보드에서 `import openpibo` 후 기본 동작(부팅 화면, LED, 카메라 1프레임) 확인
      — **기기에서 확인해야 한다. 이것만 남았다.**
- [x] `motion.move()`가 pibo에서만 노출 (파이브레인에서는 이유를 말하는 예외)
- [x] 블록 툴박스가 보드별로 다르게 렌더링
      (파이보 173블록/16카테고리, 파이브레인 161블록/15카테고리 — 시험으로 확인)

### 기기에서 확인하는 순서

```bash
cd /home/pi/openpibo-os
git fetch && git checkout claude/pibo-pibrain-integration-uw14wz

sudo bash system/set_board.sh pibrain      # 또는 pibo
sudo bash system/install.sh                # wheel + 유닛 + 보드 확인
sudo bash system/units/capture-from-device.sh   # llama-server 유닛 떠 오기
sudo systemctl restart booting.service ide.service

# 화면 / LED / 카메라
/home/pi/.pyenv/bin/python3 -c "
from openpibo.board import BOARD; print(BOARD.name, BOARD.label)
from openpibo.oled import get_display; d = get_display(); d.clear()
from openpibo.vision_camera import Camera; c = Camera(); print(c.read().shape)
"
```

---

## 1. 리버스 프록시 + 헬스체크 — **코드 완료 / 실기 미확인**

### 선행 조건
- 0단계 완료

### 작업

1. ~~허브에 프록시 라우트 추가~~ **완료** — `ide/proxy.py`
   ```
   /tools/*     → 127.0.0.1:50000
   /classify/*  → 127.0.0.1:50010
   /llm/*       → 127.0.0.1:50020
   ```
   HTTP, SSE/MJPEG 스트리밍, WebSocket(socket.io) 전부 중계한다.
2. `/api/system/*` 정리 — **안 했다.** 기존 socket.io 이벤트로 돌고 있고,
   2단계 SPA shell 에서 설정 모달과 함께 손대는 것이 맞다. 지금 옮기면 두 번 만든다.
3. ~~**3초 blind sleep 제거**~~ **완료** — 다만 `systemctl is-active` 폴링만으로는
   부족했다. `is-active` 는 **uvicorn 이 포트를 잡기 전에 이미 active 를 돌려준다.**
   그래서 두 단계로 나눴다: `active`(유닛이 떴다) → `ready`(포트가 응답한다).
   화면은 `ready` 에서만 넘어간다.
4. ~~전환 진행 상태를 SSE 로 전달~~ **완료** — `/api/service/{name}/events`
5. ~~CORS 미들웨어 제거~~ **완료** — 덤으로, 원래 설정이 스펙상 무효였다
   (`allow_origins=["*"]` + `allow_credentials=True`). 즉 지금까지도 실제로
   동작하지 않았다 (`04-known-issues.md` 8).

### 프록시가 손봐야 했던 것 (계획에 없던 부분)

경로 앞머리로 중계하면 뒤쪽 앱의 URL 이 전부 어긋난다. 두 가지를 해결했다.

- **자산 경로.** 뒤쪽 템플릿이 `../static/...` 을 쓴다. `/tools/` 아래에서는
  브라우저가 허브의 `/static/` 을 찾아간다. → HTML 을 지나갈 때 `/tools/static/` 으로 고친다.
- **JS 안의 절대 URL.** `fetch(\`http://${location.host}/control_cam\`)` 같은 것들이
  허브 루트로 샌다. → 허브가 HTML 에 `window.__BASE__` 를 심고, 앱 JS 가 그걸 앞에 붙인다.
  포트로 직접 접속하면 `__BASE__` 가 없어 `''` 가 되므로 예전 그대로 동작한다.

  특히 `tools` 의 socket.io 는 `path: "/socket.io"` 로 고정돼 있었다. 그대로 두면
  **허브 자신의 socket.io 에 붙어 엉뚱한 서버와 이야기한다.**

### 완료 기준

- [x] 브라우저 주소가 `http://<ip>/` 하나로 유지
- [x] 새 창이 뜨지 않음 (안내 문서 `:8080` 만 예외로 남김 — 자원을 다투지 않는다)
- [x] 뒤로가기 동작 (`location.href` 로 같은 창 이동)
- [x] 전환 중 진행 상태가 화면에 보임 (몇 초 걸리는지 초 단위로)
- [ ] **기기에서 실제로 세 서비스가 프록시 너머로 동작** — 남음

### 주의

- **포트는 50020이다** (llama-server). 8081 아님
- `call_llm()`의 `http://0.0.0.0:50020`은 잘못된 주소 →
  `127.0.0.1`로 (`04-known-issues.md`)
- 프로세스 통합이 아니다. **여전히 systemd가 서로를 죽인다**
  (`services.EXCLUSIVE` 가 하나를 켤 때 나머지를 끈다. 유닛의 `Conflicts=` 와 이중으로)

### 완료 기준

- 브라우저 주소가 `http://<ip>/` 하나로 유지
- 새 창이 뜨지 않음
- 뒤로가기 동작
- 전환 중 진행 상태가 화면에 보임

---

## 2. SPA shell + 설정 모달 — **코드 완료 / 실기 미확인**

### 선행 조건
- 1단계 완료

### 작업

1. ~~**vapi-od `view_project` 라우팅 규약 이식**~~ **완료** — `ide/envelope.py`
   - `/api/<묶음>/<기능>` (`/api/system/info`, `/api/service/{name}/events` …)
   - 응답 봉투 `{type, result, data, elapsed_ms, device}`
   - `elapsed_ms` 는 장식이 아니다. 파이 4 에서는 어떤 호출이 느린지가 곧 UX 다.
   - `device` 로 어느 보드가 답했는지 구분한다.
2. ~~상단바 + 탭~~ **완료** — 단 **홈 / 체험 / 코딩 / 학습 / 대화** 5개다.
   계획의 "블록 / 파이썬"을 **두 탭으로 나누지 않았다.**
   현재 IDE 는 Blockly 와 CodeMirror 를 **한 화면에 같이** 띄운다. 나누려면
   IDE 자체를 다시 짜야 하는데 그건 2단계의 일이 아니다. 같은 페이지를 가리키는
   탭 두 개를 만드는 건 나뉜 척만 하는 것이라 하지 않았다. → 별도 과제.
3. ~~**설정 모달**~~ **완료** — 시스템 정보 / 와이파이 / 실행 기록 / 전원.
   어느 탭에서든 ⚙ 로 열린다.
   **초기화는 넣지 않았다.** 되돌릴 수 없는 동작이라 확인 절차를 제대로 설계해야
   하고, 지금 `handle_restore` 는 와이파이까지 되돌리고 바로 종료한다.
   설정 모달의 다른 항목과 무게가 달라 따로 다룬다.
4. ~~상태 배지~~ **완료** — 카메라 사용중(어느 화면이 쓰는지까지) / 코드 실행중 /
   모델 로딩중. `/api/system/events` SSE 로 2초마다, **바뀔 때만** 보낸다.
5. ~~반응형~~ **완료** — 720px 아래에서 상단 탭이 하단 탭바로 내려간다.

### 계획과 다르게 한 것

- **프레임워크를 안 썼다.** 계획은 "Preact + htm(CDN)도 충분한 선택지"였는데
  **CDN 을 못 쓴다** — 교실 파이는 인터넷이 없을 수 있다. 벤더링하면 번들이 늘고,
  탭 셸 하나에 그럴 이유가 없다. 바닐라 JS 452줄. 빌드 단계 없음, 의존성 0.
- **각 화면은 iframe 이다.** 1단계에서 origin 을 합쳐서 가능해졌다. 앱 자체는
  손대지 않는다. IDE iframe 만 살려 둔다(편집 중인 코드가 날아가면 안 된다).
  나머지는 떠날 때 버린다 — 어차피 서비스가 꺼져 죽은 화면이 된다.
- **예전 랜딩을 `/landing` 에 남겨 뒀다.** 셸이 실기에서 확인될 때까지 돌아갈 곳이
  필요하다. 확인되면 지운다.

### 완료 기준

- [x] 탭 전환 시 페이지 리로드 없음 (브라우저 시험으로 확인)
- [x] 설정이 어느 탭에서든 열림
- [x] 기존 IDE / classifier / tools 기능이 전부 접근 가능
- [x] 뒤로가기·앞으로가기·새로고침이 탭과 맞물림
- [ ] **기기에서 확인** — 남음

### 확인 방법

```bash
bash test/ui/run.sh     # 진짜 브라우저로 몬다. 하드웨어 불필요
```

### 주의

- **파이에서 빌드하지 않는다.** 개발 머신에서 빌드 → 정적 파일만 배포
- React 풀 스택은 과함. Preact + htm(CDN)도 충분
- **학생 코드 실행 중 라이브 카메라 미리보기는 하지 않는다**
  (`00-decisions.md` 5.4). 기존 `/show` 패턴 유지
- 전환 지연은 숨기지 말고 정직하게 표시. 파이보 눈 LED 병행

### 완료 기준

- 탭 전환 시 페이지 리로드 없음
- 설정이 어느 탭에서든 열림
- 기존 IDE / classifier / tools 기능이 전부 접근 가능

---

## 3. yolo11s / yolo11s-pose 전환

### 선행 조건
- `01-measurements.md` B.5 (현재 YOLO 지연) 측정 완료

### 작업

1. `yolo11s` 파일 배치 → `vision_detect.py:145`, `:233` 경로 교체
   (현재 두 곳이 `yolo26s` / `yolo11s`로 불일치)
2. **속도 실측** — imgsz 640/480/320
3. `yolo11s-pose` 추가
4. `detect_pose()` → **`Person` NamedTuple 어댑터**로 반환 타입 유지
5. 자세 학습 클래스 분리 확인 (만세 / 팔짱 / 앉기 정도)
6. movenet 제거

### 주의

- COCO 80 클래스 그대로 → 라벨 인덱스 무변경.
  vapi-od `COCO_KO` 한글 라벨 80종 재사용 가능
- **3단계에서 잠깐 공존, 4단계 아님 — 이 단계 안에서 5→6 순서로 진행**
- yolo11s-pose가 파이 4에서 감당 안 되면 **movenet 유지로 되돌린다.**
  그 경우 vapi-od 특징 호환 포기
- movenet 제거 시 딸려오는 것: `openpibo/modules/pose/`,
  `movenet_lightning.tflite`, `detect_pose_vis()` 호환
- **`tflite_runtime`은 남긴다** (TeachableMachine 이관 예정)
- detect + pose 동시 상주 시 `Detect()` RSS 재측정 필요

### 완료 기준

- 기존 예제·블록 코드가 수정 없이 동작
- `detect_pose()` 반환이 `Person` 형태 유지
- 자세 3~4종 분류가 실기에서 동작
- movenet 참조 0건

---

## 4. 5모드 학습 이식

### 선행 조건
- 3단계 완료 (body 모드가 yolo-pose에 의존)
- 손·표정 모드는 3단계 없이도 가능

### 작업

**순서: 손 → 표정 → 상반신/전신 → (5단계에서 이미지)**

1. `_embed()` 계열 이식 — `pose`(63), `face`(52), `body_up`(22), `body`(34)
2. 학습 헤드 추론 — numpy matmul 2번 + relu + softmax
3. 저장 포맷 — `data/user/<slug>/model.zip` + `meta.json`
4. `SoftError` 패턴 이식 — "손이 안 보여요" 같은 예상된 실패는 트레이스백 없이

### 주의

- **손·표정은 추가 모델 0개, 추가 런타임 0개, 추가 RAM 거의 0**
- `vision_face.py:149`에 `output_face_blendshapes=True`가 **이미 켜져 있다.**
  52차원이 지금도 나오는데 안 쓰고 있었다
- `KP_CONF = 0.5` 규칙을 함께 가져와야 재현된다
- `_embed_body()` 정규화: 전신은 엉덩이 중심 + 몸통 길이, 상반신은 어깨 중심 + 어깨 너비.
  인덱스 **5, 6, 11, 12**만 사용. 파이 `BodyPart` enum이 COCO 순서와 일치함 확인됨
- pose/face/body 모드는 **같은 기기 안에서 학습·추론하면 자기완결적**

### 완료 기준

- 손 모양 3종, 표정 3종 학습 후 인식 동작
- 자세 3종 학습 후 인식 동작
- 학습 데이터 수집 중 프레임 누락이나 오작동 없음

---

## 5. image 모드 → OpenVINO 백본 (TF 제거 동시)

### 선행 조건
- 4단계 완료

### 작업

1. `mobilenetv2_feat.xml`(OpenVINO IR) 배치
2. `CustomClassifier`의 `tf.keras.applications.MobileNetV2` → OpenVINO로 교체
3. 분류 헤드 → numpy (Dense 하나면 matmul + softmax)
4. `TeachableMachine` → `tf.lite.Interpreter` → `tflite_runtime`
   (`modules/pose/movenet.py`가 이미 올바른 패턴을 쓴다 — 그대로 따를 것)
5. `convert_tfjs_to_keras()` 처리 — 아래 셋 중 택일
   - (a) 유지 (subprocess 격리는 이미 되어 있음)
   - (b) tfjs `model.json` + `.bin`에서 **가중치만 파싱해 npz로** → keras 불필요
   - (c) 변환을 개발 머신으로 위임
6. TF 계열 제거

### 주의

- **전처리가 브라우저와 정확히 일치해야 한다**:
  `fromPixels(RGB) → resizeNearestNeighbor([224,224]) → toFloat() → div(255)`.
  어긋나면 정확도가 **조용히** 무너진다. `_preprocess()`의 nearest-neighbor
  인덱싱 방식을 그대로 옮길 것
- 현재 구조는 이미 TF를 잘 격리하고 있다 —
  `run_classify.py`는 `Camera`만 import하고, 변환은 subprocess.
  **상시 점유가 없으므로 급하지 않다**
- 진짜 위험은 **변환 순간의 RAM 스파이크**(300~500MB 추정)가 허브와 겹치는 것.
  b/c를 안 하더라도 **변환 중 허브 슬롯을 비우는 처리**만 넣으면 당분간 충분
- **브라우저 TF.js 학습은 그대로 둔다.** 파이 RAM을 안 쓰는 옳은 설계다

### 완료 기준

- 이미지 분류 학습·추론이 TF 없이 동작
- `import tensorflow` 0건
- 브라우저 학습 결과와 서버 추론 결과가 일치

---

## 6. Face / Detect 지연 로딩

### 선행 조건
- `01-measurements.md` B.4 (`Face()` RSS) 측정 완료

### 작업

`Face.__init__()`의 6개 무조건 로드를 그룹별 지연으로:

```
A. 탐지     face-detection             → 상시
B. 분석     age-gender + emotion       → analyze_face 첫 호출
C. 얼굴인식 dlib predictor + encoder   → train/recognize/landmark 첫 호출
D. 메시     mediapipe face_landmarker  → detect_mesh 첫 호출
```

`Detect.__init__()`도 동일하게 — YOLO는 첫 호출 시.

### 주의

- **올바른 패턴이 이미 같은 파일에 있다**:
  `self.hand_gesture_recognizer = None` + `load_hand_gesture_model()`
- **C는 통째로 묶는다.** `shape_predictor_68`은 dlib 인코더의 정렬 전제라
  분리 불가능한 쌍이다
- C는 동시에 face-reidentification 교체 시의 **교체 단위**다.
  경계를 여기로 맞춰두면 나중에 손댈 곳이 한 군데
- 첫 호출 지연이 생기므로 **상태 배지로 로딩을 노출**할 것

### 완료 기준

- 얼굴 위치만 쓰는 코드에서 `Face()` RSS가 A그룹 수준
- `detect_mesh`만 쓰는 코드에서 dlib이 안 올라옴
- 기존 API 시그니처 무변경

---

## 7. (후순위) 프로세스 통합, ultralytics/torch 제거

### 선행 조건
- 1~6단계 완료
- `01-measurements.md` B.3, B.7 측정 완료

### 7a. ultralytics 제거

1. letterbox 전처리 + NMS 후처리 직접 구현
2. 백엔드는 일단 **onnxruntime 유지** (이미 설치됨)
3. pose 후처리 추가
4. torch / torchvision / torchaudio 제거

**두 축을 혼동하지 말 것** (`00-decisions.md` 7.3):
형식(ONNX vs OpenVINO)만 바꾸면 torch는 그대로 남는다.
**래퍼를 먼저 손봐야** 백엔드 교체가 몇 줄 문제가 된다.

### 7b. 백엔드 벤치

같은 코드에서 onnxruntime ↔ OpenVINO를 갈아끼워 실측.
**ARM에서 어느 쪽이 빠른지 추측하지 말 것.**

### 7c. 프로세스 통합 + ResourceBroker

1. 4개 서비스를 단일 uvicorn으로
2. `ResourceBroker` — 카메라/오디오/시리얼 단일 소유 + 프레임 팬아웃
3. `ModelSlot` — 무거운 모델 하나씩 교대, 유휴 시 자동 해제
4. llama-server는 별도 프로세스 유지, 슬롯이 start/stop만 관리

### 7d. openpibo 씬 클라이언트화

`00-decisions.md` 8.3 참조.
**IDE 모델 중복 적재 문제의 해법.** 이게 끝나야 학생 코드 실행이 즉시 시작된다.

### 완료 기준

- `import torch` 0건
- 학생 코드 실행 시작 지연 1초 미만
- 카메라 스트림과 학습 데이터 수집 동시 동작

---

## 상시 원칙

- **하드웨어 값은 추측 금지.** 데이터시트/실기로 확인 안 되면 "확인 필요" 명시
- **`03-discarded.md`를 먼저 읽을 것.** 이미 틀린 판단을 반복하지 않기 위해
- 큰 변경 전에 회귀 시험이 도는지 확인
- 커밋을 잘게. 현장 기기가 있으면 `main`은 동작 상태로 유지
