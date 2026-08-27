"""
화면을 지운다. 보드가 무엇이든 그 보드의 디스플레이를 지운다.
"""

def run():
  try:
    from openpibo.oled import get_display

    o = get_display()
    o.clear()
    ret = True, ""
  except Exception as ex:
    ret = False, str(ex)
  finally:
    return ret


if __name__ == "__main__":
  print(run())
