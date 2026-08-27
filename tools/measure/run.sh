#!/bin/bash
# openpibo-os 실측 스크립트
#
# 파이 기기에서 실행한다. 결과를 docs/plan/01-measurements.md 의 A절에 옮겨 적을 것.
#
#   bash tools/measure/run.sh              전체
#   bash tools/measure/run.sh disk         디스크만
#   bash tools/measure/run.sh mem          메모리만
#   bash tools/measure/run.sh llm          LLM 관련만
#   bash tools/measure/run.sh yolo         YOLO 지연만
#
# 주의: mem / yolo 는 실제로 모델을 올린다. 다른 서비스가 돌고 있으면
#       숫자가 흔들리므로 가능하면 정지 후 측정할 것.

set -u

PY="${PY:-/home/pi/.pyenv/bin/python3}"
SP="$($PY -c 'import site;print(site.getsitepackages()[0])' 2>/dev/null || echo /home/pi/.pyenv/lib/python3.11/site-packages)"
MODE="${1:-all}"

hr() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }

# ---------------------------------------------------------------- 시스템
sys() {
  hr "시스템"
  date -Iseconds
  echo "python : $PY"
  echo "site   : $SP"
  uname -srm
  cat /etc/os-release 2>/dev/null | grep PRETTY_NAME
  echo
  free -m
  echo
  df -h /
  echo
  echo "-- CMA / GPU --"
  grep -i cma /proc/meminfo || echo "(CMA 항목 없음)"
  vcgencmd get_mem gpu 2>/dev/null || echo "(vcgencmd 없음)"
  echo
  echo "-- 스로틀링 (0x0 이 정상) --"
  vcgencmd get_throttled 2>/dev/null || true
  vcgencmd measure_temp 2>/dev/null || true
}

# ---------------------------------------------------------------- 디스크
disk() {
  hr "site-packages 용량"
  for p in torch tensorflow ultralytics mediapipe cv2 onnxruntime openvino \
           openvino_telemetry dlib scipy pandas numpy PIL picamera2; do
    [ -e "$SP/$p" ] && du -sh "$SP/$p" 2>/dev/null
  done
  echo
  du -sh "$SP" 2>/dev/null | sed 's/$/   (site-packages 전체)/'

  hr "dlib 본체 (site-packages/dlib 은 16K 껍데기일 수 있음)"
  ls -lh "$SP"/_dlib* 2>/dev/null || echo "(_dlib*.so 없음)"

  hr "dlib 모델 파일"
  DLIBDIR=$($PY -c 'import openpibo_dlib_models,os;print(os.path.dirname(openpibo_dlib_models.__file__))' 2>/dev/null)
  if [ -n "${DLIBDIR:-}" ] && [ -d "$DLIBDIR" ]; then
    echo "경로: $DLIBDIR"
    du -ah "$DLIBDIR" 2>/dev/null | sort -h | tail -10
  else
    echo "(openpibo_dlib_models 경로를 찾지 못함)"
  fi

  hr "모델 디렉토리"
  du -sh /home/pi/.model/* 2>/dev/null
  echo
  du -ch /home/pi/.model/face/*/*.bin 2>/dev/null | tail -1
  echo
  ls -lh /home/pi/.model/object/ 2>/dev/null

  hr "openvino-dev 의존성 (scipy / opencv-python 을 끌어왔는지)"
  $PY -m pip show openvino-dev 2>/dev/null | grep -i requires || echo "(openvino-dev 미설치)"

  hr "opencv 중복 확인"
  $PY -m pip list 2>/dev/null | grep -i opencv || true
}

