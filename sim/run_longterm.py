"""장기 시뮬레이션: 같은 작업 큐, 같은 마감으로 전략들을 비교합니다.

    python sim/run_longterm.py --period val     # 1) 검증 기간(2024)에서 람다 곡선을 보고 람다를 고름
    python sim/run_longterm.py --lam 2          # 2) 고른 람다로 테스트 기간(2025~) 평가 (테스트는 마지막에 한 번만)
    python sim/run_longterm.py --jobs random    # 날마다 다른 무작위 작업 큐 (견고성 확인)

전략
- A  즉시 실행        : 작업을 가능한 한 빨리 실행 (기준선)
- B  하루 전 고정     : 우리 하루 전 예측으로 계획하고 그대로 실행 (구글식)
- C  매 시점 재계획   : 이득이 조금이라도 있으면 바로 옮김 (람다 0, 변경 예산 없음)
- D1 Δ에만 반응       : 지금 슬롯이 예측보다 더러운지만 보고 람다 기준 보정 (미래는 원래 예측대로)
- D2 우리 방식        : 학습한 오차 지속 모델 + 람다 기준 보정
- P  완벽 예측        : 실제 값을 미리 알고 계획 (이론상 상한)

지표
- 추정 탄소 (실제 탄소 집약도 x 가정 전력량. 전력량은 config.KWH_PER_SLOT, 비율 지표에는 영향 없음)
- 계획 변경 횟수 (하루 평균)
- 마감 준수율
- 오차 손실 회복률 = (B - X) / (B - P)

결과: sim/results/ 에 CSV 2개와 그래프 1개
한계: 보정은 작업을 '뒤로 미루는' 것만 합니다. 앞당기기는 TODO.
"""
import argparse
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from controller import config  # noqa: E402
from controller import schedulers  # noqa: E402
from controller.schedulers import CorrectingScheduler, FixedScheduler, Job, default_jobs  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
OURS = ROOT / "data" / "forecast" / "dayahead_ours.csv"
OUT_DIR = Path(__file__).resolve().parent / "results"
N = config.SLOTS_PER_DAY
LAMBDAS = [0, 1, 2, 5, 10, 20, 40, 80]


def load_days(period: str) -> list[tuple[str, list[float], list[float]]]:
    raw = pd.concat([pd.read_csv(f) for f in sorted(RAW_DIR.glob("uk_carbon_*.csv"))]).drop_duplicates("time_utc")
    ours = pd.read_csv(OURS)
    df = ours.merge(raw[["time_utc", "actual"]], on="time_utc", how="left")
    df["date"] = df["time_utc"].str[:10]
    df = df[df["date"] >= "2025-01-01"] if period == "test" else df[df["date"] < "2025-01-01"]
    days = []
    for d, g in df.groupby("date"):
        if len(g) == N and g["actual"].notna().all():
            days.append((d, g["forecast"].tolist(), g["actual"].astype(float).tolist()))
    return days


def random_jobs(rng: random.Random) -> list[Job]:
    jobs = [Job("urgent", need=rng.randint(2, 6), deadline=rng.randint(6, 12), urgent=True)]
    for i in range(rng.randint(4, 7)):
        need = rng.randint(3, 10)
        jobs.append(Job(f"flex-{i}", need=need, deadline=rng.randint(max(need * 2, 16), N)))
    return jobs


def simulate(make_sched, forecast, actual, jobs) -> dict:
    s = make_sched(jobs, forecast)
    co2 = 0.0
    for t in range(N):
        running = s.step(t, actual[t])
        co2 += len(running) * config.KWH_PER_SLOT * actual[t]
    flex = [j for j in s.jobs.values()]
    met = sum(j.done >= j.need for j in flex)
    return {"co2_g": co2, "changes": s.changes, "met": met, "jobs": len(flex)}


def strategies(lam: float) -> dict:
    return {
        "A 즉시 실행": lambda j, f: FixedScheduler(j, [float(i) for i in range(N)]),
        "B 하루 전 고정": lambda j, f: FixedScheduler(j, f),
        "C 매 시점 재계획": lambda j, f: CorrectingScheduler(j, f, lam=0, error_model="learned", max_changes=10**9),
        "D1 Δ에만 반응": lambda j, f: CorrectingScheduler(j, f, lam=lam, error_model="delta"),
        "D2 우리 방식": lambda j, f: CorrectingScheduler(j, f, lam=lam, error_model="learned"),
    }


def run_all(days, job_mode, seed, makers: dict) -> dict:
    """전략별 합계. P(완벽 예측)는 forecast 자리에 실제 값을 넣은 B."""
    makers = dict(makers)
    totals = {k: {"co2_g": 0.0, "changes": 0, "met": 0, "jobs": 0} for k in list(makers) + ["P 완벽 예측"]}
    rng = random.Random(seed)
    for _, fc, ac in days:
        base_jobs = random_jobs(rng) if job_mode == "random" else default_jobs()
        for name, mk in makers.items():
            r = simulate(mk, fc, ac, [Job(j.id, j.need, j.deadline, j.urgent) for j in base_jobs])
            for k in r:
                totals[name][k] += r[k]
        r = simulate(lambda j, f: FixedScheduler(j, ac), fc, ac, [Job(j.id, j.need, j.deadline, j.urgent) for j in base_jobs])
        for k in r:
            totals["P 완벽 예측"][k] += r[k]
    return totals


