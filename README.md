# ICDF_eco — 탄소 인지 AI 데이터센터 스케줄러

2026 Energy ICDF · 연세대학교 YAX

하루 전에 세운 계획은 유지하고, 당일 예측 오차가 계속 이어질 것 같을 때만 계획을 고치는 스케줄러입니다.
부스에서는 랙 두 개로 비교합니다. B 랙은 구글식 하루 전 고정, D2 랙은 저희 방식입니다.

전체 설명은 [docs/프로젝트_설명.md](docs/프로젝트_설명.md), 지금까지 한 일은 [docs/진행상황.md](docs/진행상황.md), 영국 탄소 데이터 자료는 [docs/참고자료.md](docs/참고자료.md)에 있습니다.

| 문서 | 언제 보나 |
|---|---|
| [docs/프로젝트_소개.md](docs/프로젝트_소개.md) | 프로젝트를 처음 접할 때 (쉬운 설명) |
| [docs/시연_가이드.md](docs/시연_가이드.md) | 부스에서 시연을 켜고 설명할 때 |
| [docs/아두이노_연결후_할일.md](docs/아두이노_연결후_할일.md) | 아두이노를 메인 PC에 처음 연결할 때 |
| [docs/Jetson_연결후_할일.md](docs/Jetson_연결후_할일.md) | Jetson 2대를 연결할 때 |

## 폴더 구성

| 폴더 | 내용 | 돌아가는 곳 |
|---|---|---|
| `firmware/fan_led/` | 아두이노 스케치. 팬 4개와 WS2812 LED 바를 시리얼 명령으로 제어 | 아두이노 Uno |
| `controller/` | 배속 시연 엔진. 탄소 신호 재생, B·D2 스케줄러, 아두이노 제어, CSV 기록 | 메인 PC |
| `data/` | 영국 탄소 데이터 내려받기 스크립트. 받은 CSV는 git에 올리지 않음 | 메인 PC |
| `gui/` | 시연 화면. 시연 엔진이 `--gui`로 띄움 | 메인 PC |
| `jetson/` | AI 작업 실행과 전력 측정 (`agent.py`). 연결 방법은 `jetson/README.md` | Jetson Orin Nano 2대 |
| `sim/` | 하루 전 예측 학습 (`train_forecast.py`), 오차 지속 학습 (`train_error_persistence.py`), 장기 시뮬레이션 (`run_longterm.py`) | 메인 PC |
| `docs/` | 배선도, 시스템 흐름도, 프로젝트 설명 | |

## 처음 설정 (데스크톱)

