"""data/raw의 CSV에서 하루치(48슬롯) 탄소 신호를 읽습니다."""
import csv
from pathlib import Path

from . import config

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def load_day(day: str) -> tuple[list[float], list[float]]:
    """day = 'YYYY-MM-DD' (UTC). (forecast 48개, actual 48개)를 돌려줍니다.

    forecast는 지금은 API의 forecast 값을 씁니다. 이 값은 하루 전 예측보다 정확하므로
    나중에 우리 모델이 만든 하루 전 예측으로 바꿔야 합니다 (docs/참고자료.md 참고).
    """
    prefix = day + "T"
    rows = []
    for f in sorted(RAW_DIR.glob("uk_carbon_*.csv")):
        with open(f, encoding="utf-8") as fp:
            rows += [r for r in csv.DictReader(fp) if r["time_utc"].startswith(prefix)]
    rows = sorted({r["time_utc"]: r for r in rows}.values(), key=lambda r: r["time_utc"])

    if len(rows) != config.SLOTS_PER_DAY:
        raise ValueError(f"{day}: {len(rows)}행만 있습니다. data/fetch_uk_carbon.py로 그 날짜를 받으세요.")

    forecast = [float(r["forecast"]) for r in rows]
    actual = _fill_missing([r["actual"] for r in rows], forecast)
    return forecast, actual


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
