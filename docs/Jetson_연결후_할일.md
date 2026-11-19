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

## 1. 역할과 주소 (2026-11-19 완료)

| 장치 | 역할 | 사용자 | IP | 유선 연결 이름 | 확인 |
|---|---|---|---|---|---|
| 메인 PC (hj-gram) | 시연 엔진, 화면 | `hj` | 10.0.0.1 | `유선 연결 1` (USB 랜 어댑터 `enx00e04c3639d4`) | [x] |
| Jetson #1 | **B 랙** (구글식) | `jetson` | 10.0.0.11 (+ 기존 라이다용 192.168.0.5) | `lidar-link` (`enP8p1s0`) | [x] |
| Jetson #2 | **D2 랙** (우리 방식) | `yax-module1` | 10.0.0.12 | `Profile 1` (`eno1`) | [x] |

- 두 Jetson 모두 호스트 이름이 `ubuntu`라서 이름으로는 구분이 안 됩니다. **사용자 이름**으로 구분하세요.
- [ ] 두 Jetson에 B, D2 스티커 붙이기 (바뀌면 실측값이 반대 랙에 표시됨)

## 2. 네트워크 연결 (완료)

- [x] 스위치에 메인 PC 유선 포트, Jetson 2대를 랜선으로 연결
- [x] 메인 PC 고정 IP 10.0.0.1 (게이트웨이 없음 → 인터넷은 와이파이로 그대로)
- [x] Jetson #1: 기존 `lidar-link`(192.168.0.5)에 주소를 **추가** (`+ipv4.addresses`), 라이다 설정은 그대로
- [x] Jetson #2: DHCP(`auto`)였던 `eno1` 연결을 고정 주소로 바꿈
- [x] 메인 PC에서 `ping 10.0.0.11`, `ping 10.0.0.12` 응답 확인
- [x] 메인 PC SSH 키를 두 Jetson에 등록 (`ssh-copy-id`) → `ssh jetson@10.0.0.11`, `ssh yax-module1@10.0.0.12`가 비밀번호 없이 됨

이렇게 했습니다 (다시 할 때 참고):
```bash
# 메인 PC
nmcli con mod "유선 연결 1" ipv4.method manual ipv4.addresses 10.0.0.1/24 ipv4.gateway "" ipv4.never-default yes
nmcli con up "유선 연결 1"
# Jetson #1 (기존 주소 유지, 하나 더 붙임)
sudo nmcli con mod lidar-link +ipv4.addresses 10.0.0.11/24 && sudo nmcli con up lidar-link
# Jetson #2 (이름이 같은 'Profile 1'이 두 개라 UUID로 지정)
sudo nmcli con mod ce06c6ca-d051-41f6-ab3a-13aaf704e5a6 ipv4.method manual ipv4.addresses 10.0.0.12/24
sudo nmcli con up ce06c6ca-d051-41f6-ab3a-13aaf704e5a6
```

