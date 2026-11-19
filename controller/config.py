"""시연 설정값. 부스에서 바꿀 일이 있는 숫자는 모두 여기에 둡니다."""

# 시간
SLOTS_PER_DAY = 48          # 30분 x 48 = 하루
SECONDS_PER_SLOT = 2.5      # 1시간 = 5초 → 하루 = 2분

# 랙
FANS_PER_RACK = 2           # 팬 하나 = 작업 슬롯 하나
FAN_IDS = {"B": [1, 2], "D2": [3, 4]}   # 아두이노 팬 번호
KWH_PER_SLOT = 0.25         # 작업 하나가 30분 동안 쓰는 전력량 (가정값, Jetson 실측으로 바꿀 것)

# 구름
CLOUD_DELTA = 120           # 구름이 있을 때 탄소 신호에 더하는 값 (gCO2/kWh)

# D2 보정
LAMBDA_G = 10.0             # 변경 비용 람다 (gCO2). 0이면 매번 재계획, 아주 크면 하루 전 고정과 같음
ERROR_EMA_ALPHA = 0.5       # 오차 이동평균 가중치 (클수록 최근 오차에 민감)
ERROR_DECAY = 0.85          # 오차가 한 슬롯 뒤에 남는 비율 (단기 예측). 0이면 바로 사라진다고 봄
MAX_CHANGES_PER_DAY = 20    # 변경 예산
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
