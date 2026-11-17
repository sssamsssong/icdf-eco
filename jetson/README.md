# Jetson (랙 2대)

아직 뼈대만 있습니다. 부스에서는 시간이 남을 때 붙입니다. 그 전까지 메인 PC가 `config.KWH_PER_SLOT` 가정값으로 대신합니다.

할 일:
1. 메인 PC에서 "작업 시작/멈춤" 명령 받기 (같은 스위치에 연결, 소켓 또는 HTTP)
2. 작업 = GPU에서 작은 AI 작업을 반복 실행 (예: 작은 모델 추론 루프)
3. `tegrastats`로 전력을 읽어 메인 PC로 보내기 (`power_reader.py`)

참고: `sudo tegrastats --interval 1000` 출력의 `VDD_IN 4500mW/4500mW` 같은 항목이 보드 전체 전력입니다.
항목 이름은 JetPack 버전마다 다를 수 있으니 실제 출력을 보고 맞추세요.
