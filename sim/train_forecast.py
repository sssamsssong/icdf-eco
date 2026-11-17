"""하루 전 탄소 예측 모델 학습 (뼈대).

    python sim/train_forecast.py
    python sim/train_forecast.py --cutoff 48     # 전날 하루를 다 안다고 가정 (덜 현실적)

하는 일
1. data/raw/*.csv를 읽어 날짜(UTC) x 48칸 표로 만듦
2. 시간순 분할: 학습 ~2023 · 검증 2024 · 테스트 2025~
3. 기준선(단순 예측)과 모델들의 MAE 비교. 모델은 기준선보다 좋아야 의미가 있음
4. 검증 MAE가 가장 낮은 모델을 저장하고, 2024~ 모든 날의 하루 전 예측을 CSV로 저장
   → data/forecast/dayahead_ours.csv  (controller에서 --ours 로 사용)
5. 예측 오차가 다음 칸까지 얼마나 이어지는지(1칸 자기상관)를 계산해 ERROR_DECAY 추천값 출력

하루 전 예측의 조건
- D일 예측은 D-1일 낮 12시(UTC)에 낸다고 가정합니다. 그래서 D-1일은 앞 24칸(--cutoff)까지만 입력에 씁니다.
- 날씨 입력이 없으므로 풍력 변화는 못 맞춥니다. 발표 때 한계로 밝힙니다.

TODO
- 날씨 예보(풍속, 일사량) 입력 추가하면 크게 좋아질 수 있음
- 하이퍼파라미터 조정, 다른 모델(LightGBM, MLP) 시도
"""
import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_FORECAST = ROOT / "data" / "forecast" / "dayahead_ours.csv"
OUT_MODEL = ROOT / "models" / "dayahead.joblib"
SLOTS = 48

TRAIN_END = "2023-12-31"
VAL_END = "2024-12-31"


# ---------- 1. 데이터 ----------
def load_series() -> pd.DataFrame:
    """30분 간격 actual, forecast(API) 시계열. 짧은 빈칸(2시간 이하)만 보간."""
    files = sorted(RAW_DIR.glob("uk_carbon_*.csv"))
    if not files:
        raise SystemExit("data/raw가 비었습니다. 먼저 data/fetch_uk_carbon.py를 실행하세요.")
    df = pd.concat([pd.read_csv(f) for f in files]).drop_duplicates("time_utc")
    df["time_utc"] = pd.to_datetime(df["time_utc"], format="%Y-%m-%dT%H:%MZ")
    df = df.set_index("time_utc").sort_index()
    full = pd.date_range(df.index.min(), df.index.max(), freq="30min")
    df = df.reindex(full)
    return df.interpolate(limit=4)


def to_daily(s: pd.Series) -> pd.DataFrame:
    """시계열 → 날짜 x 48칸 표. 48칸이 다 차지 않은 날은 NaN이 남음."""
    d = s.to_frame("v")
    d["date"] = d.index.normalize()
    d["slot"] = d.index.hour * 2 + d.index.minute // 30
    return d.pivot_table(index="date", columns="slot", values="v")


# ---------- 2. 입력 만들기 ----------
def make_dataset(daily: pd.DataFrame, cutoff: int):
    """D일 목표 48칸에 대해 입력을 만듭니다.
    입력: D-1 앞 cutoff칸, D-2 48칸, D-7 48칸, 요일, 계절(sin/cos)
    """
    X, Y, dates = [], [], []
    idx = daily.index
    for d in idx:
        prev = [d - pd.Timedelta(days=k) for k in (1, 2, 7)]
        if not all(p in daily.index for p in prev):
            continue
        y = daily.loc[d].values
        d1 = daily.loc[prev[0]].values[:cutoff]
        d2 = daily.loc[prev[1]].values
        d7 = daily.loc[prev[2]].values
        if np.isnan(y).any() or np.isnan(d1).any() or np.isnan(d2).any() or np.isnan(d7).any():
            continue
        doy = d.dayofyear / 365.25 * 2 * np.pi
        cal = [d.dayofweek, np.sin(doy), np.cos(doy)]
        X.append(np.concatenate([d1, d2, d7, cal]))
        Y.append(y)
        dates.append(d)
    return np.array(X), np.array(Y), pd.DatetimeIndex(dates)