```bash
git clone <이 저장소 주소>
cd icdf-eco
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 한 번에 켜기 (메인 PC, 우분투)

```bash
icdf                 # = ./demo.sh  아두이노·Jetson을 찾아서 붙이고 화면을 엶
icdf --dry-run       # 아두이노 없이
icdf --no-jetson     # Jetson 없이
icdf --rehearsal     # 리허설 (하루 약 24초)
icdf --detail        # 자세한 화면
icdf --classic       # 예전 화면
icdf 2025-06-15      # 날짜 바꾸기
```
`icdf` 단축어는 `~/.bash_aliases`에 `alias icdf='~/icdf-eco/demo.sh'`로 등록되어 있습니다 (새 터미널부터 적용).
시연 중 조작은 브라우저 화면에서 합니다 (Enter 시작, 스페이스 구름). 우분투 터미널에서는 `s`/`c`/`q` 키가 동작하지 않으니 끌 때는 Ctrl+C.

## 실행 순서

1. **아두이노**: Arduino IDE에서 `firmware/fan_led/fan_led.ino`를 엽니다. 라이브러리 관리자에서 `Adafruit NeoPixel`을 설치하고 업로드합니다.
2. **탄소 데이터 받기**:
   ```bash
   python data/fetch_uk_carbon.py --start 2024-01-01 --end 2024-03-01
   ```
   `data/raw/uk_carbon_20240101_20240301.csv`가 생깁니다.
   2017-09-12 ~ 2026-11-16 전체 데이터(`uk_carbon_20170912_20261117.csv`, 4MB)는 이미 저장소에 들어 있으니, 그 뒤 날짜가 필요할 때만 받으면 됩니다.
3. **시연 (부스용)**: 브라우저에 화면이 뜨고, 화면의 [시작]을 누르면 하루를 2분으로 재생합니다. 끝나면 [다시 시작].
   ```bash
   python -m controller.main --day 2025-03-10 --ours --gui --port COM3
   python -m controller.main --day 2025-03-10 --ours --gui --dry-run      # 아두이노 없이 화면만
   ```
   - 화면에서: [구름 올리기] 버튼 또는 스페이스 = 구름, Enter = 시작
   - 터미널에서: `s` 시작, `c` 구름, `q` 종료
   - 화면 주소는 http://127.0.0.1:8000/ 입니다. 모니터에서 F11로 전체 화면, 글자가 작으면 Ctrl + 마우스 휠
   - 리허설 때 빨리 보고 싶으면 `--slot-seconds 0.5` (30분 한 칸을 0.5초로)
   - `--ours`는 우리 하루 전 예측을 씁니다 (2024년 이후 날짜만)

   리허설이나 테스트 때는 구름 구간을 미리 정하고 배속 없이 바로 결과를 볼 수 있습니다.
   ```bash
   python -m controller.main --day 2024-01-15 --dry-run --fast --cloud 10-11   # 짧은 구름: D2 변경 없음
   python -m controller.main --day 2024-01-15 --dry-run --fast --cloud 8-22    # 긴 구름: D2만 작업을 뒤로 옮김
   ```

포트 번호는 장치 관리자 → 포트(COM & LPT)에서 확인합니다.

## 아두이노 (115200 baud)

| 방향 | 문자열 | 뜻 |
|---|---|---|
| PC → 아두이노 | `1 1` ~ `4 1` | 팬 1~4번 켜기 (`0`이면 끄기) |
| 아두이노 → PC | `LUX 523.4` | 조도센서 값, 0.2초마다 (센서를 못 읽으면 `LUX -1`) |

팬 번호와 핀: 1 = D3, 2 = D5 (B 랙) / 3 = D6, 4 = D11 (D2 랙). 조도센서 BH1750: SDA = A4, SCL = A5. LED 바는 쓰지 않습니다.

## 구름 스테이션 (조도센서)

- [시작]을 누르는 순간의 밝기가 기준입니다. **시작할 때는 센서를 가리지 마세요.**
- 재생 중에 센서를 가리면 가린 비율만큼 탄소 신호가 올라갑니다 (완전히 가리면 +150, 반쯤 가리면 +75).
  15%보다 적게 가려진 것은 무시합니다. 화면 오른쪽 위에 "빛 가림 62% → 탄소 +93"으로 보입니다.
- 화면의 [구름 올리기] 버튼(+120)도 그대로 됩니다. 둘 다 있으면 큰 쪽을 씁니다.
- 숫자는 `controller/config.py`의 `CLOUD_SENSOR_*`에서 바꿉니다. 센서가 없거나 너무 어두우면 버튼만 씁니다.

## 할 일 (우선순위 순)

- [x] 팬이 LOW에서 멈추는지 확인
- [ ] 새 펌웨어 올리고 `--gui --port`로 팬·LED·화면 같이 확인
- [ ] 리허설: 날짜, 구름 길이, 람다 정하기
- [ ] 구름 입력을 키보드에서 센서로 바꿀지 결정
- [x] 시연 화면 (`gui/index.html`)
- [ ] Jetson 작업 실행과 전력 전송 (코드 완성, 가짜 Jetson으로 시험함. 실제 보드 연결 남음)
- [x] 하루 전 예측 모델 첫 버전 (Ridge, 기준선보다 MAE 약 15% 낮음) → `sim/README.md`
- [x] 당일 오차 지속 모델 (D2가 사용, 평균 MAE 28.4 vs D1 33.7) → `sim/README.md`
- [x] 장기 시뮬레이션: D2 회복률 9.6%, 변경은 매 시점 재계획의 절반 → `sim/README.md`
- [ ] 보정에 '앞당기기' 추가, 작업 큐 현실화
