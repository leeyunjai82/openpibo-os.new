# 01. 실측값과 대기 항목

**추정치와 실측값을 섞지 말 것.** 이 문서의 "실측" 표에 없는 숫자는 전부 추정이다.
`03-discarded.md`에 추정이 크게 빗나간 사례가 정리되어 있다.

측정 스크립트: `tools/measure/run.sh`

최종 갱신: 2026-08-27

---

## A. 실측 완료

### A.1 메모리

| 항목 | 값 | 측정일 | 비고 |
|---|---|---|---|
| **`Detect()` 인스턴스 RSS 증가** | **789 MB** | 2026-08-27 | 로그에 `TensorFlow Lite XNNPACK delegate` 출력됨 |

`Detect()` 하나가 2GB의 40%다. 이 숫자가 아래 결론을 확정한다.

- LLM(Gemma 3 1B, 800~950MB 추정)과 **절대 공존 불가**
- `ModelSlot` 교대가 필수
- 지연 로딩이 RAM에 직접 듣는 몇 안 되는 조치

### A.2 디스크 — site-packages

| 패키지 | 크기 |
|---|---|
| tensorflow | **1.1 G** |
| torch | **400 M** |
| openvino | **96 M** |
| mediapipe | 60 M |
| cv2 | 58 M |
| onnxruntime | 37 M |
| ultralytics | 6.4 M |
| openvino_telemetry | 216 K |
| openvino-2024.5.0.dist-info | 312 K |
| openvino_dev-2024.5.0.dist-info | 356 K (**메타패키지, 본체 없음**) |
| dlib | 16 K (**본체 아님 — 아래 B.2 참조**) |

### A.3 디스크 — 모델 파일

| 모델 | 크기 | 정밀도 |
|---|---|---|
| age-gender-recognition-retail-0013.bin | 8.2 M | FP32 |
| face-detection-retail-0004.bin | 2.3 M | FP32 |
| emotions-recognition-retail-0003.bin | 9.5 M | FP32 |
| **합계** | **20 M** | |

파라미터 수 대조 결과 **세 개 다 FP32 IR**이다.

| 모델 | MParams | FP32 이론값 | 실제 |
|---|---|---|---|
| face-detection-retail-0004 | 0.588 | 2.35 MB | 2.3 M |
| age-gender-retail-0013 | 2.138 | 8.55 MB | 8.2 M |
| emotions-retail-0003 | 2.483 | 9.93 MB | 9.5 M |

Open Model Zoo에 FP16 / FP16-INT8 배포판이 있다.
- FP16 → 20MB가 10MB. **CPU 플러그인은 로드 시 FP32로 되돌리므로 RAM은 그대로일 가능성**
- FP16-INT8 → 디스크·RAM·속도 모두 이득. 단 age/emotion 정확도 확인 필요

**우선순위 낮음.** 20MB는 dlib 옆에서 잔돈이다.
다만 A그룹(face-detection)은 상시 로드이므로 여기만 INT8로 바꾸는 건 검토 가치 있음.

### A.4 파일시스템

```
/dev/mmcblk0p2   28G   16G   12G  58%  /
```

**12G 여유.** 디스크를 정리 명분으로 쓸 수 없다.

---

## B. 실측 대기 — 우선순위 순

### B.1 최우선 — 로드맵 3단계 판단에 필요

#### llama-server 실행 인자

```
systemctl cat llama-server
```

`-c`(컨텍스트), `-t`(스레드), `--no-mmap`, `-ngl`, 모델 경로, 포트가 전부 여기 있다.
**이 유닛 파일이 레포에 없다** → `system/units/`로 편입할 것.

#### `llama-bench`의 `pp` 수치

```
llama-bench -m /home/pi/.model/<model>.gguf -p 128 -n 64 -t 4
```

**RAG 청크 상한을 결정하는 유일한 숫자.**
`pp`(prompt processing) tok/s가 나오면 주입 가능 토큰 수가 확정된다.

#### `llama-server` 프로세스 RSS

LLM 구동 중 실제 점유. 허브와 공존 가능 여부를 가른다.

### B.2 dlib 실제 크기 — 미확인

`00-decisions.md`에서 "dlib 모델 ~122MB"라고 쓴 건 **일반 배포본 기준 추정**이다.
실제 파일을 아직 못 찾았다.

```
du -sh /home/pi/.pyenv/lib/python3.11/site-packages/_dlib*
python3 -c "import openpibo_dlib_models as m; print(m.__file__)"
du -ah $(python3 -c "import openpibo_dlib_models,os; print(os.path.dirname(openpibo_dlib_models.__file__))") | sort -h | tail
```

`site-packages/dlib`이 16K로 나왔는데, dlib은 보통
`_dlib_pybind11.cpython-311-aarch64-linux-gnu.so` 단일 파일로 깔린다.