def summarize(totals: dict, n_days: int) -> pd.DataFrame:
    B = totals["B 하루 전 고정"]["co2_g"]
    P = totals["P 완벽 예측"]["co2_g"]
    A = totals["A 즉시 실행"]["co2_g"] if "A 즉시 실행" in totals else None
    rows = []
    for name, t in totals.items():
        rows.append({
            "전략": name,
            "탄소 kg": round(t["co2_g"] / 1000, 1),
            "A 대비 %": round((t["co2_g"] / A - 1) * 100, 2) if A else None,
            "하루 평균 변경": round(t["changes"] / n_days, 2),
            "마감 준수율 %": round(t["met"] / t["jobs"] * 100, 2),
            "회복률 %": round((B - t["co2_g"]) / (B - P) * 100, 1) if B != P else None,
        })
    return pd.DataFrame(rows).set_index("전략")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=["val", "test"], default="test")
    ap.add_argument("--jobs", choices=["default", "random"], default="default")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--lam", type=float, default=None, help="표에 쓸 람다 (기본: config.LAMBDA_G). 검증 기간에서 고른 값을 넣으세요")
    ap.add_argument("--no-sweep", action="store_true", help="람다 곡선 생략")
    args = ap.parse_args()

    lam = config.LAMBDA_G if args.lam is None else args.lam
    schedulers.WARN = False  # 무작위 큐에서 가끔 나오는 '마감 안에 배치 못함' 경고 끄기 (모든 전략에 똑같이 적용)
    days = load_days(args.period)
    print(f"기간 {args.period}: {len(days)}일 ({days[0][0]} ~ {days[-1][0]}), 작업 큐 {args.jobs}, 람다 {lam:g}\n")
    OUT_DIR.mkdir(exist_ok=True)
    tag = f"{args.period}_{args.jobs}"

    totals = run_all(days, args.jobs, args.seed, strategies(lam))
    table = summarize(totals, len(days))
    print(table.to_string())
    table.to_csv(OUT_DIR / f"summary_{tag}.csv", encoding="utf-8-sig")

    if args.no_sweep:
        return
    print("\n람다별 결과 (D1, D2) 계산 중...")
    rows = []
    for lam in LAMBDAS:
        makers = {
            "B 하루 전 고정": strategies(lam)["B 하루 전 고정"],
            "D1": strategies(lam)["D1 Δ에만 반응"],
            "D2": strategies(lam)["D2 우리 방식"],
        }
        s = summarize(run_all(days, args.jobs, args.seed, makers), len(days))
        for name in ("D1", "D2"):
            rows.append({"람다 g": lam, "전략": name,
                         "하루 평균 변경": s.loc[name, "하루 평균 변경"], "회복률 %": s.loc[name, "회복률 %"]})
        print(f"  람다 {lam:>3}: D1 변경 {s.loc['D1', '하루 평균 변경']:5.2f} 회복 {s.loc['D1', '회복률 %']:6.1f}%"
              f" | D2 변경 {s.loc['D2', '하루 평균 변경']:5.2f} 회복 {s.loc['D2', '회복률 %']:6.1f}%")
    sweep = pd.DataFrame(rows)
    sweep.to_csv(OUT_DIR / f"lambda_sweep_{tag}.csv", index=False, encoding="utf-8-sig")
    plot(sweep, OUT_DIR / f"lambda_curve_{tag}.png", args.period)


def plot(sweep: pd.DataFrame, path: Path, period: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    have = {f.name for f in font_manager.fontManager.ttflist}
    plt.rcParams["font.family"] = next((f for f in ["Malgun Gothic", "AppleGothic", "NanumGothic"] if f in have), "DejaVu Sans")
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(7, 4.5))
    colors = {"D1": "#9aa0a6", "D2": "#1a7f5a"}
    for name, g in sweep.groupby("전략"):
        ax.plot(g["하루 평균 변경"], g["회복률 %"], marker="o", color=colors[name], label=name, linewidth=2)
        for _, r in g.iterrows():
            ax.annotate(f"λ{r['람다 g']:g}", (r["하루 평균 변경"], r["회복률 %"]),
                        textcoords="offset points", xytext=(4, 4), fontsize=8, color=colors[name])
    ax.axhline(0, color="#ccc", linewidth=1)
    ax.set_xlabel("하루 평균 계획 변경 횟수")
    ax.set_ylabel("오차 손실 회복률 (%)")
    ax.set_title(f"람다별 변경량 대비 회복률 ({'2025~ 테스트' if period == 'test' else '2024 검증'})")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    print("그래프:", path)


if __name__ == "__main__":
    main()