**IPv4 주소가 없을 때 Jetson 찾기**: IPv6 링크 로컬 주소는 설정 없이도 생깁니다.
```bash
ping -6 -c 2 ff02::1%enx00e04c3639d4      # 응답한 fe80::... 중 메인 PC 자신(...b867)이 아닌 것
ip -6 neigh show dev enx00e04c3639d4      # MAC 3c:6d:66:... 이 NVIDIA (#1 ...:b5:07:5e, #2 ...:bf:43:b8)
ssh <사용자>@fe80::...%enx00e04c3639d4
```
링크 로컬 주소는 연결이 다시 올라올 때 **바뀔 수 있습니다** (#2에서 실제로 바뀜). 안 되면 위 명령으로 다시 찾으세요.

## 3. Jetson마다 준비 (두 대 모두 완료)

두 Jetson 모두 인터넷이 안 돼서 `git clone` 대신 메인 PC에서 파일 3개를 보냈습니다.
```bash
ssh jetson@10.0.0.11 'mkdir -p ~/icdf-eco/jetson'
scp jetson/agent.py jetson/power_reader.py jetson/icdf-agent.service jetson@10.0.0.11:~/icdf-eco/jetson/
# #2는 jetson@10.0.0.11 대신 yax-module1@10.0.0.12
```
코드를 고치면 같은 명령으로 다시 보내고 Jetson에서 `sudo systemctl restart icdf-agent`.

- [x] 전력 항목: 두 대 모두 `tegrastats`로 sudo 없이 읽힘
- [x] 직접 실행해서 "준비 완료" 확인
- [x] 작업 종류: **두 대 모두 `numpy-cpu`** (PyTorch 없음. 인터넷이 없어 설치 못 함)
- [x] 대기 전력이 숫자로 나옴
- [x] 방화벽: 막히지 않음 (8100 포트 바로 응답)

| | #1 B (10.0.0.11) | #2 D2 (10.0.0.12) |
|---|---|---|
| 보드 / 전력 모드 | Orin Nano Super / 25W | Orin Nano Super / 25W |
| JetPack (L4T) | R36.5.2 | R36.4.4 |
| numpy | 1.26.4 (pip, OpenBLAS) | 1.21.5 (apt) |
| 시계 | 재부팅하면 11-15로 돌아감 (RTC 배터리 없음) | 11-17 근처, 시간대 EST |

## 4. 메인 PC에서 하나씩 시험 (완료)

| 확인 | B (10.0.0.11) | D2 (10.0.0.12) |
|---|---|---|
| `/status` 응답이 옴 | [x] | [x] |
| 작업 2개일 때 `avg_mw`가 대기 전력보다 높음 | [x] | [x] |
| 작업 0개로 바꾸면 다시 대기 전력 근처로 내려옴 | [x] | [x] |
| 기록: 대기 / 작업 2개 | 4.4 W / 5.2 W (**+0.7 W**) | 5.6 W / 8.4 W (**+2.8 W**) |

**같은 작업인데 늘어난 전력이 네 배 다릅니다.** 하드웨어와 전력 모드는 같고, numpy(BLAS) 버전이 달라 CPU를 다르게 쓰는 것으로 보입니다. 7번을 보세요.

## 5. 자동 실행 설정 (두 대 모두 완료)

- [x] #1: `jetson/icdf-agent.service`를 그대로 설치 (사용자 `jetson`)
- [x] #2: 사용자 이름이 달라서 바꿔서 설치
  ```bash
  sed 's#User=jetson#User=yax-module1#; s#/home/jetson/#/home/yax-module1/#' ~/icdf-eco/jetson/icdf-agent.service \
      | sudo tee /etc/systemd/system/icdf-agent.service >/dev/null
  sudo systemctl daemon-reload && sudo systemctl enable --now icdf-agent
  ```
- [x] #1 재부팅 후 `curl http://10.0.0.11:8100/status`가 저절로 응답
- [x] 부팅 직후 대기 전력이 높게 잡히던 문제(6.5 W) → 서비스가 **60초 기다렸다가** 시작하도록 고침. 그래서 재부팅·재시작 뒤 1분은 응답이 없는 게 정상

## 6. 시연 엔진과 같이 돌리기

```bash
cd ~/icdf-eco && source .venv/bin/activate
python -m controller.main --day 2025-03-10 --ours --gui --port /dev/ttyACM0 \
    --jetson-b http://10.0.0.11:8100 --jetson-d2 http://10.0.0.12:8100
```

2026-11-19 시험 (`--dry-run --cloud 8-22 --slot-seconds 1`, 아두이노 없이):
- [x] 터미널에 `Jetson B 연결됨`, `Jetson D2 연결됨`
- [x] 하루가 끝나면 `Jetson 실측 탄소` 출력: **B 1.01 g, D2 3.89 g** (가정 전력 기준 누적은 B 1521 g, D2 1434 g)
- [x] 화면의 랙 카드에 `Jetson 실측 __ W (대기 __ W)`가 보임 (`--gui`로 확인. 실측 탄소는 7번 결정대로 숨김)
- [ ] 팬이 도는 랙의 Jetson 전력이 올라가고, 팬이 멈추면 내려감 (아두이노와 같이)
- [ ] 시연 중 Jetson 랜선을 뽑으면 "Jetson 연결 안 됨"이 뜨고 **시연은 계속됨**, 다시 꽂으면 몇 초 안에 돌아옴
- [ ] 매번 주소를 적기 싫으면 `controller/config.py`의 `JETSON_HOSTS` 주석 풀기

## 7. 정해야 할 것

- [x] **랙별 실측 탄소를 화면에 보여 줄지** → **숨기기로 함** (`controller/config.py`의 `GUI_SHOW_MEASURED_CO2 = False`, 화면에는 실측 W만). 위 시험에서 D2 실측(3.89 g)이 B(1.01 g)의 네 배로 나옵니다. 스케줄러 때문이 아니라 #2 보드가 같은 작업에 전력을 더 쓰기 때문입니다. 그대로 보여 주면 "우리 방식이 더 나쁘다"로 읽힙니다.
  - 추천: 탄소 비교는 가정 전력값으로 하고, 실측은 "실제로 돌고 있다"는 증거로 W만 보여 주기
  - 근본 해결: 두 Jetson의 numpy 버전 맞추기, 또는 Jetson용 PyTorch(GPU 작업) 설치. 둘 다 인터넷이나 휠 파일이 필요
- [ ] **실측 탄소 배율 `JETSON_POWER_SCALE`**: Jetson은 몇 W라 실측 탄소가 몇 g 수준입니다. 그대로 보여 줄지(1), 서버 규모로 키울지 정하기
- [ ] **발표에서 실측값을 어떻게 말할지**: 화면의 큰 숫자와 D2의 판단은 가정 전력값, 실측값은 참고로 따로 표시된다는 점

## 알아 둘 점

- Jetson 대기 전력은 `agent.py`가 **시작할 때 3초 동안** 잽니다. 이때 다른 일을 시키면 대기 전력이 높게 잡혀 실측값이 작게 나옵니다. 서비스는 부팅 뒤 60초 기다렸다가 켜집니다. 그래도 이상하면 `sudo systemctl restart icdf-agent`.
- 메인 PC에서 30초 동안 명령이 없으면 Jetson은 스스로 작업을 멈춥니다. 시연 대기 중에 Jetson이 쉬고 있는 것은 정상입니다.
- 실측 탄소는 시연의 한 칸(2.5초) 동안 잰 평균 전력이 30분 동안 이어졌다고 보고 계산합니다.

## 문제 해결

| 증상 | 원인과 해결 |
|---|---|
| `ping`이 안 됨 | 랜선, 스위치 전원, IP 오타, 두 장치의 대역(10.0.0.x)이 같은지 |
| 메인 PC에 `enx...` 장치가 아예 없음 (`ip -br addr`) | USB 랜 어댑터가 빠짐. 이 어댑터는 접촉 불량이 있어 **노트북에 직접, 끝까지** 꽂고 테이프로 고정 |
| Jetson이 몇 분 보였다가 사라지고 안 돌아옴 | 그 Jetson 유선 연결이 DHCP(`auto`)라 주소를 못 받고 포기한 것. 랜선을 뺐다 꽂고, 보이는 동안 고정 주소로 바꾸기 (2번 참고) |
| `ssh` 링크 로컬 주소(`fe80::`)가 갑자기 안 됨 | 주소가 바뀜. `ping -6 ff02::1%enx00e04c3639d4`로 다시 찾기 |
| `ping`은 되는데 `curl`이 안 됨 | `agent.py`가 안 켜짐 (`systemctl status icdf-agent`) 또는 방화벽 |
| 대기 전력 `None`, "VDD_IN 항목 없음" | `tegrastats` 출력 이름이 다름 → `agent.py`의 `POWER_RE` 수정. sudo가 필요하면 서비스를 `User=root`로 |
| 작업 종류가 `numpy-cpu` | PyTorch가 없거나 CUDA를 못 찾음 → `python3 -c "import torch; print(torch.cuda.is_available())"` |
| 화면에 계속 "Jetson 연결 안 됨" | 엔진에 준 주소(`--jetson-b`) 오타, 포트 8100인지 확인 |
| 실측 전력이 0 근처 | 대기 전력이 높게 잡힘 → `agent.py` 재시작 |
