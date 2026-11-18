# Jetson 연결 후 할 일

Jetson Orin Nano Developer Kit 2대를 메인 PC와 스위치로 묶은 뒤 순서대로 진행합니다.
명령과 설정의 자세한 설명은 [jetson/README.md](../jetson/README.md)에 있고, 이 문서는 체크리스트입니다.

Jetson이 없거나 연결이 끊겨도 시연은 그대로 돌아갑니다. 그러니 **아두이노 시연이 먼저 완성된 다음에** 붙이세요.

## 0. 이미 해 둔 것 (2026-11-18)

- [x] Jetson 프로그램 `jetson/agent.py`: 작업 켜기/끄기, 전력 보고, 30초 명령 없으면 자동 정지
- [x] 메인 PC 연결 코드 `controller/jetson.py`: 응답 없으면 가정값으로 계속, 5초마다 다시 연결
- [x] 화면(GUI)에 랙별 실측 전력(W)과 실측 탄소 표시
- [x] 자동 실행 설정 파일 `jetson/icdf-agent.service`
- [x] 메인 PC에서 가짜 Jetson(`--mock`) 2대로 전체 흐름 시험 완료

## 1. 역할과 주소 정하기

| 장치 | 역할 | IP | 확인 |
|---|---|---|---|
| 메인 PC | 시연 엔진, 화면 | 10.0.0.1 | [ ] |
| Jetson #1 | **B 랙** (구글식) | 10.0.0.11 | [ ] |
| Jetson #2 | **D2 랙** (우리 방식) | 10.0.0.12 | [ ] |

- [ ] 두 Jetson에 B, D2 스티커 붙이기 (바뀌면 실측값이 반대 랙에 표시됨)

## 2. 네트워크 연결

- [ ] 스위치에 메인 PC 유선 포트, Jetson 2대를 랜선으로 연결
- [ ] 메인 PC 고정 IP 설정 (10.0.0.1)
- [ ] Jetson 각각 고정 IP 설정 (10.0.0.11, 10.0.0.12)
- [ ] 메인 PC에서 `ping 10.0.0.11`, `ping 10.0.0.12` 응답 확인

