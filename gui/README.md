# GUI (메인 PC)

아직 비어 있습니다.

보여줄 것 (GUI_목업 기준):
- 탄소 곡선: 하루 전 예측과 실제(구름 포함) 값
- 두 랙의 현재 실행 작업 수
- 누적 탄소 B vs D2
- D2 계획 변경 횟수와 변경 이력

가장 빠른 방법: `controller/main.py`가 쓰는 `logs/run_*.csv`를 1초마다 다시 읽어 그리기.
후보: matplotlib 애니메이션, Streamlit, 또는 목업 HTML + 작은 로컬 서버.
