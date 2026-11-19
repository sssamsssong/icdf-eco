"""배속 시연 엔진.

    python -m controller.main --day 2025-03-10 --ours --gui --port COM3   # 부스용
    python -m controller.main --day 2025-03-10 --ours --gui --dry-run     # 아두이노 없이 화면만
    python -m controller.main --day 2025-03-10 --ours --dry-run --fast --cloud 8-22   # 결과만 빠르게

--gui: 브라우저에 화면을 띄우고, 화면의 [시작]으로 하루를 재생합니다. 끝나면 [다시 시작]으로 반복.
키보드 (터미널 창): s = 시작, c = 구름 켜기/끄기, q = 종료
키보드 (브라우저 화면): Enter = 시작, 스페이스 = 구름
기록은 logs/run_YYYYMMDD_HHMMSS.csv 에 남습니다.
"""
import argparse
import csv
import time
import webbrowser
from datetime import datetime
from pathlib import Path

from . import config
from .arduino import Arduino
from .carbon import load_day
from .jetson import Jetsons
from .schedulers import CorrectingScheduler, FixedScheduler, default_jobs
from .server import Shared, start_server

try:
    import msvcrt  # Windows 키 입력
except ImportError:
    msvcrt = None


class Quit(Exception):
    pass


def load_longterm() -> list[dict]:
    """장기 시뮬레이션 요약 (sim/run_longterm.py 결과). 없으면 빈 목록."""
    path = Path(__file__).resolve().parent.parent / "sim" / "results" / "summary_test_default.csv"
    try:
        with open(path, encoding="utf-8-sig") as f:
            return [{"name": r["전략"], "kg": float(r["탄소 kg"]), "changes": float(r["하루 평균 변경"]),
                     "recovery": float(r["회복률 %"])} for r in csv.DictReader(f)]
    except (OSError, KeyError, ValueError):
        return []


LONGTERM = load_longterm()


def cost_proof(cost_g: float) -> dict | None:
    """변경 1회 비용이 cost_g일 때의 장기 시뮬레이션 결과 (sim/results의 람다별 표에서 계산).

    전략마다 검증 기간(2024)에서 순이득이 가장 큰 람다를 고르고, 테스트 기간(2025~)의 값을 돌려줍니다.
    순이득 kg = B(하루 전 고정) 대비 줄인 탄소 - 변경 횟수 x cost_g.
    """
    res = Path(__file__).resolve().parent.parent / "sim" / "results"
    days = {"val": 366, "test": 685}   # sim/README.md의 기간 (2024 / 2025-01-01 ~ 2026-11-16)
    try:
        gap, sweep = {}, {}
        for per in days:
            with open(res / f"summary_{per}_default.csv", encoding="utf-8-sig") as f:
                kg = {r["전략"].split()[0]: float(r["탄소 kg"]) for r in csv.DictReader(f)}
            gap[per] = kg["B"] - kg["P"]
            with open(res / f"lambda_sweep_{per}_default.csv", encoding="utf-8-sig") as f:
                sweep[per] = {(r["전략"], float(r["람다 g"])): (float(r["하루 평균 변경"]), float(r["회복률 %"]))
                              for r in csv.DictReader(f)}
    except (OSError, KeyError, ValueError):
        return None

    def net(per, key):
        ch, rec = sweep[per][key]
        return rec / 100 * gap[per] - ch * days[per] * cost_g / 1000

    out = {"cost": cost_g, "days": days["test"]}
    for name in ("D1", "D2"):
        lams = sorted(l for (n, l) in sweep["val"] if n == name and (n, l) in sweep["test"])
        if not lams:
            return None
        best = max(lams, key=lambda l: net("val", (name, l)))
        out[name] = {"lam": best, "changes": sweep["test"][(name, best)][0], "net_kg": round(net("test", (name, best)), 2)}
    return out


PROOF = cost_proof(config.CHANGE_COST_G)


def read_key() -> str | None:
    if msvcrt and msvcrt.kbhit():
        return msvcrt.getwch().lower()
    return None


def to_led(g: float) -> int:
    return round((g - config.LED_MIN_G) / (config.LED_MAX_G - config.LED_MIN_G) * 100)