설정 명령은 [jetson/README.md의 1. 네트워크](../jetson/README.md#1-네트워크-스위치-하나에-메인-pc--jetson-2대)에 있습니다.
Jetson 화면 없이 작업하려면 `ssh jetson@10.0.0.11`처럼 메인 PC에서 접속하면 편합니다.

## 3. Jetson마다 준비 (두 대 모두)

- [ ] 저장소 받기: `git clone https://github.com/sssamsssong/icdf-eco ~/icdf-eco`
- [ ] 전력 항목 확인: `sudo tegrastats --interval 1000`에 `VDD_IN ...mW`가 보이는지
- [ ] 직접 실행: `cd ~/icdf-eco/jetson && python3 agent.py`
- [ ] 시작 메시지의 **작업 종류** 확인
  - `torch-cuda`: 가장 좋음 (GPU 사용, 작업 켜고 끌 때 전력 차이가 큼)
  - `numpy-cpu`: PyTorch가 없음. 동작은 하지만 GPU를 안 씀 → JetPack 버전에 맞는 Jetson용 PyTorch 설치 고려
- [ ] 시작 메시지의 **대기 전력**이 숫자로 나오는지 (`None`이면 tegrastats 문제)
- [ ] 방화벽이 켜져 있으면 `sudo ufw allow 8100/tcp`

## 4. 메인 PC에서 하나씩 시험

```bash
curl http://10.0.0.11:8100/status
curl -X POST "http://10.0.0.11:8100/jobs?n=2"
sleep 3; curl http://10.0.0.11:8100/power
curl -X POST "http://10.0.0.11:8100/jobs?n=0"
sleep 3; curl http://10.0.0.11:8100/power
```

| 확인 | B (10.0.0.11) | D2 (10.0.0.12) |
|---|---|---|
| `/status` 응답이 옴 | [ ] | [ ] |
| 작업 2개일 때 `avg_mw`가 대기 전력보다 확실히 높음 | [ ] | [ ] |
| 작업 0개로 바꾸면 다시 대기 전력 근처로 내려옴 | [ ] | [ ] |
| 기록: 대기 ___ W / 작업 1개 ___ W / 작업 2개 ___ W | | |

전력 차이가 너무 작으면(1 W 미만) 화면에서 차이가 안 보입니다. 이 경우 `torch-cuda`인지 다시 확인하세요.

## 5. 자동 실행 설정 (두 대 모두)

- [ ] `jetson/icdf-agent.service`의 `User`와 경로가 실제 사용자 이름과 맞는지 확인 (기본 `jetson`)
- [ ] 설치하고 켜기 (명령은 파일 맨 위 주석에 있음)
- [ ] Jetson을 재부팅한 뒤 메인 PC에서 `curl http://10.0.0.11:8100/status`가 바로 응답하는지

## 6. 시연 엔진과 같이 돌리기

```bash
cd ~/icdf-eco && source .venv/bin/activate
python -m controller.main --day 2025-03-10 --ours --gui --port /dev/ttyACM0 \
    --jetson-b http://10.0.0.11:8100 --jetson-d2 http://10.0.0.12:8100
```

- [ ] 터미널에 `Jetson B 연결됨`, `Jetson D2 연결됨`
- [ ] 화면의 랙 카드에 `Jetson 실측 __ W · 실측 탄소 __ g`가 보임
- [ ] 팬이 도는 랙의 Jetson 전력이 올라가고, 팬이 멈추면 내려감
- [ ] 하루가 끝나면 터미널에 `Jetson 실측 탄소` 결과가 출력됨
- [ ] 시연 중 Jetson 랜선을 뽑으면 화면에 "Jetson 연결 안 됨"이 뜨고 **시연은 계속됨**, 다시 꽂으면 몇 초 안에 돌아옴
- [ ] 매번 주소를 적기 싫으면 `controller/config.py`의 `JETSON_HOSTS` 주석 풀기

## 7. 정해야 할 것

- [ ] **실측 탄소 배율 `JETSON_POWER_SCALE`**: Jetson은 몇 W라 실측 탄소가 몇 g 수준입니다. 그대로 보여 줄지(1), 서버 규모로 키울지 정하기
- [ ] **발표에서 실측값을 어떻게 말할지**: 화면의 큰 숫자와 D2의 판단은 가정 전력값, 실측값은 참고로 따로 표시된다는 점

## 알아 둘 점

- Jetson 대기 전력은 `agent.py`가 **시작할 때 3초 동안** 잽니다. 이때 다른 일을 시키면 대기 전력이 높게 잡혀 실측값이 작게 나옵니다. 이상하면 `agent.py`를 다시 시작하세요.
- 메인 PC에서 30초 동안 명령이 없으면 Jetson은 스스로 작업을 멈춥니다. 시연 대기 중에 Jetson이 쉬고 있는 것은 정상입니다.
- 실측 탄소는 시연의 한 칸(2.5초) 동안 잰 평균 전력이 30분 동안 이어졌다고 보고 계산합니다.

## 문제 해결

| 증상 | 원인과 해결 |
|---|---|
| `ping`이 안 됨 | 랜선, 스위치 전원, IP 오타, 두 장치의 대역(10.0.0.x)이 같은지 |
| `ping`은 되는데 `curl`이 안 됨 | `agent.py`가 안 켜짐 (`systemctl status icdf-agent`) 또는 방화벽 |
| 대기 전력 `None`, "VDD_IN 항목 없음" | `tegrastats` 출력 이름이 다름 → `agent.py`의 `POWER_RE` 수정. sudo가 필요하면 서비스를 `User=root`로 |
| 작업 종류가 `numpy-cpu` | PyTorch가 없거나 CUDA를 못 찾음 → `python3 -c "import torch; print(torch.cuda.is_available())"` |
| 화면에 계속 "Jetson 연결 안 됨" | 엔진에 준 주소(`--jetson-b`) 오타, 포트 8100인지 확인 |
| 실측 전력이 0 근처 | 대기 전력이 높게 잡힘 → `agent.py` 재시작 |