**face-reidentification 교체 이득의 크기가 여기 달려 있다.**

### B.3 789MB 분해 — 어디가 범인인가

통째로는 손댈 곳을 못 정한다. 한 줄씩 끊어서:

```
import cv2
import torch
from ultralytics import YOLO
import mediapipe
import dlib
```

각각의 RSS 증가량. 그리고 모델 적재분을 따로:

```
YOLO('/home/pi/.model/object/yolo26s.onnx', task='detect')
```

**`import torch` 한 줄의 숫자가 ultralytics 제거의 실제 이득**이고,
`YOLO load` 숫자가 onnxruntime 직접 호출로 갈 때의 기준선이다.

### B.4 `Face()` RSS 증가량

지연 로딩 그룹(A/B/C/D) 분할의 실제 이득.
cv2·mediapipe·dlib을 `Detect`와 공유하므로 증가분은 789보다 훨씬 작을 것.

가능하면 그룹별로도:
- A만 (face-detection)
- A+B (+ age-gender, emotion)
- A+C (+ dlib predictor, encoder)
- A+D (+ mediapipe landmarker)

### B.5 YOLO 추론 지연 — imgsz 포함

```
imgsz 640 / 480 / 320 각각의 평균 지연 (워밍업 후 5회)
```

**현재 `yolo26s`가 파이에서 얼마나 걸리는지 아직 모른다.**
지금이 이미 s급이니, 현재 지연이 견딜 만하면 yolo11s로 가도 비슷할 것이다.

속도가 모자라면 **모델 급수보다 imgsz를 먼저 줄인다**
(640→320은 연산량 1/4, n↔s 차이 3배보다 지렛대가 크다).

### B.6 CMA / GPU 메모리

```
grep -i cma /proc/meminfo     # CmaTotal / CmaFree
vcgencmd get_mem gpu
```

picamera2의 CMA는 커널이 부팅 시 떼어가므로 `free`에 안 보인다.
`cma=256M` 같은 게 잡혀 있으면 2GB 중 256MB가 이미 없는 셈.

### B.7 서비스별 PSS / RSS

```
smaps_rollup의 Pss 합 vs RSS
```

RSS 합과 PSS 차이가 클수록 프로세스 간 라이브러리 중복이 크고,
**7단계 프로세스 통합의 이득이 크다.**

### B.8 openvino-dev 의존성

```
pip show openvino-dev | grep Requires
```

여기 `scipy`나 `opencv-python`이 나오면, **openvino-dev를 먼저 빼야**
그것들을 안전하게 지울 수 있다. 순서가 있다.

### B.9 e5-small 관련 (4단계 이후)

- 파이의 OpenVINO 버전이 vapi-od의 e5 IR 포맷을 읽는지
- ARM에서 INT8 추론이 제대로 가속되는지 (안 되면 FP32로 떨어져 메모리 2배)
- 질의 1건 인코딩 지연
- **대안**: onnxruntime으로 돌렸을 때와 비교

### B.10 정책 판단용 (측정 아님)

- `Oled7735`(ST7735S)가 현행 제품에 쓰이는지, `bl=cs_pin`이 의도인지
- `recognize()`가 dlib 랜드마크에 의존하는지 → C그룹 경계 확정
- `facedb`에 현장 등록된 얼굴이 얼마나 쌓여 있는지 → 교체 시 재등록 비용
- `threshold=0.4`가 교재·예제에 하드코딩되어 있는지
- `vision_classify`를 학생 예제나 `tools`에서 직접 쓰는 곳이 있는지
  (있으면 TF가 상시 점유가 된다)
- `tools/pibo/lib.py`의 `Pibo` 클래스가 openpibo의 어디까지 끌어오는지
- `yolo26s.onnx`(145행) / `yolo11s.onnx`(233행) 두 경로가 의도된 것인지
- `speech.py`의 `analysis()`가 `https://oe-napi.circul.us`를 호출한다.
  온디바이스 전제와 충돌. 의도된 잔존인지 정리 대상인지
- LLM과 비전이 **동시에** 필요한 수업 시나리오가 있는지
- RAG 지식베이스 예상 규모 (교과 단원 몇 개 분량)
- PC(vapi-od)에서 학습한 모델을 파이보로 옮기는 시나리오가 실제 수업에 있는지
- 교실에서 여러 명이 동시에 카메라에 잡히는 상황을 얼마나 상정해야 하는지

---

## C. 기록 양식

측정 후 A절에 다음 형식으로 추가한다.

```
| 항목 | 값 | 측정일 | 조건 |
|---|---|---|---|
| 예: import torch RSS | 000 MB | 2026-00-00 | 단독 프로세스, 워밍업 없음 |
```

**조건을 반드시 적을 것.** 워밍업 여부, 동시 실행 중인 서비스, imgsz 등에 따라
숫자가 크게 달라진다.
