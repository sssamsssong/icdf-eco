# ICDF_eco — 탄소 인지 AI 데이터센터 스케줄러

2026 Energy ICDF · 연세대학교 YAX

하루 전에 세운 계획은 유지하고, 당일 예측 오차가 계속 이어질 것 같을 때만 계획을 고치는 스케줄러입니다.
부스에서는 랙 두 개로 비교합니다. B 랙은 구글식 하루 전 고정, D2 랙은 저희 방식입니다.

전체 설명은 [docs/프로젝트_설명.md](docs/프로젝트_설명.md), 지금까지 한 일은 [docs/진행상황.md](docs/진행상황.md), 영국 탄소 데이터 자료는 [docs/참고자료.md](docs/참고자료.md)에 있습니다.

## 폴더 구성

| 폴더 | 내용 | 돌아가는 곳 |
|---|---|---|
| `firmware/fan_led/` | 아두이노 스케치. 팬 4개와 WS2812 LED 바를 시리얼 명령으로 제어 | 아두이노 Uno |
| `controller/` | 배속 시연 엔진. 탄소 신호 재생, B·D2 스케줄러, 아두이노 제어, CSV 기록 | 메인 PC |
| `data/` | 영국 탄소 데이터 내려받기 스크립트. 받은 CSV는 git에 올리지 않음 | 메인 PC |
| `gui/` | 시연 화면. 시연 엔진이 `--gui`로 띄움 | 메인 PC |
| `jetson/` | AI 작업 실행과 전력 측정 (아직 뼈대만 있음) | Jetson 2대 |
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

## 아두이노 시리얼 명령 (115200 baud)

| 보내는 문자열 | 동작 |
|---|---|
| `1 1` ~ `4 1` | 팬 1~4번 켜기 (`0`이면 끄기) |
| `9 0` ~ `9 100` | LED 바 색. 0 = 초록(깨끗함), 100 = 빨강(탄소 많음) |

팬 번호와 핀: 1 = D3, 2 = D5 (B 랙) / 3 = D6, 4 = D11 (D2 랙). LED 데이터는 D7.

## 할 일 (우선순위 순)

- [x] 팬이 LOW에서 멈추는지 확인
- [ ] 새 펌웨어 올리고 `--gui --port`로 팬·LED·화면 같이 확인
- [ ] 리허설: 날짜, 구름 길이, 람다 정하기
- [ ] 구름 입력을 키보드에서 센서로 바꿀지 결정
- [x] 시연 화면 (`gui/index.html`)
- [ ] Jetson 작업 실행과 전력 전송
- [x] 하루 전 예측 모델 첫 버전 (Ridge, 기준선보다 MAE 약 15% 낮음) → `sim/README.md`
- [x] 당일 오차 지속 모델 (D2가 사용, 평균 MAE 28.4 vs D1 33.7) → `sim/README.md`
- [x] 장기 시뮬레이션: D2 회복률 9.6%, 변경은 매 시점 재계획의 절반 → `sim/README.md`
- [ ] 보정에 '앞당기기' 추가, 작업 큐 현실화
