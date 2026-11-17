"""배속 시연 엔진.

    python -m controller.main --day 2024-01-15 --dry-run
    python -m controller.main --day 2024-01-15 --port COM3

실행 중 키: c = 구름 켜기/끄기, q = 종료
결과는 logs/run_YYYYMMDD_HHMMSS.csv 에 저장됩니다. GUI는 이 CSV(또는 나중에 소켓)를 읽으면 됩니다.
"""
import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

from . import config
from .arduino import Arduino
from .carbon import load_day
from .schedulers import CorrectingScheduler, FixedScheduler, default_jobs

try:
    import msvcrt  # Windows 키 입력
except ImportError:
    msvcrt = None


def read_key() -> str | None:
    if msvcrt and msvcrt.kbhit():
        return msvcrt.getwch().lower()
    return None


def to_led(g: float) -> int:
    return round((g - config.LED_MIN_G) / (config.LED_MAX_G - config.LED_MIN_G) * 100)


def run(day: str, port: str | None, dry_run: bool, cloud_slots: set[int] = frozenset(), ours: bool = False):
    forecast, actual = load_day(day, ours)
    racks = [FixedScheduler(default_jobs(), forecast), CorrectingScheduler(default_jobs(), forecast)]
    arduino = Arduino(port, dry_run)
    co2 = {r.name: 0.0 for r in racks}
    cloud = False

    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"run_{datetime.now():%Y%m%d_%H%M%S}.csv"
    fp = open(log_path, "w", newline="", encoding="utf-8")
    w = csv.writer(fp)
    w.writerow(["slot", "forecast", "actual", "cloud", "observed",
                "B_running", "D2_running", "B_co2_g", "D2_co2_g", "D2_changes"])

    print(f"{day} 시연 시작. c = 구름, q = 종료")
    try:
        for t in range(config.SLOTS_PER_DAY):
            slot_end = time.monotonic() + config.SECONDS_PER_SLOT

            if t in cloud_slots:
                cloud = True
            elif cloud_slots and t - 1 in cloud_slots:
                cloud = False
            observed = actual[t] + (config.CLOUD_DELTA if cloud else 0)
            row = {}
            for rack in racks:
                running = rack.step(t, observed)
                co2[rack.name] += len(running) * config.KWH_PER_SLOT * observed
                for i, fan in enumerate(config.FAN_IDS[rack.name]):
                    arduino.set_fan(fan, i < len(running))
                row[rack.name] = running
            arduino.set_led(to_led(observed))

            d2 = racks[1]
            print(f"{t // 2:02d}:{30 * (t % 2):02d}  탄소 {observed:5.0f}{' 구름' if cloud else '     '}"
                  f"  B {len(row['B'])}개  D2 {len(row['D2'])}개"
                  f"  누적 B {co2['B']:6.0f} g / D2 {co2['D2']:6.0f} g  변경 {d2.changes}")
            w.writerow([t, forecast[t], actual[t], int(cloud), observed,
                        "|".join(row["B"]), "|".join(row["D2"]),
                        round(co2["B"], 1), round(co2["D2"], 1), d2.changes])
            fp.flush()

            # 슬롯 시간이 끝날 때까지 키 입력 확인
            while time.monotonic() < slot_end:
                k = read_key()
                if k == "c":
                    cloud = not cloud
                    print("구름 켜짐" if cloud else "구름 걷힘")
                elif k == "q":
                    raise KeyboardInterrupt
                time.sleep(0.02)
    except KeyboardInterrupt:
        print("중단")
    finally:
        arduino.close()
        fp.close()

    print("\nD2 변경 이력:")
    for line in racks[1].log:
        print(" ", line)
    for rack in racks:
        unfinished = [j.id for j in rack.jobs.values() if j.done < j.need]
        print(f"{rack.name}: 누적 {co2[rack.name]:.0f} g, 변경 {rack.changes}회, 마감 못 맞춘 작업 {unfinished or '없음'}")
    print("기록:", log_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True, help="YYYY-MM-DD (data/raw에 있는 날짜)")
    ap.add_argument("--port", help="아두이노 포트, 예: COM3")
    ap.add_argument("--dry-run", action="store_true", help="아두이노 없이 실행")
    ap.add_argument("--cloud", help="구름 슬롯 범위 미리 지정, 예: 20-30 (리허설/테스트용)")
    ap.add_argument("--ours", action="store_true", help="API forecast 대신 우리 하루 전 예측 사용")
    ap.add_argument("--fast", action="store_true", help="슬롯 대기 없이 바로 끝까지 (테스트용)")
    args = ap.parse_args()
    if args.fast:
        config.SECONDS_PER_SLOT = 0
    cloud_slots = set()
    if args.cloud:
        a, b = map(int, args.cloud.split("-"))
        cloud_slots = set(range(a, b + 1))
    run(args.day, args.port, args.dry_run, cloud_slots, args.ours)


if __name__ == "__main__":
    main()