def handle_keys(shared: Shared):
    k = read_key()
    if k == "c":
        print("구름 켜짐" if shared.toggle_cloud() else "구름 걷힘")
    elif k == "s":
        shared.start_event.set()
    elif k == "q":
        raise Quit


def make_racks(forecast) -> list:
    """같은 작업, 같은 예측으로 시작하는 스케줄러들. [0] = B(Google), [1] = D2(YAX), [2] = D1(Reactive, 화면 전용)."""
    racks = [FixedScheduler(default_jobs(), forecast), CorrectingScheduler(default_jobs(), forecast)]
    if config.GUI_SHOW_REACTIVE:
        r = CorrectingScheduler(default_jobs(), forecast, error_model="delta")
        r.name = "D1"
        racks.append(r)
    return racks


class CloudSensor:
    """조도센서 값을 구름 크기(탄소 신호에 더할 값)로 바꿉니다."""

    def __init__(self, arduino: Arduino, shared: Shared):
        self.arduino, self.shared = arduino, shared
        self.base: float | None = None

    def calibrate(self):
        """지금 밝기를 기준(구름 없음)으로 잡습니다. 하루를 시작할 때마다 부릅니다."""
        self.base = None
        if not config.CLOUD_SENSOR or self.arduino.dry_run:
            return
        self.arduino.take_lux()
        time.sleep(0.7)                     # 새 값 서너 개를 모음
        lux = self.arduino.take_lux()
        if lux is None:
            print("조도센서: 값이 없습니다 → 버튼 구름만 사용")
        elif lux < config.CLOUD_SENSOR_MIN_LUX:
            print(f"조도센서: 기준 밝기가 너무 어둡습니다 ({lux:.0f} lux) → 버튼 구름만 사용")
        else:
            self.base = lux
            print(f"조도센서: 기준 밝기 {lux:.0f} lux (지금 가려져 있으면 안 됩니다)")

    def ratio(self, lux: float | None) -> float:
        if self.base is None or lux is None:
            return 0.0
        r = max(0.0, min(1.0, (self.base - lux) / self.base))
        return r if r >= config.CLOUD_SENSOR_DEADBAND else 0.0

    def delta(self) -> float:
        """지난 칸 동안의 평균 조도로 계산한 구름 크기."""
        return config.CLOUD_SENSOR_MAX_DELTA * self.ratio(self.arduino.take_lux())

    def publish(self):
        """화면에 보여 줄 실시간 값."""
        if self.arduino.dry_run or not config.CLOUD_SENSOR:
            self.shared.sensor = None
            return
        lux = self.arduino.lux if self.arduino.sensor_ok() else None
        r = self.ratio(lux)
        self.shared.sensor = {"lux": None if lux is None else round(lux, 1),
                              "base": None if self.base is None else round(self.base, 1),
                              "pct": round(r * 100), "delta": round(config.CLOUD_SENSOR_MAX_DELTA * r)}


def snapshot(status, day, t, forecast, observed, cloud_hist, racks, co2, hardware,
             jetsons=None, measured=None) -> dict:
    d2 = racks[1]
    jet = None
    if jetsons is not None and jetsons.enabled:
        jet = jetsons.summary()
        for rack, info in jet.items():
            info["co2"] = round((measured or {}).get(rack, 0.0), 2)
        jet = {"racks": jet, "scale": config.JETSON_POWER_SCALE, "show_co2": config.GUI_SHOW_MEASURED_CO2}
    return {
        "status": status,
        "day": day,
        "slot": t,
        "slots": config.SLOTS_PER_DAY,
        "seconds_per_slot": config.SECONDS_PER_SLOT,
        "forecast": forecast,
        "observed": observed,
        "cloud_hist": cloud_hist,
        "racks": {
            r.name: {
                "co2": round(co2[r.name], 1),
                "changes": r.changes,
                "running": len(r.plan[t]) if 0 <= t < config.SLOTS_PER_DAY else 0,
                "plan": [len(p) for p in r.plan],
                "moved_now": sum(1 for e in getattr(r, "events", []) if e["t"] == t),
            } for r in racks
        },
        "events": d2.events,
        "decisions": d2.decisions,
        "trace": d2.trace,
        "lam": d2.lam,
        "max_changes": d2.max_changes,
        "error_model": d2.error_model,
        "facts": config.MODEL_FACTS,
        "longterm": LONGTERM,
        "change_cost": config.CHANGE_COST_G,
        "proof": PROOF,
        "kwh": config.KWH_PER_SLOT,
        "jobs": len(d2.jobs),
        "cloud_delta": max(config.CLOUD_DELTA, config.CLOUD_SENSOR_MAX_DELTA if config.CLOUD_SENSOR else 0),
        "hardware": hardware,
        "jetson": jet,
    }