# ---------- 3. 기준선 ----------
def baselines(X: np.ndarray, cutoff: int) -> dict[str, np.ndarray]:
    d1 = X[:, :cutoff]
    d2 = X[:, cutoff:cutoff + SLOTS]
    d7 = X[:, cutoff + SLOTS:cutoff + 2 * SLOTS]
    last = np.repeat(d1[:, -1:], SLOTS, axis=1)
    return {
        "기준선: 마지막 관측값 유지": last,
        "기준선: 이틀 전 같은 시각": d2,
        "기준선: 일주일 전 같은 시각": d7,
    }


def mae(a, b) -> float:
    return float(np.mean(np.abs(a - b)))


# ---------- 4. 모델 ----------
def make_models() -> dict:
    return {
        "Ridge": make_pipeline(StandardScaler(), Ridge(alpha=10.0)),
        "GradientBoosting": MultiOutputRegressor(
            HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15),
            n_jobs=-1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", type=int, default=24, help="D-1일 중 입력에 쓸 칸 수 (24 = 낮 12시까지)")
    args = ap.parse_args()

    df = load_series()
    daily = to_daily(df["actual"])
    api_daily = to_daily(df["forecast"])
    X, Y, dates = make_dataset(daily, args.cutoff)

    tr = dates <= TRAIN_END
    va = (dates > TRAIN_END) & (dates <= VAL_END)
    te = dates > VAL_END
    print(f"날짜 수  학습 {tr.sum()} · 검증 {va.sum()} · 테스트 {te.sum()}  (입력 {X.shape[1]}개)\n")

    results = []
    for name, pred in baselines(X, args.cutoff).items():
        results.append((name, mae(pred[va], Y[va]), mae(pred[te], Y[te]), None))

    for name, model in make_models().items():
        print(f"학습 중: {name}")
        model.fit(X[tr], Y[tr])
        p = model.predict(X)
        results.append((name, mae(p[va], Y[va]), mae(p[te], Y[te]), model))

    # 참고: API forecast (하루 전 예측이 아니라 직전 단기 예측이라 비교 대상 아님)
    api = api_daily.reindex(dates).values
    ok = ~np.isnan(api).any(axis=1)
    api_te = mae(api[te & ok], Y[te & ok])

    print(f"\n{'방법':<28}{'검증 MAE':>10}{'테스트 MAE':>12}   (gCO2/kWh)")
    for name, v, t, _ in results:
        print(f"{name:<28}{v:>10.1f}{t:>12.1f}")
    print(f"{'(참고) API 단기 forecast':<28}{'':>10}{api_te:>12.1f}")

    # 검증 MAE가 가장 낮은 모델 선택
    best = min((r for r in results if r[3] is not None), key=lambda r: r[1])
    best_base = min((r for r in results if r[3] is None), key=lambda r: r[1])
    print(f"\n선택: {best[0]} (검증 MAE {best[1]:.1f}, 가장 좋은 기준선 {best_base[1]:.1f})")
    if best[1] >= best_base[1]:
        print("주의: 모델이 기준선보다 나쁩니다. 입력이나 모델을 바꿔야 합니다.")

    model = best[3]
    OUT_MODEL.parent.mkdir(exist_ok=True)
    joblib.dump({"model": model, "cutoff": args.cutoff}, OUT_MODEL)

    # 2024~ 모든 날 예측 저장 (controller --ours 에서 사용)
    keep = va | te
    pred = model.predict(X[keep])
    rows = []
    for d, p in zip(dates[keep], pred):
        for s in range(SLOTS):
            t = d + pd.Timedelta(minutes=30 * s)
            rows.append((t.strftime("%Y-%m-%dT%H:%MZ"), round(float(p[s]), 1)))
    OUT_FORECAST.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows, columns=["time_utc", "forecast"]).to_csv(OUT_FORECAST, index=False)
    print(f"모델 저장: {OUT_MODEL}")
    print(f"예측 저장: {OUT_FORECAST}  ({keep.sum()}일)")

    # ---------- 5. 오차 지속 정도 → ERROR_DECAY ----------
    err = (model.predict(X[va]) - Y[va]).ravel()   # 검증 기간 오차를 시간순으로 이어 붙임
    rho = float(np.corrcoef(err[:-1], err[1:])[0, 1])
    print(f"\n검증 기간 예측 오차의 1칸(30분) 자기상관 = {rho:.3f}")
    print(f"→ controller/config.py 의 ERROR_DECAY 를 {rho:.2f} 로 바꾸는 것을 추천합니다.")


if __name__ == "__main__":
    main()
