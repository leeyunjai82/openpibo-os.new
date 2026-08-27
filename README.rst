openpibo-python
===============

교육용 로봇 파이보(pibo) / 파이브레인(pibrain) 공용 파이썬 패키지.

두 보드가 같은 코드를 쓰고, 차이는 보드 프로파일 한 곳에만 둔다::

    from openpibo.board import BOARD

    BOARD.name                 # 'pibo' | 'pibrain'
    BOARD.features.has_legs    # True | False

    from openpibo.oled import get_display
    from openpibo.device import get_device

    oled = get_display()       # 보드에 맞는 디스플레이 클래스
    device = get_device()      # 보드에 맞는 device 클래스

보드는 ``/home/pi/.board`` 또는 환경변수 ``OPENPIBO_BOARD`` 가 정한다.

설치::

    pip install openpibo_python-*.whl              # 라이브러리만
    pip install "openpibo_python-*.whl[all]"       # 의존성까지 전부

무거운 의존성(opencv, dlib, mediapipe, picamera2)은 기본 설치에 넣지 않았다.
기기에는 이미 깔려 있고, PC 에서 받으려 하면 dlib 소스 빌드로 들어간다.

See `openpibo-Guide <https://themakerrobot.github.io/openpibo-os.pibo/build/html/index.html>`__ for more information.
