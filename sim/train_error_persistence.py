"""당일 오차 지속 모델 학습 (D2의 ④ 단기 예측).

    python sim/train_error_persistence.py

질문: 지금까지 본 하루 전 예측 오차 e(t), e(t-1), ... 로 h칸 뒤 오차 e(t+h)를 맞출 수 있는가?
- 오차 e = 실제 - 우리 하루 전 예측 (sim/train_forecast.py 결과)
- 학습: 2024 (검증 기간의 예측 오차) · 평가: 2025~
- 모델: h마다 선형 회귀 하나 (입력 = 최근 오차 LAGS칸 + 상수). 계수가 작아서 JSON으로 저장
  → controller/error_model.json  (D2가 config.ERROR_MODEL = "learned" 일 때 사용)

비교 대상 (MAE가 낮을수록 좋음)
- 0으로 보기      : 오차는 바로 사라진다 = 하루 전 계획 그대로 (B의 관점)
- 지금 오차 유지  : 지금 오차가 계속 간다 = D1
- 규칙 (EMA x DECAY^h) : 지금 D2가 쓰는 고정 규칙
- 학습 모델       : 이 스크립트가 만드는 것
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parent.parent
sys_path = str(ROOT)
import sys  # noqa: E402
sys.path.insert(0, sys_path)
from controller import config  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
OURS = ROOT / "data" / "forecast" / "dayahead_ours.csv"
OUT = ROOT / "controller" / "error_model.json"

LAGS = 8           # 최근 몇 칸의 오차를 볼지 (8칸 = 4시간)
H_MAX = 47         # 최대 몇 칸 앞까지 (47칸 ≈ 하루)
TRAIN_END = "2024-12-31"


def load_errors() -> pd.Series:
    raw = pd.concat([pd.read_csv(f) for f in sorted(RAW_DIR.glob("uk_carbon_*.csv"))]).drop_duplicates("time_utc")
    raw["time_utc"] = pd.to_datetime(raw["time_utc"], format="%Y-%m-%dT%H:%MZ")
    actual = raw.set_index("time_utc")["actual"].sort_index()
    ours = pd.read_csv(OURS)
    ours["time_utc"] = pd.to_datetime(ours["time_utc"], format="%Y-%m-%dT%H:%MZ")
    fc = ours.set_index("time_utc")["forecast"]
    grid = pd.date_range(fc.index.min(), fc.index.max(), freq="30min")
    return (actual.reindex(grid) - fc.reindex(grid))   # 예측이 없는 날은 NaN


def make_xy(e: np.ndarray, h: int):
    """입력 [e(t), e(t-1), ..., e(t-LAGS+1)], 목표 e(t+h). NaN이 섞인 표본은 버림."""
    n = len(e)
    idx = np.arange(LAGS - 1, n - h)
    X = np.stack([e[idx - k] for k in range(LAGS)], axis=1)
    y = e[idx + h]
    ok = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
    return X[ok], y[ok], idx[ok]


def ema_series(e: np.ndarray, alpha: float) -> np.ndarray:
    out = np.full_like(e, np.nan)
    m = 0.0
    for i, v in enumerate(e):
        if np.isnan(v):
            m = 0.0
            continue
        m = alpha * v + (1 - alpha) * m
        out[i] = m
    return out


def main():
    err = load_errors()
    tr = (err.index <= TRAIN_END)
    e_tr, e_te = err[tr].values, err[~tr].values
    ema_te = ema_series(e_te, config.ERROR_EMA_ALPHA)
    print(f"오차 칸 수  학습(2024) {np.isfinite(e_tr).sum()} · 평가(2025~) {np.isfinite(e_te).sum()}")
    print(f"오차 크기 (평가 MAE) {np.nanmean(np.abs(e_te)):.1f} gCO2/kWh\n")

    coefs, intercepts = [], []
    table = []
    for h in range(1, H_MAX + 1):
        Xtr, ytr, _ = make_xy(e_tr, h)
        m = Ridge(alpha=1.0).fit(Xtr, ytr)
        coefs.append([round(float(c), 5) for c in m.coef_])
        intercepts.append(round(float(m.intercept_), 3))

        Xte, yte, idx = make_xy(e_te, h)
        rule = ema_te[idx] * config.ERROR_DECAY ** h
        ok = ~np.isnan(rule)
        table.append({
            "h": h,
            "0으로 보기": np.mean(np.abs(yte)),
            "지금 오차 유지(D1)": np.mean(np.abs(Xte[:, 0] - yte)),
            "규칙 EMA×DECAY^h": np.mean(np.abs(rule[ok] - yte[ok])),
            "학습 모델": np.mean(np.abs(m.predict(Xte) - yte)),
        })

    df = pd.DataFrame(table).set_index("h")
    show = df.loc[[1, 2, 4, 8, 16, 24, 32, 47]]
    show.index = [f"{h}칸 뒤 ({h / 2:g}시간)" for h in show.index]
    print("평가 기간(2025~) MAE, gCO2/kWh — 낮을수록 좋음")
    print(show.round(1).to_string())
    print("\n전체 h 평균:")
    print(df.mean().round(1).to_string())

    OUT.write_text(json.dumps({
        "lags": LAGS, "h_max": H_MAX,
        "coef": coefs, "intercept": intercepts,
        "note": "e(t+h) = intercept[h-1] + sum_k coef[h-1][k] * e(t-k). sim/train_error_persistence.py가 생성",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n저장: {OUT}")
    print("D2에서 쓰려면 controller/config.py 에서 ERROR_MODEL = \"learned\"")


if __name__ == "__main__":
    main()
