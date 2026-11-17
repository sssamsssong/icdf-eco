"""data/raw의 CSV에서 하루치(48슬롯) 탄소 신호를 읽습니다."""
import csv
from pathlib import Path

from . import config

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OURS_CSV = Path(__file__).resolve().parent.parent / "data" / "forecast" / "dayahead_ours.csv"


def load_day(day: str, ours: bool = False) -> tuple[list[float], list[float]]:
    """day = 'YYYY-MM-DD' (UTC). (forecast 48개, actual 48개)를 돌려줍니다.

    ours=False: API의 forecast (직전 단기 예측이라 하루 전 예측보다 훨씬 정확함)
    ours=True : sim/train_forecast.py가 만든 우리 하루 전 예측 (2024년 이후 날짜만 있음)
    """
    prefix = day + "T"
    rows = []
    for f in sorted(RAW_DIR.glob("uk_carbon_*.csv")):
        with open(f, encoding="utf-8") as fp:
            rows += [r for r in csv.DictReader(fp) if r["time_utc"].startswith(prefix)]
    rows = sorted({r["time_utc"]: r for r in rows}.values(), key=lambda r: r["time_utc"])

    if len(rows) != config.SLOTS_PER_DAY:
        raise ValueError(f"{day}: {len(rows)}행만 있습니다. data/fetch_uk_carbon.py로 그 날짜를 받으세요.")

    actual_guess = [float(r["actual"]) if r["actual"] not in ("", "None") else 0.0 for r in rows]
    forecast = _fill_missing([r["forecast"] for r in rows], actual_guess)  # API forecast 빈칸 대비
    actual = _fill_missing([r["actual"] for r in rows], forecast)
    if ours:
        forecast = _load_ours(prefix)
    return forecast, actual


def _load_ours(prefix: str) -> list[float]:
    if not OURS_CSV.exists():
        raise ValueError("우리 예측 파일이 없습니다. 먼저 python sim/train_forecast.py 를 실행하세요.")
    with open(OURS_CSV, encoding="utf-8") as fp:
        vals = [float(r["forecast"]) for r in csv.DictReader(fp) if r["time_utc"].startswith(prefix)]
    if len(vals) != config.SLOTS_PER_DAY:
        raise ValueError(f"{prefix[:-1]}의 우리 예측이 없습니다 (2024년 이후, 앞뒤 데이터가 온전한 날만 있음).")
    return vals


def _fill_missing(values: list[str], fallback: list[float]) -> list[float]:
    out = []
    for i, v in enumerate(values):
        if v not in ("", "None", None):
            out.append(float(v))
        elif out:
            out.append(out[-1])
        else:
            out.append(fallback[i])
    return out
