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

# LED 표시 범위 (gCO2/kWh → 0~100)
LED_MIN_G = 50
LED_MAX_G = 350

# 시리얼
BAUD = 115200
