#!/usr/bin/env bash
# 부스 시연을 한 번에 켭니다 (메인 PC, 우분투).
#   ./demo.sh                 기본 날짜로 시연 (아두이노·Jetson은 있으면 자동으로 붙음)
#   ./demo.sh 2025-06-15      날짜 바꾸기
#   ./demo.sh --dry-run       아두이노 없이 화면만
#   ./demo.sh --no-jetson     Jetson 없이
#   ./demo.sh --classic       예전 화면으로 열기
#   ./demo.sh --rehearsal     리허설: 30분 한 칸을 0.5초로 (하루 약 24초)
# 그 밖의 옵션은 그대로 controller.main에 넘어갑니다 (예: --cloud 8-22, --slot-seconds 1).
# 단축어: 터미널에서 icdf  (~/.bash_aliases에 등록)
set -u
cd "$(dirname "$(readlink -f "$0")")"

DAY="2025-03-10"
JETSON_B="10.0.0.11"
JETSON_D2="10.0.0.12"
WIRED_CON="유선 연결 1"      # 메인 PC 유선 연결 이름 (10.0.0.1)
PORT_HTTP=8000

use_arduino=1; use_jetson=1; classic=0; extra=()
for a in "$@"; do
  case "$a" in
    20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]) DAY="$a" ;;
    --dry-run)   use_arduino=0 ;;
    --no-jetson) use_jetson=0 ;;
    --classic)   classic=1 ;;
    --rehearsal) extra+=(--slot-seconds 0.5) ;;
    -h|--help)   sed -n 2,10p "$0"; exit 0 ;;
    *)           extra+=("$a") ;;
  esac
done

ok()   { printf '  \e[32m✓\e[0m %s\n' "$*"; }
warn() { printf '  \e[33m!\e[0m %s\n' "$*"; }

echo "ICDF_eco 시연 준비 ($DAY)"

# 파이썬 (.venv가 있으면 그걸 씀)
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python

# 이미 켜진 시연이 있으면 끔 (포트 충돌 방지)
if pgrep -f "[c]ontroller.main" >/dev/null; then
  warn "이미 켜진 시연 엔진을 끕니다"
  pkill -f "[c]ontroller.main"; sleep 1
fi

# 아두이노
args=(--day "$DAY" --ours --gui --no-browser --http-port "$PORT_HTTP")
if [ $use_arduino = 1 ]; then
  port=$(ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null | head -1)
  if [ -n "$port" ]; then
    if fuser "$port" >/dev/null 2>&1; then
      warn "아두이노 $port 를 다른 프로그램이 쓰고 있습니다 (Arduino IDE 시리얼 모니터를 닫으세요) → 아두이노 없이 진행"
      args+=(--dry-run)
    else
      ok "아두이노 $port"; args+=(--port "$port")
    fi
  else
    warn "아두이노가 안 보입니다 → 화면만 (팬 안 돎)"; args+=(--dry-run)
  fi
else
  args+=(--dry-run); warn "아두이노 안 씀 (--dry-run)"
fi

# Jetson (유선 10.0.0.x)
if [ $use_jetson = 1 ]; then
  if ! ip -4 addr | grep -q "10\.0\.0\.1/"; then
    nmcli con up "$WIRED_CON" >/dev/null 2>&1 && sleep 2
  fi
  if ! ip -4 addr | grep -q "10\.0\.0\.1/"; then
    warn "유선 랜(10.0.0.1)이 없습니다. USB 랜 어댑터를 확인하세요 → Jetson 없이 진행"
  else
    for pair in "B:$JETSON_B" "D2:$JETSON_D2"; do
      name=${pair%%:*}; ip=${pair#*:}
      if curl -s -m 2 "http://$ip:8100/status" >/dev/null; then
        ok "Jetson $name ($ip)"
      else
        warn "Jetson $name ($ip) 응답 없음. 켠 지 1분이 안 됐으면 기다리면 붙습니다 (엔진이 5초마다 다시 시도)"
      fi
    done
    args+=(--jetson-b "http://$JETSON_B:8100" --jetson-d2 "http://$JETSON_D2:8100")
  fi
fi

url="http://127.0.0.1:$PORT_HTTP/"
[ $classic = 1 ] && url="${url}classic"

# 엔진이 뜨면 브라우저를 엶 (F11 = 전체 화면)
(
  for _ in $(seq 1 40); do
    curl -s -o /dev/null "http://127.0.0.1:$PORT_HTTP/state" && break
    sleep 0.25
  done
  [ -z "${NO_BROWSER:-}" ] && xdg-open "$url" >/dev/null 2>&1
) &

echo
echo "화면: $url   (F11 전체 화면 · Enter 시작 · 스페이스 구름 · 끝내려면 이 창에서 Ctrl+C)"
echo
exec "$PY" -u -m controller.main "${args[@]}" "${extra[@]}"