def run_day(day, forecast, actual, arduino, shared, cloud_slots, hardware, log_dir, jetsons, sensor):
    racks = make_racks(forecast)
    co2 = {r.name: 0.0 for r in racks}
    measured = {r.name: 0.0 for r in racks}   # Jetson 실측 전력으로 계산한 탄소 (연결된 랙만)

    def account(slot):
        """지난 칸 동안 Jetson이 잰 평균 전력으로 실측 탄소를 더합니다."""
        for rack, w in jetsons.read_power().items():
            if w is not None:
                measured[rack] += w * 0.5 / 1000 * observed[slot] * config.JETSON_POWER_SCALE
    observed, cloud_hist = [], []

    log_path = log_dir / f"run_{datetime.now():%Y%m%d_%H%M%S}.csv"
    fp = open(log_path, "w", newline="", encoding="utf-8")
    w = csv.writer(fp)
    w.writerow(["slot", "forecast", "actual", "cloud", "observed",
                "B_running", "D2_running", "B_co2_g", "D2_co2_g", "D2_changes",
                "B_meas_co2_g_prev", "D2_meas_co2_g_prev",   # Jetson 실측: 직전 칸까지 누적
                "cloud_delta"])                               # 구름으로 더한 값 (버튼 또는 조도센서)

    sensor.calibrate()
    print(f"\n{day} 재생 시작")
    try:
        for t in range(config.SLOTS_PER_DAY):
            slot_end = time.monotonic() + config.SECONDS_PER_SLOT

            if cloud_slots:
                shared.cloud = t in cloud_slots
            # 구름 크기: 버튼(고정값)과 조도센서(가린 만큼) 중 큰 쪽
            cloud_delta = max(config.CLOUD_DELTA if shared.cloud else 0, sensor.delta())
            cloud = cloud_delta > 0
            obs = actual[t] + cloud_delta
            observed.append(obs)
            cloud_hist.append(cloud)

            row = {}
            for rack in racks:
                running = rack.step(t, obs)
                co2[rack.name] += len(running) * config.KWH_PER_SLOT * obs
                for i, fan in enumerate(config.FAN_IDS.get(rack.name, [])):   # Reactive(D1)는 팬 없음
                    arduino.set_fan(fan, i < len(running))
                row[rack.name] = running
            arduino.set_led(to_led(obs))
            if jetsons.enabled:
                if t > 0:
                    account(t - 1)
                jetsons.set_jobs({name: len(r) for name, r in row.items()})

            shared.set_state(snapshot("running", day, t, forecast, observed, cloud_hist, racks, co2, hardware,
                                      jetsons, measured))
            print(f"{t // 2:02d}:{30 * (t % 2):02d}  탄소 {obs:5.0f}{f' 구름+{cloud_delta:3.0f}' if cloud else '         '}"
                  f"  B {len(row['B'])}개  D2 {len(row['D2'])}개"
                  f"  누적 B {co2['B']:6.0f} g / D2 {co2['D2']:6.0f} g  변경 {racks[1].changes}")
            w.writerow([t, forecast[t], actual[t], int(cloud), obs, "|".join(row["B"]), "|".join(row["D2"]),
                        round(co2["B"], 1), round(co2["D2"], 1), racks[1].changes,
                        round(measured["B"], 3), round(measured["D2"], 3), round(cloud_delta, 1)])
            fp.flush()

            while time.monotonic() < slot_end:
                handle_keys(shared)
                sensor.publish()
                time.sleep(0.02)
        if jetsons.enabled:
            account(config.SLOTS_PER_DAY - 1)
    finally:
        arduino.all_off()
        jetsons.stop_all()
        fp.close()

    shared.cloud = False
    shared.set_state(snapshot("done", day, config.SLOTS_PER_DAY - 1, forecast, observed, cloud_hist,
                              racks, co2, hardware, jetsons, measured))
    print("\nD2 변경 이력:")
    for line in racks[1].log:
        print(" ", line)
    for rack in racks:
        unfinished = [j.id for j in rack.jobs.values() if j.done < j.need]
        print(f"{rack.name}: 누적 {co2[rack.name]:.0f} g, 변경 {rack.changes}회, 마감 못 맞춘 작업 {unfinished or '없음'}")
    if jetsons.enabled:
        print("Jetson 실측 탄소 (배율 {}):".format(config.JETSON_POWER_SCALE),
              ", ".join(f"{k} {v:.2f} g" for k, v in measured.items() if k in jetsons.links))
    print("기록:", log_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True, help="YYYY-MM-DD (data/raw에 있는 날짜)")
    ap.add_argument("--port", help="아두이노 포트, 예: COM3")
    ap.add_argument("--dry-run", action="store_true", help="아두이노 없이 실행")
    ap.add_argument("--cloud", help="구름 슬롯 범위 미리 지정, 예: 20-30 (리허설/테스트용)")
    ap.add_argument("--ours", action="store_true", help="API forecast 대신 우리 하루 전 예측 사용")
    ap.add_argument("--fast", action="store_true", help="슬롯 대기 없이 바로 끝까지 (테스트용)")
    ap.add_argument("--gui", action="store_true", help="브라우저 화면 띄우기 (시작 버튼으로 반복 재생)")
    ap.add_argument("--slot-seconds", type=float, help=f"30분 한 칸을 몇 초로 (기본 {config.SECONDS_PER_SLOT})")
    ap.add_argument("--no-browser", action="store_true", help="브라우저 자동으로 열지 않기")
    ap.add_argument("--http-port", type=int, default=8000, help="GUI 주소 포트 (기본 8000)")
    ap.add_argument("--jetson-b", help="B 랙 Jetson 주소, 예: http://10.0.0.11:8100 (config.JETSON_HOSTS 대신)")
    ap.add_argument("--jetson-d2", help="D2 랙 Jetson 주소, 예: http://10.0.0.12:8100")
    args = ap.parse_args()
    if args.slot_seconds is not None:
        config.SECONDS_PER_SLOT = args.slot_seconds
    if args.fast:
        config.SECONDS_PER_SLOT = 0
    cloud_slots = set()
    if args.cloud:
        a, b = map(int, args.cloud.split("-"))
        cloud_slots = set(range(a, b + 1))

    forecast, actual = load_day(args.day, args.ours)
    arduino = Arduino(args.port, args.dry_run)
    hardware = "아두이노 연결 안 함" if arduino.dry_run else f"아두이노 {args.port}"
    hosts = dict(config.JETSON_HOSTS)
    if args.jetson_b:
        hosts["B"] = args.jetson_b
    if args.jetson_d2:
        hosts["D2"] = args.jetson_d2
    jetsons = Jetsons(hosts)
    if jetsons.enabled:
        hardware += " · Jetson " + ", ".join(f"{k} {'연결됨' if l.online else '연결 안 됨'}" for k, l in jetsons.links.items())
    shared = Shared()
    sensor = CloudSensor(arduino, shared)
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    try:
        if not args.gui:
            print("c = 구름, q = 종료")
            run_day(args.day, forecast, actual, arduino, shared, cloud_slots, hardware, log_dir, jetsons, sensor)
            return

        start_server(shared, args.http_port)
        url = f"http://127.0.0.1:{args.http_port}/"
        empty = make_racks(forecast)
        shared.set_state(snapshot("ready", args.day, -1, forecast, [], [], empty,
                                  {r.name: 0.0 for r in empty}, hardware, jetsons))
        print(f"화면: {url}  (화면의 [시작] 또는 s = 시작, c = 구름, q = 종료)")
        if not args.no_browser:
            webbrowser.open(url)
        while True:
            shared.start_event.clear()
            while not shared.start_event.is_set():
                handle_keys(shared)
                sensor.publish()
                time.sleep(0.05)
            run_day(args.day, forecast, actual, arduino, shared, cloud_slots, hardware, log_dir, jetsons, sensor)
    except (KeyboardInterrupt, Quit):
        print("종료")
    finally:
        jetsons.stop_all()
        arduino.close()


if __name__ == "__main__":
    main()
