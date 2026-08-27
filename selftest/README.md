# selftest — 기기 검사 프로그램 (하드웨어가 있어야 돈다)

생산·수리 때 파이 위에서 돌려 부품이 다 살아 있는지 눈으로 확인하는 웹앱이다.
`themakerrobot/openpibo-os.pibo` 의 `test/` 를 그대로 옮겨 온 것이다.

    cd /home/pi/openpibo-os/selftest
    sudo /home/pi/.pyenv/bin/python3 test.py

`TEST_PG.bak` 이 바탕화면 실행기(런처) 원본이다.

## 왜 test/ 에서 옮겼나

`test/` 라는 이름 하나에 성격이 정반대인 둘이 들어 있었다.

    test/     하드웨어 없이 도는 개발용 시험   bash test/run.sh
    test/     하드웨어가 있어야 도는 기기 검사  sudo python3 test/test.py

`bash test/run.sh` 와 `test/test.py` 는 서로 아무 상관이 없다. 같은 폴더에 있으면
CI 에서 `test/` 를 통째로 돌리려다 하드웨어를 찾다 죽는다. 이름으로 갈랐다.

    test/       개발용 (CI, 노트북에서 돈다)
    selftest/   기기 검사 (파이에서, 하드웨어 있어야)