# ---------------------------------------------------------------- 메모리
mem() {
  hr "실행 중인 서비스 RSS / PSS"
  printf "%-7s %-18s %8s %8s\n" PID NAME RSS_MB PSS_MB
  for p in $(pgrep -f 'run_ide|booting|run_tools|run_classify|llama-server' 2>/dev/null); do
    NAME=$(ps -o comm= -p "$p" 2>/dev/null)
    RSS=$(( $(ps -o rss= -p "$p" 2>/dev/null || echo 0) / 1024 ))
    PSS=$(( $(awk '/^Pss:/{s+=$2} END{print s+0}' "/proc/$p/smaps_rollup" 2>/dev/null || echo 0) / 1024 ))
    printf "%-7s %-18s %8s %8s\n" "$p" "$NAME" "$RSS" "$PSS"
  done
  echo "RSS 합과 PSS 합의 차이가 클수록 프로세스 간 라이브러리 중복이 크다 (통합 이득)"

  hr "import 별 RSS 증가량"
  echo "(각각 별도 프로세스. 워밍업 없음)"
  for m in "import cv2" \
           "import numpy" \
           "import torch" \
           "from ultralytics import YOLO" \
           "import mediapipe" \
           "import dlib" \
           "import onnxruntime" \
           "import openvino" \
           "import tflite_runtime.interpreter" \
           "import tensorflow"; do
    $PY - "$m" <<'EOF' 2>/dev/null
import sys, os
stmt = sys.argv[1]
def rss():
    for line in open('/proc/self/status'):
        if line.startswith('VmRSS:'):
            return int(line.split()[1])
    return 0
b = rss()
try:
    exec(stmt)
    print("%-38s %6d MB" % (stmt, (rss()-b)//1024))
except Exception as e:
    print("%-38s   실패: %s" % (stmt, type(e).__name__))
EOF
  done

  hr "클래스 생성 시 RSS 증가량"
  echo "(openpibo import 후 기준선 대비)"
  $PY - <<'EOF' 2>/dev/null
def rss():
    for line in open('/proc/self/status'):
        if line.startswith('VmRSS:'):
            return int(line.split()[1])
    return 0

base = rss()
print("%-38s %6d MB   (기준선)" % ("(시작)", base//1024))

try:
    from openpibo.vision_detect import Detect
    b = rss(); d = Detect()
    print("%-38s %6d MB" % ("Detect()", (rss()-b)//1024))
except Exception as e:
    print("Detect() 실패: %r" % (e,))

try:
    from openpibo.vision_face import Face
    b = rss(); f = Face()
    print("%-38s %6d MB" % ("Face()", (rss()-b)//1024))
except Exception as e:
    print("Face() 실패: %r" % (e,))

print("%-38s %6d MB   (총계)" % ("(합계)", rss()//1024))
EOF

  hr "Face 모델 그룹별 (지연 로딩 이득 추정)"
  $PY - <<'EOF' 2>/dev/null
def rss():
    for line in open('/proc/self/status'):
        if line.startswith('VmRSS:'):
            return int(line.split()[1])
    return 0
try:
    import openpibo_dlib_models as M
    from openvino.runtime import Core
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    import dlib
    base = rss()

    ie = Core()
    b = rss()
    ie.compile_model(ie.read_model("/home/pi/.model/face/detection/face-detection-retail-0004.xml"), "CPU")
    print("%-38s %6d MB" % ("A. face-detection", (rss()-b)//1024))

    b = rss()
    ie.compile_model(ie.read_model("/home/pi/.model/face/age-gender/age-gender-recognition-retail-0013.xml"), "CPU")
    ie.compile_model(ie.read_model("/home/pi/.model/face/emotion/emotions-recognition-retail-0003.xml"), "CPU")
    print("%-38s %6d MB" % ("B. age-gender + emotion", (rss()-b)//1024))

    b = rss()
    dlib.shape_predictor(M.filepath("shape_predictor_68_face_landmarks.dat"))
    dlib.face_recognition_model_v1(M.filepath("dlib_face_recognition_resnet_model_v1.dat"))
    print("%-38s %6d MB" % ("C. dlib predictor + encoder", (rss()-b)//1024))

    b = rss()
    mp_vision.FaceLandmarker.create_from_options(
        mp_vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(
                model_asset_path='/home/pi/.model/face/landmark/face_landmarker.task'),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_faces=2, output_face_blendshapes=True))
    print("%-38s %6d MB" % ("D. mediapipe landmarker", (rss()-b)//1024))
except Exception as e:
    print("그룹 측정 실패: %r" % (e,))
EOF
}

# ---------------------------------------------------------------- LLM
llm() {
  hr "llama-server 유닛 (여기에 -c 값이 있다)"
  systemctl cat llama-server 2>/dev/null || echo "(유닛 없음 — 이름 확인 필요)"

  hr "llama-server 프로세스"
  pgrep -a -f llama-server || echo "(실행 중 아님)"
  for p in $(pgrep -f llama-server 2>/dev/null); do
    echo "PID $p  RSS $(( $(ps -o rss= -p $p)/1024 )) MB"
  done

  hr "모델 파일"
  ls -lh /home/pi/.model/*.gguf /home/pi/.model/**/*.gguf 2>/dev/null || echo "(gguf 못 찾음)"

  hr "llama-bench 안내"
  cat <<'EOF'
pp(prompt processing) 수치가 RAG 청크 상한을 결정하는 유일한 숫자다.
모델 경로를 확인한 뒤 직접 실행할 것:

  llama-bench -m /home/pi/.model/<model>.gguf -p 128 -n 64 -t 4

  pp = prefill  (주입 컨텍스트 처리 속도) ← 이 숫자가 중요
  tg = 생성     (토큰 출력 속도)
EOF
}

# ---------------------------------------------------------------- YOLO
yolo() {
  hr "YOLO 추론 지연 (imgsz 별)"
  $PY - <<'EOF' 2>/dev/null
import glob, os, time
import numpy as np
try:
    from ultralytics import YOLO
except Exception as e:
    raise SystemExit("ultralytics import 실패: %r" % (e,))

cands = sorted(glob.glob('/home/pi/.model/object/*.onnx')) + \
        sorted(glob.glob('/home/pi/.model/object/*.pt'))
if not cands:
    raise SystemExit("모델을 찾지 못함: /home/pi/.model/object/")

img = None
for pat in ('/home/pi/myimage/*.jpg', '/home/pi/myimage/*.png'):
    f = sorted(glob.glob(pat))
    if f:
        import cv2
        img = cv2.imread(f[0]); break
if img is None:
    img = (np.random.rand(480, 640, 3) * 255).astype('uint8')
    print("(테스트 사진이 없어 무작위 이미지 사용 — 검출 결과는 무의미, 지연만 유효)")

def rss():
    for line in open('/proc/self/status'):
        if line.startswith('VmRSS:'):
            return int(line.split()[1])
    return 0

for path in cands:
    b = rss()
    try:
        m = YOLO(path, task='detect')
    except Exception as e:
        print("%-28s 로드 실패: %s" % (os.path.basename(path), type(e).__name__)); continue
    load = (rss() - b) // 1024
    m(img, verbose=False)                      # 워밍업
    print("\n%s   (적재 +%d MB)" % (os.path.basename(path), load))
    for sz in (640, 480, 320):
        try:
            t = time.time()
            for _ in range(5):
                m(img, imgsz=sz, verbose=False)
            print("   imgsz %3d : %5d ms" % (sz, (time.time()-t)/5*1000))
        except Exception as e:
            print("   imgsz %3d : 실패 %s" % (sz, type(e).__name__))
EOF
}

case "$MODE" in
  all)  sys; disk; mem; llm; yolo ;;
  sys)  sys ;;
  disk) sys; disk ;;
  mem)  sys; mem ;;
  llm)  sys; llm ;;
  yolo) sys; yolo ;;
  *)    echo "사용법: bash tools/measure/run.sh [all|sys|disk|mem|llm|yolo]"; exit 1 ;;
esac

hr "완료"
echo "결과를 docs/plan/01-measurements.md 의 A절에 옮겨 적을 것."
echo "측정 조건(동시 실행 서비스, 워밍업 여부)도 함께 기록할 것."
