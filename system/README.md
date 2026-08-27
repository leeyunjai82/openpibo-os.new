# system/ — 부팅할 때 도는 것들

기기가 켜질 때 이 폴더의 것들이 순서대로 돈다.
**보드(파이보 / 파이브레인)에 따라 갈리는 지점을 여기 다 적어 둔다.**

## 부팅 순서

```
init                          ← 부팅 시 한 번 (rc.local / systemd)
 ├ /media/usb/update.zip 있으면 복구하고 끝
 ├ 호스트명을 시리얼로 (바뀌면 재부팅)
 ├ /home/pi/{code,myimage,myaudio,mymodel} 생성
 ├ /home/pi/.board 확인            ← 보드 판별. 없으면 pibo 로 폴백 + 경고
 ├ systemd 유닛 링크 확인          ← units/install.sh
 ├ sudo servo init                 ← 파이보만 (다리 서보)
 ├ systemctl start booting.service
 └ systemctl start ide.service

booting.service → booting.py      (:8080)
 ├ get_display()                   ← 파이보 SSD1306 / 파이브레인 ILI9341
 ├ DeviceControl()                 ← has_mcu 인 보드만 (파이보). 눈 LED 부팅 표시
 ├ uart_ctrl.start()               ← /dev/ttyGS0 USB 가젯 시리얼 (보드 공통)
 ├ boot()  스플래시 + 네트워크 대기
 └ wifi_update() 10초마다 — 무선 끊기면 hotspot.sh 로 AP 모드

ide.service → ide/run_ide.py      (:80)
 └ 필요할 때 tools / classify / llama-server 를 systemctl 로 번갈아 켠다
```

## 보드에 따라 갈리는 지점

| 파일 | 무엇이 갈리나 | 어디서 정해지나 |
|---|---|---|
| `init` | `servo init` 실행 여부 | `/home/pi/.board` |
| `booting.py` | 디스플레이 클래스 | `openpibo.oled.get_display()` |
| `booting.py` | MCU 제어 (`mcu_control`) 자체를 import 하는지 | `BOARD.features.has_mcu` |
| `booting.py` | 스플래시 이미지, OS 버전 겹쳐쓰기, 진행 표시 문자 | `BOARD.boot.*` |
| `network_disp.py` | 글자 크기와 줄 좌표 전체 | `BOARD.network_disp.*` |

**`if board == 'pibo'` 를 새로 쓰지 말 것.** 값이 모자라면
`openpibo/profiles/*.toml` 에 키를 추가한다.

## 보드 정하기

```bash
sudo bash system/set_board.sh pibrain   # 설정
bash system/set_board.sh                # 지금 값 확인
```

`/home/pi/.board` 에 이름 한 줄을 쓰고 `config.json` 의 `board` 키도 맞춘다.
이미 떠 있는 서비스는 다시 시작해야 반영된다.

## systemd 유닛

`units/` 에 있다. `/etc/systemd/system/` 으로 **심볼릭 링크**하므로
레포를 갱신하면 유닛도 같이 갱신된다.

```bash
sudo bash system/units/install.sh                   # 링크
sudo systemctl enable booting.service ide.service   # 부팅 시 자동 시작
```

`tools` / `classify` / `llama-server` 는 **enable 하지 않는다.**
셋 다 카메라·오디오·모델 슬롯을 독점해서 동시에 뜨면 2GB 에서 OOM 이다.
`ide.service` 가 필요할 때 하나씩 켜고 나머지를 끈다
(`docs/plan/00-decisions.md` 4.3).

### llama-server.service 는 아직 비어 있다

기기의 `/etc/systemd/system/llama-server.service` 에만 있고 레포에 없다.
**컨텍스트 길이 `-c` 가 그 안에 있는데, 코드 어디에도 그 값이 없다.**
RAG 청크 상한을 정하는 숫자라 추측으로 채우면 안 된다.

```bash
sudo bash system/units/capture-from-device.sh   # 기기에서 실물을 떠 온다
git diff system/units/                          # 확인하고 커밋
```

떠 오기 전까지 `install.sh` 는 이 유닛만 건너뛴다.
지금 돌고 있는 설정을 빈 값으로 덮어쓰지 않기 위해서다.

## 이 폴더의 나머지

| 파일 | 하는 일 | 보드 |
|---|---|---|
| `system.sh` | 시리얼·OS버전·온도·메모리·IP·SSID 를 콤마로 뱉는다 | 공통 |
| `wifi.py` | `nmcli` 로 AP 스캔 | 공통 |
| `conwifi.sh` | 와이파이 접속 (open / wpa-psk / wpa-enterprise) | 공통 |
| `hotspot.sh` | 무선이 없을 때 AP 모드 | 공통 |
| `network_disp.py` | 화면에 IP/SSID/시리얼 표시 | 레이아웃이 갈림 |
| `clear_disp.py` | 화면 지우기 | 공통 (`get_display()`) |
| `uart_ctrl.py` | `/dev/ttyGS0` USB 가젯 시리얼로 코드 실행 | 공통 |
| `mcu_control.py` | `/dev/ttyS0` 로 ATmega328P 제어 | **파이보 전용** |
| `opening.mp3` | 부팅음 | 공통 |
| `pibo.jpg` | 파이보 스플래시 (128x64) | 파이보 |
| `pibrain320.jpg` | 파이브레인 스플래시 (240x320) | 파이브레인 |
| `themaker.jpg` / `themaker320.jpg` | 대체 스플래시 (미사용) | — |
