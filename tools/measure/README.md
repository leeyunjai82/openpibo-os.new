# tools/measure — 실측 스크립트

```bash
bash tools/measure/run.sh              # 전체
bash tools/measure/run.sh disk         # 디스크만
bash tools/measure/run.sh mem          # 메모리만
bash tools/measure/run.sh llm          # LLM 관련만
bash tools/measure/run.sh yolo         # YOLO 지연만
```

**기기에서 돌린다.** 결과를 `docs/plan/01-measurements.md` A절에 옮겨 적고,
**측정 조건(동시 실행 중인 서비스, 워밍업 여부, imgsz)도 함께 적는다.**
조건이 없으면 나중에 그 숫자를 못 쓴다.

## 먼저 알아 둘 것

- **`mem` 과 `yolo` 는 실제로 모델을 올린다.** 다른 서비스가 돌고 있으면 숫자가
  흔들린다. 가능하면 정지하고 재실행할 것.

  ```bash
  sudo systemctl stop tools.service classify.service llama-server.service
  bash tools/measure/run.sh mem
  ```

- **`mem` 의 dlib 그룹별 측정은 모델 경로를 하드코딩했다.**
  경로가 다르면 그 블록만 실패하고 나머지는 계속 돈다. 통째로 죽지 않는다.

- **`yolo` 모드는 `/home/pi/myimage/` 에서 사진을 찾는다.** 없으면 무작위 이미지를
  쓴다. 그 경우 **지연만 유효하고 검출 결과는 무의미하다.** 스크립트가 그렇게 찍어 준다.

- **`llama-bench` 는 안내만 한다.** 모델 경로를 스크립트가 알 수 없어서다.
  `llm` 모드가 gguf 를 찾아 주니 그 경로로 직접 돌릴 것.

  ```bash
  llama-bench -m /home/pi/.model/<model>.gguf -p 128 -n 64 -t 4
  ```

  `pp`(prompt processing) 가 **RAG 청크 상한을 결정하는 유일한 숫자다.**

## 지금 제일 급한 것

`docs/plan/01-measurements.md` B.1 — 로드맵 3단계 판단에 필요하다.

1. `systemctl cat llama-server` 의 `-c` 값
   → `sudo bash system/units/capture-from-device.sh` 로 레포에 떠 오면 같이 해결된다
2. `llama-bench` 의 `pp` 수치
3. `import torch` 단독 RSS (B.3) — ultralytics 제거의 실제 이득
