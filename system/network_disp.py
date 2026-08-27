"""
부팅이 끝난 뒤 화면에 네트워크/시스템 정보를 띄운다.

**레이아웃이 보드마다 다르다.** 파이보는 128x64 흑백에 3줄, 파이브레인은
240x320 컬러에 6줄이다. 글자 크기도 13 대 20이다.
좌표를 코드에 박지 않고 보드 프로파일의 ``[network_disp]`` 절에서 읽는다.

  → openpibo/profiles/pibo.toml, openpibo/profiles/pibrain.toml
"""

import os

SYSTEM_DIR = os.path.dirname(os.path.abspath(__file__))


def collect():
  """system.sh 의 출력을 화면에 쓸 값으로 바꾼다."""

  v = os.popen(f'{SYSTEM_DIR}/system.sh').read().strip('\n').split(',')
  # v = [serial, os_version, uptime, temp, mem_total, mem_avail,
  #      wlan0, eth1, ssid, psk, identity, key_mgmt]

  if v[7] != "" and v[7][0:3] != "169":        # 유선이 먼저다
    ip, ssid = v[7], ""
  elif v[6] != "" and v[6][0:3] != "169":
    ip, ssid = v[6], v[8]
  else:
    ip, ssid = "", ""

  return {
    'sn': v[0][-8:],
    'ip': ip.strip(),
    'ssid': ssid,
    'os_version': v[1] if len(v) > 1 else '',
  }


def run():
  try:
    from openpibo.board import BOARD
    from openpibo.oled import get_display

    values = collect()
    o = get_display()
    o.set_font(size=BOARD.network_disp.font_size)

    for line in BOARD.network_disp.layout:
      x, y = line['xy']
      o.draw_text((x, y), line['text'].format(**values))

    o.show()
    ret = True, ""
  except Exception as ex:
    ret = False, str(ex)
  finally:
    return ret


if __name__ == "__main__":
  print(run())
