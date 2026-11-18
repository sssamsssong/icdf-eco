# Jetson (랙 2대, Jetson Orin Nano Developer Kit)

랙 하나에 Jetson 하나. 메인 PC가 칸마다 "작업 몇 개 돌려"라고 보내면 Jetson이 GPU 작업을 켜고 끄고,
`tegrastats`로 잰 보드 전력을 메인 PC가 받아 갑니다.
Jetson이 없거나 응답하지 않아도 시연은 그대로 돌아갑니다 (가정 전력값 `config.KWH_PER_SLOT` 사용).

| 파일 | 내용 |
|---|---|
| `agent.py` | Jetson에서 실행. 작업 켜기/끄기 + 전력 보고 (HTTP, 포트 8100). 표준 라이브러리만 사용 |
| `icdf-agent.service` | Jetson이 켜지면 `agent.py` 자동 실행 (systemd) |
| `power_reader.py` | 전력 항목 확인용 (tegrastats 출력을 그대로 보여 줌) |
| `../controller/jetson.py` | 메인 PC 쪽 연결 코드 |

## 1. 네트워크 (스위치 하나에 메인 PC + Jetson 2대)

전시장 와이파이에 기대지 않도록 유선 고정 IP를 씁니다. 메인 PC 와이파이(192.168.1.x)와 겹치지 않는 대역으로.

| 장치 | IP |
|---|---|
| 메인 PC (유선 `enp4s0`) | 10.0.0.1/24 |
| B 랙 Jetson | 10.0.0.11/24 |
| D2 랙 Jetson | 10.0.0.12/24 |

메인 PC (우분투):
```bash
sudo nmcli con add type ethernet ifname enp4s0 con-name icdf ipv4.method manual ipv4.addresses 10.0.0.1/24 ipv6.method ignore
sudo nmcli con up icdf
```

Jetson (각각 11, 12). 유선 인터페이스 이름은 `ip -br link`로 확인 (보통 `eth0` 또는 `enP8p1s0`):
```bash
sudo nmcli con add type ethernet ifname eth0 con-name icdf ipv4.method manual ipv4.addresses 10.0.0.11/24 ipv6.method ignore
sudo nmcli con up icdf
```
게이트웨이를 넣지 않았으니 인터넷은 기존 와이파이로 그대로 나갑니다.

연결 확인 (메인 PC에서): `ping 10.0.0.11`, `ping 10.0.0.12`

## 2. Jetson 준비

```bash
git clone https://github.com/sssamsssong/icdf-eco ~/icdf-eco
cd ~/icdf-eco/jetson
sudo tegrastats --interval 1000     # VDD_IN 항목이 보이는지 확인 후 Ctrl+C
python3 agent.py                    # "준비 완료 … 작업 종류 torch-cuda" 가 나오면 성공
```

- **작업 종류**는 시작할 때 출력됩니다. `torch-cuda`가 가장 좋고 (GPU 사용, 전력 차이가 큼),
  PyTorch가 없으면 `numpy-cpu`로 대신합니다. GPU를 쓰려면 NVIDIA의 Jetson용 PyTorch wheel을 JetPack 버전에 맞게 설치하세요.
- **전력 항목**: Orin Nano는 `VDD_IN 4936mW/4936mW` 형태입니다. 다르게 나오면 `agent.py`의 `POWER_RE`를 고치세요.
  `tegrastats`가 sudo 없이 안 되면 서비스에서 `User=root`로 돌리세요.
- **방화벽**: `sudo ufw status`가 active면 `sudo ufw allow 8100/tcp`
- **자동 실행**: `icdf-agent.service` 안의 설명대로 설치. 기본 사용자/경로는 `jetson`, `/home/jetson/icdf-eco`

메인 PC에서 확인:
```bash
curl http://10.0.0.11:8100/status
curl -X POST "http://10.0.0.11:8100/jobs?n=2"   # 작업 2개 → 전력이 올라가야 함
curl http://10.0.0.11:8100/power
curl -X POST "http://10.0.0.11:8100/jobs?n=0"
```

## 3. 시연과 같이 돌리기

```bash
python -m controller.main --day 2025-03-10 --ours --gui --port /dev/ttyACM0 \
    --jetson-b http://10.0.0.11:8100 --jetson-d2 http://10.0.0.12:8100
```
매번 적기 번거로우면 `controller/config.py`의 `JETSON_HOSTS` 주석을 풀어 두세요.

화면의 랙 카드에 `Jetson 실측 W · 실측 탄소 g`가 나타납니다. 연결이 끊기면 "Jetson 연결 안 됨"으로 바뀌고 5초마다 다시 붙습니다.

## 실측 탄소 계산

- 칸(시연에서 2.5초)마다 그동안 잰 평균 전력에서 **대기 전력을 뺀 값**(작업 때문에 늘어난 전력)을 구합니다.
  대기 전력은 `agent.py`가 시작할 때 3초 동안 잽니다. 이때는 Jetson에 다른 일을 시키지 마세요.
- 그 W가 **30분 동안** 이어졌다고 보고 `W x 0.5h x 탄소 집약도 x JETSON_POWER_SCALE`을 더합니다.
- 화면 큰 숫자(누적 탄소)와 D2의 결정은 **지금처럼 가정 전력값**을 씁니다. 실측 탄소는 그 아래 따로 보여 줍니다.
  Jetson 한 대는 수 W라 실측 탄소가 몇 g 수준입니다. 서버 규모로 보여 주고 싶으면 `JETSON_POWER_SCALE`을 키우세요.
- `logs/run_*.csv`의 `B_meas_co2_g_prev`, `D2_meas_co2_g_prev` 열은 **직전 칸까지** 누적입니다 (전력은 칸이 끝나야 알 수 있으므로).

## 안전장치

- 메인 PC에서 30초 동안 명령이 없으면 Jetson이 작업을 모두 멈춥니다 (`WATCHDOG_S`).
- 메인 PC가 종료할 때 두 Jetson에 작업 0개를 보냅니다.

## Jetson 없이 메인 PC에서 시험

```bash
python jetson/agent.py --mock --host 127.0.0.1 --port 8101 &
python jetson/agent.py --mock --host 127.0.0.1 --port 8102 &
python -m controller.main --day 2024-01-15 --dry-run --slot-seconds 0.3 --cloud 8-22 \
    --jetson-b http://127.0.0.1:8101 --jetson-d2 http://127.0.0.1:8102
```
가짜 전력은 `5 W + 작업 1개당 2.5 W`입니다.
