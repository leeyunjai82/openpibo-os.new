# openpibo-os 통합 · 개편 계획

파이보 / 파이브레인 소프트웨어 통합과 UX 전면 개편 계획.

**대상 하드웨어: Raspberry Pi 4B RAM 2GB, Bookworm, 온디바이스 실행.**
2GB가 모든 판단의 제약이다.

---

> **진행 상황 (2026-08-27)**
> -1단계와 0단계의 **코드 작업이 끝났다.** 실기 확인은 아직이다.
> 무엇이 됐고 무엇이 남았는지는 [02-roadmap.md](02-roadmap.md) 와
> [04-known-issues.md](04-known-issues.md) 의 상태 표시를 볼 것.
> 레포 최상위 [README.md](../../README.md) 에도 요약이 있다.

---

## 읽는 순서

| 문서 | 내용 | 언제 읽나 |
|---|---|---|
| **[03-discarded.md](03-discarded.md)** | **틀린 판단 기록** | **작업 시작 전 반드시** |
| [00-decisions.md](00-decisions.md) | 확정 사항과 근거 | 무엇을 왜 하는지 |
| [01-measurements.md](01-measurements.md) | 실측값 / 대기 항목 | 숫자가 필요할 때 |
| [02-roadmap.md](02-roadmap.md) | 0~7단계 작업 | 무엇부터 할지 |
| [04-known-issues.md](04-known-issues.md) | 발견된 버그 | 리팩터링 전 |

**`03-discarded.md`를 먼저 읽을 것.** 계획 수립 과정에서 추정으로 내렸다가
실측으로 뒤집힌 판단들이 정리되어 있다. dlib을 "미사용"으로 오판했던 것 같은
사고를 반복하지 않기 위한 문서다.

---

## 핵심 제약 3가지

### 1. `Detect()` 하나가 789 MB

실측값이다. 2GB의 40%.

- LLM(Gemma 3 1B, 800~950MB 추정)과 비전 모델은 **절대 공존 불가**
- 모델 슬롯 교대가 선택이 아니라 필수
- 현재 `systemctl stop llama-server`로 서로 죽이는 구조는 **우연히 옳았다**

### 2. 디스크는 문제가 아니다

28G 중 12G 여유. **의존성 제거의 명분은 RAM 하나뿐이고,
그 기준으로 실익이 있는 건 torch(ultralytics 경유)뿐이다.**

tensorflow가 디스크 1위(1.1G)지만 상시 import되지 않아 RAM 영향이 거의 없다.

### 3. 두 레포는 갈라진 게 아니라 복붙 후 드리프트

`device.py`는 바이트 단위로 동일하고 이미 `Device`/`DeviceByPiBrain` 보드 분기를
갖고 있다. 차이의 대부분이 로직이 아니라 **보드 상수**다.

**패턴은 이미 있는데 안 쓰고 있었다.**

---

## 로드맵 요약

```
0. 레포 통합 + board.py 프로파일        ← UX보다 먼저
1. 리버스 프록시 + 헬스체크
2. SPA shell + 설정 모달
3. yolo11s / yolo11s-pose 전환
4. 5모드 학습 이식 (손·표정은 추가 비용 0)
5. image 모드 → OpenVINO 백본 (TF 제거 동시)
6. Face / Detect 지연 로딩
7. (후순위) 프로세스 통합, ultralytics/torch 제거
```

**0단계를 UX 앞에 두는 이유**: SPA shell(2단계)이 가장 덩치 큰 작업이다.
통합 없이 진행하면 두 번 만들게 되고, 지금 `tools/`가 socket.io / REST+SSE로
갈라진 것과 같은 일이 반복된다.

---

## 작업 전 확인

```bash
bash tools/measure/run.sh
```

주의사항은 [`tools/measure/README.md`](../../tools/measure/README.md).
결과를 `01-measurements.md` A절에 옮겨 적는다.
**측정 조건(동시 실행 서비스, 워밍업 여부)도 함께 기록할 것.**

최소한 다음은 3단계 전에 필요하다:
- `systemctl cat llama-server` → `-c` 값
  (`sudo bash system/units/capture-from-device.sh` 로 레포에 떠 오면 같이 해결된다)
- `llama-bench`의 `pp` 수치 → RAG 청크 상한
- `import torch` 단독 RSS → ultralytics 제거의 실제 이득

---

## 상시 원칙

1. **하드웨어 값은 추측 금지.** 전압·전류 정격, 핀맵, 타이밍, 커넥터 핀 순서는
   데이터시트로 확인되지 않으면 "확인 필요"라고 명시한다
2. **메모리·디스크는 재고 나서 말한다.** 추정은 자릿수가 틀린다
3. **현장에서 돌고 있는 구성이 이론보다 우선한다**
4. **큰 작업을 두 번 하게 되는 순서인지 항상 확인한다**
5. **grep 결과의 부재를 근거로 쓰기 전에 검색 조건을 확인한다**
6. **한 보드의 사실을 다른 보드에 넘겨짚지 않는다**

---

## 참고 레포

- `themakerrobot/openpibo-os.pibo` — 통합 기준 (아카이브 예정)
- `themakerrobot/openpibo-os.pibrain` — 병합 대상 (아카이브 예정)
- `themakerrobot/vapi-od` — Intel AI PC용 "The Maker".
  RAG(`db_routes.py`), 5모드 학습(`train_routes.py`),
  라우팅 규약, 회귀 시험(`tools/schema_test`, `tools/e2e`)의 이식 원본
