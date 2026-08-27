# tools/legacy_pibrain — 파이브레인 구 Tools 서버 (동작하지 않음)

`themakerrobot/openpibo-os.pibrain` 의 `tools/` 를 **원본 그대로** 옮겨둔 것이다.
아카이브 예정인 레포에서 사라지지 않게 보존만 한 것이고, **어디에서도 실행되지 않는다.**

## 왜 병합하지 않았나

`docs/plan/00-decisions.md` 1.4 — `tools/` 는 두 보드가 아키텍처까지 갈라진 유일한 곳이다.

| | 파이보 (`tools/run_tools.py`) | 파이브레인 (이 폴더) |
|---|---|---|
| 전송 | socket.io (`fastapi_socketio`) | REST + SSE (`StreamingResponse`) |
| 포트 | 50000 | 50040 |
| 라이브러리 계층 | `tools/lib.py` 의 `Pibo` 클래스 | 서버 모듈 전역 |
| 줄 수 | 501 + 512 | 469 |

상수 차이가 아니라 **다시 짠 것**이다. 지금 한쪽으로 억지로 맞추면 판단이 섞이고,
`docs/plan/02-roadmap.md` 2단계(SPA shell)에서 어차피 한 번 더 갈아엎게 된다.

## 언제 없어지나

로드맵 2단계에서 SPA shell + 단일 origin으로 `tools/` 를 새로 만들 때
양쪽에서 살릴 기능을 골라 넣은 뒤 이 폴더를 지운다.

**그때까지 이 폴더의 코드를 "현행"으로 읽지 말 것.**
