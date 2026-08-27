#!/usr/bin/env python3
"""
tools 서비스 진입점 — 보드에 맞는 tools 앱을 띄운다.

왜 갈라져 있나
  파이보와 파이브레인은 **다른 하드웨어**다. 화면이 같을 수가 없다.

    파이보     장치 / 모션 / 비전 / 음성 / 시뮬
               다리 12축 서보, 눈 네오픽셀, MCU 가 있어야 뜻이 있는 화면들이다.
    파이브레인 버튼 / LED / 카메라·비전 / 음성합성 / LCD
               다리도 MCU 도 없고 대신 버튼 4 개와 LCD 가 있다.

  파이브레인에 파이보 화면을 띄우면 "모션" 탭 전체가 죽은 화면이 된다.
  그래서 하나로 억지로 합치지 않고, 보드가 자기 앱을 고른다.

  두 앱 모두 ``run_tools:app`` 을 uvicorn 으로 띄우는 같은 모양이고,
  각자 자기 폴더의 ``static/``, ``templates/`` 를 상대 경로로 연다.
  그래서 고르는 일은 **작업 폴더를 정하는 것**이 전부다.

  포트는 양쪽 다 50000 이다. 셸 프록시(``ide/proxy.py``)가 ``/tools/`` 를
  50000 으로 보내므로, 어느 보드든 셸에서는 같은 주소로 열린다.
  (파이브레인 원본은 50040 이었다. 셸 뒤로 들어오면서 50000 으로 맞췄다.)
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

#: 보드 이름 -> tools 앱이 있는 폴더 (HERE 기준)
APP_DIR = {
  'pibo':    HERE,
  'pibrain': os.path.join(HERE, 'pibrain'),
}


def app_dir_for(board_name):
  """보드에 맞는 폴더. 모르는 보드면 파이보 것으로 간다(예전 그대로)."""
  return APP_DIR.get(board_name, HERE)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--port', type=int, default=50000)
  parser.add_argument('--board', default=None,
                      help='보드를 강제로 지정한다(시험용). 안 주면 openpibo.board 가 정한다.')
  args = parser.parse_args()

  name = args.board
  if name is None:
    from openpibo.board import BOARD
    name = BOARD.name

  workdir = app_dir_for(name)
  os.chdir(workdir)
  sys.path.insert(0, workdir)

  print(f'[tools] board={name} dir={workdir} port={args.port}', flush=True)

  import uvicorn
  uvicorn.run('run_tools:app', host='0.0.0.0', port=args.port, access_log=False)


if __name__ == '__main__':
  main()
