# tools — 체험 도구 (:50000, 셸에서는 `/tools/`)

**보드마다 다른 앱이 뜬다.** `launch.py` 가 고른다.

    tools/
      launch.py     보드를 보고 아래 둘 중 하나를 띄운다
      pibo/         socket.io    장치 / 모션 / 비전 / 음성 / 시뮬
      pibrain/      REST + SSE   버튼 / LED / 카메라·비전 / 음성합성 / LCD
      measure/      실측 스크립트 (체험 앱과 무관 — docs/plan/01-measurements.md 용)

두 앱은 **같은 깊이에 나란히** 둔다. 한쪽만 `tools/` 바로 밑에 있으면
"파이보가 본체고 파이브레인은 곁가지"처럼 읽히는데, 둘은 대등하다.

하드웨어가 달라 화면이 같을 수가 없다. 왜 합치지 않았는지는
`tools/pibrain/README.md` 와 `docs/plan/00-decisions.md` 1.4 에 있다.

## 띄우기

    # 서비스 (system/units/tools.service 가 이렇게 부른다)
    python3 tools/launch.py --port 50000

    # 보드를 강제로 지정 (시험용)
    python3 tools/launch.py --board pibrain --port 50000

`--board` 를 안 주면 `openpibo.board.BOARD` 가 정한다
(`OPENPIBO_BOARD` 환경변수 → `/home/pi/.board` → `config.json`).

## 필요한 것

    pip3 install fastapi_socketio uvicorn      # 파이보 (socket.io)
    # 파이브레인은 cv2 를 쓴다 — requirements/vision.txt 참고

## 시험

    python3 test/test_tools_launch.py
