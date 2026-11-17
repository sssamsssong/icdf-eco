"""영국 Carbon Intensity API에서 30분 단위 탄소 집약도를 내려받아 CSV로 저장합니다.

사용 예:
    python data/fetch_uk_carbon.py --start 2024-01-01 --end 2024-03-01

API는 한 번에 31일까지만 조회되므로 30일씩 나눠 받습니다.
결과: data/raw/uk_carbon_YYYYMMDD_YYYYMMDD.csv  (열: time_utc, forecast, actual)
"""
import argparse
import csv
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

API = "https://api.carbonintensity.org.uk/intensity/{start}/{end}"
CHUNK_DAYS = 30


def fetch(start: datetime, end: datetime) -> list[dict]:
    rows = {}
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=CHUNK_DAYS), end)
        url = API.format(start=cur.strftime("%Y-%m-%dT%H:%MZ"), end=nxt.strftime("%Y-%m-%dT%H:%MZ"))
        print("받는 중:", cur.date(), "~", nxt.date())
        r = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
        r.raise_for_status()
        for d in r.json()["data"]:
            t = d["from"]
            if start.strftime("%Y-%m-%dT%H:%MZ") <= t < end.strftime("%Y-%m-%dT%H:%MZ"):
                rows[t] = {"time_utc": t,
                           "forecast": d["intensity"]["forecast"],
                           "actual": d["intensity"]["actual"]}
        cur = nxt
        time.sleep(0.5)  # 서버에 부담 주지 않게
    return [rows[k] for k in sorted(rows)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD (UTC, 이 날은 포함 안 함)")
    args = ap.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")
    rows = fetch(start, end)

    out_dir = Path(__file__).parent / "raw"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"uk_carbon_{start:%Y%m%d}_{end:%Y%m%d}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["time_utc", "forecast", "actual"])
        w.writeheader()
        w.writerows(rows)

    missing = sum(1 for r in rows if r["actual"] is None)
    print(f"저장: {out}  ({len(rows)}행, actual 빈 값 {missing}개)")


if __name__ == "__main__":
    main()
