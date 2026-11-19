"""시연 설정값. 부스에서 바꿀 일이 있는 숫자는 모두 여기에 둡니다."""

# 시간
SLOTS_PER_DAY = 48          # 30분 x 48 = 하루
SECONDS_PER_SLOT = 2.5      # 1시간 = 5초 → 하루 = 2분

# 랙
FANS_PER_RACK = 2           # 팬 하나 = 작업 슬롯 하나
FAN_IDS = {"B": [1, 2], "D2": [3, 4]}   # 아두이노 팬 번호
KWH_PER_SLOT = 0.25         # 작업 하나가 30분 동안 쓰는 전력량 (가정값, Jetson 실측으로 바꿀 것)

# 구름
CLOUD_DELTA = 120           # [구름 올리기] 버튼을 눌렀을 때 탄소 신호에 더하는 값 (gCO2/kWh)

# 구름 스테이션 (조도센서 BH1750). [시작]을 누를 때의 밝기를 기준으로, 가려진 비율만큼 탄소 신호를 올립니다.
#   가림 비율 = (기준 조도 - 지금 조도) / 기준 조도     → 탄소 신호 + CLOUD_SENSOR_MAX_DELTA x 가림 비율
# 버튼 구름과 같이 쓰면 둘 중 큰 값을 씁니다.
CLOUD_SENSOR = True             # False면 센서를 무시하고 버튼만 사용
CLOUD_SENSOR_MAX_DELTA = 150    # 완전히 가렸을 때 더하는 값 (gCO2/kWh)
CLOUD_SENSOR_DEADBAND = 0.15    # 가림 비율이 이보다 작으면 0으로 봄 (지나가는 사람 그림자, 센서 흔들림)
CLOUD_SENSOR_MIN_LUX = 20       # 기준 조도가 이보다 어두우면 센서를 쓰지 않음 (램프가 꺼져 있음)

# D2 보정
LAMBDA_G = 10.0             # 변경 비용 람다 (gCO2). 0이면 매번 재계획, 아주 크면 하루 전 고정과 같음
ERROR_EMA_ALPHA = 0.5       # 오차 이동평균 가중치 (클수록 최근 오차에 민감)
ERROR_DECAY = 0.85          # 오차가 한 슬롯 뒤에 남는 비율 (단기 예측). 0이면 바로 사라진다고 봄
MAX_CHANGES_PER_DAY = 20    # 변경 예산
# 계획을 한 번 바꿀 때 실제로 드는 탄소 (gCO2, 가정값). 작업을 멈췄다 다시 켜는 손실(체크포인트 저장·복구 등)을
# 탄소로 환산한 것으로, 4.5 g은 작업 1개의 약 3분치 전력입니다. 측정값이 아닙니다.
# 화면의 누적 탄소 = 실행 탄소 + 변경 횟수 x 이 값. 0이면 변경 비용을 세지 않습니다.
# 위 LAMBDA_G(옮길지 판단하는 문턱)와는 다른 숫자입니다. 스케줄러의 판단에는 영향이 없습니다.
CHANGE_COST_G = 4.5
ERROR_MODEL = "learned"        # "rule" = EMA x DECAY^h 규칙 / "learned" = controller/error_model.json (sim/train_error_persistence.py)

# 시연 화면 '근거' 패널에 보여 주는 학습 결과 (sim/README.md 2026-11-17 실행 결과, gCO2/kWh MAE).
# 모델을 다시 학습하면 이 숫자도 고치세요. 장기 시뮬레이션 수치는 sim/results/summary_test_default.csv에서 바로 읽습니다.
MODEL_FACTS = {
    "dayahead_model": "Ridge 회귀",
    "dayahead_train": "2017-09 ~ 2023 영국 전력망 (30분 단위)",
    "dayahead_mae": 37.2,          # 테스트 2025~
    "dayahead_baseline_mae": 47.3,  # 가장 좋은 단순 기준선 (이틀 전 같은 시각)
    "error_model": "선형 회귀 47개 (30분 ~ 23.5시간 뒤)",
    "error_train": "2024년 하루 전 예측 오차",
    "error_lags": 8,                # 최근 8칸 = 4시간
    "error_mae": 28.4,              # 평균 h 1~47
    "error_hold_mae": 33.7,         # '지금 오차 유지' (D1의 관점)
    "error_zero_mae": 37.2,         # '오차는 바로 사라진다' (B의 관점)
}

# LED 표시 범위 (gCO2/kWh → 0~100)
LED_MIN_G = 50
LED_MAX_G = 350

# 시리얼
BAUD = 115200

# Jetson (jetson/agent.py). 비워 두면 Jetson 없이 지금과 똑같이 동작합니다.
# 실행할 때 --jetson-b / --jetson-d2 로 덮어쓸 수 있습니다.
JETSON_HOSTS = {
    # "B": "http://10.0.0.11:8100",
    # "D2": "http://10.0.0.12:8100",
}
JETSON_TIMEOUT_S = 0.3      # 요청 하나를 기다리는 최대 시간
JETSON_RETRY_S = 5.0        # 연결이 끊기면 몇 초 뒤 다시 시도할지
JETSON_SUBTRACT_IDLE = True # 대기 전력은 빼고 '작업 때문에 늘어난 전력'만 셈
# 실측 탄소 = 칸 동안 잰 평균 W x 30분 x 탄소 집약도 x 이 배율.
# 1이면 Jetson 그대로 (몇 g 수준). 서버 한 대 규모로 보이려면 키우세요 (스케줄러 결정에는 영향 없음).
JETSON_POWER_SCALE = 1.0
# 화면 랙 카드에 '실측 탄소 g'를 보여 줄지. 두 Jetson은 같은 작업에도 늘어나는 전력이 달라서
# (2026-11-19: B +0.7 W, D2 +2.8 W) 그대로 보여 주면 D2가 더 나빠 보입니다. 끄면 실측 W만 보여 줍니다.
# 탄소 비교(큰 숫자)는 어느 쪽이든 가정 전력값을 씁니다. 터미널 출력과 CSV 기록에는 항상 남습니다.
GUI_SHOW_MEASURED_CO2 = False
# 화면에 세 번째 줄 'Reactive'를 같이 보여 줄지. Reactive = 지금 오차에만 반응 (문서의 D1, 학습 모델 없이 보정).
# 팬과 Jetson은 없고 화면에서만 같은 조건으로 계산합니다.
# 주의: 부스의 구름은 계단 모양이라 Reactive가 YAX보다 탄소가 적게 나오는 장면이 많습니다 (실제 685일 데이터에서는 반대).
GUI_SHOW_REACTIVE = False
