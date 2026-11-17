"""B (하루 전 고정, 구글식)와 D2 (단기 예측 + 이득-비용 보정, 우리 방식) 스케줄러.

용어
- 슬롯: 30분 한 칸. 하루 48칸.
- 작업: 필요한 슬롯 수(need)와 마감 슬롯(deadline)을 가짐. 쪼개서 실행 가능.
- 계획(plan): plan[t] = 슬롯 t에 돌릴 작업 id 목록 (최대 FANS_PER_RACK개).
"""
import json
from dataclasses import dataclass
from pathlib import Path

from . import config

WARN = True  # 하루 전 계획에서 마감 안에 다 못 넣었을 때 경고 출력


@dataclass
class Job:
    id: str
    need: int               # 필요한 슬롯 수
    deadline: int           # 이 슬롯 전까지 끝나야 함 (0~48)
    urgent: bool = False    # 긴급 작업은 계획 고정, 옮기지 않음
    done: int = 0


def default_jobs() -> list[Job]:
    """시연용 작업 큐. 두 랙에 똑같이 줍니다. (TODO: 시연 시나리오에 맞게 조정)"""
    return [
        Job("urgent-1", need=4, deadline=8, urgent=True),
        Job("train-1", need=10, deadline=48),
        Job("train-2", need=8, deadline=40),
        Job("batch-1", need=6, deadline=30),
        Job("batch-2", need=6, deadline=48),
        Job("batch-3", need=4, deadline=24),
    ]


def plan_day_ahead(jobs: list[Job], forecast: list[float]) -> list[list[str]]:
    """하루 전 계획: 긴급 작업은 맨 앞에, 유연한 작업은 마감 안의 예측상 가장 깨끗한 슬롯에."""
    n = config.SLOTS_PER_DAY
    cap = config.FANS_PER_RACK
    plan: list[list[str]] = [[] for _ in range(n)]

    for job in sorted(jobs, key=lambda j: (not j.urgent, j.deadline)):
        if job.urgent:
            candidates = range(job.deadline)
        else:
            candidates = sorted(range(job.deadline), key=lambda t: forecast[t])
        placed = 0
        for t in candidates:
            if placed == job.need:
                break
            if len(plan[t]) < cap:
                plan[t].append(job.id)
                placed += 1
        if placed < job.need and WARN:
            print(f"경고: {job.id}를 마감 안에 다 배치하지 못했습니다 ({placed}/{job.need})")
    return plan


class FixedScheduler:
    """B: 하루 전 계획을 그대로 실행합니다."""
    name = "B"

    def __init__(self, jobs: list[Job], forecast: list[float]):
        self.jobs = {j.id: j for j in jobs}
        self.forecast = forecast
        self.plan = plan_day_ahead(jobs, forecast)
        self.changes = 0

    def step(self, t: int, observed: float) -> list[str]:
        """슬롯 t의 실제 탄소 값을 보고 이번 슬롯에 돌릴 작업 목록을 돌려줍니다."""
        running = self.plan[t]
        for jid in running:
            self.jobs[jid].done += 1
        return running


class CorrectingScheduler(FixedScheduler):
    """D2: 하루 전 계획을 유지하되, 오차가 이어질 것 같고 옮기는 이득이 람다보다 클 때만 고칩니다.

    첫 버전 로직:
    1. 오차 Δ = 관측 - 예측을 매 슬롯 기록.
    2. 앞으로 h슬롯 뒤 오차를 추정해 남은 시간 예측을 갱신.
       - config.ERROR_MODEL = "rule"   : EMA x DECAY^h
       - config.ERROR_MODEL = "learned": 최근 오차 8칸으로 h칸 뒤 오차를 맞추는 학습 모델 (error_model.json)
    3. 이번 슬롯에 계획된 유연 작업마다, 마감 안의 뒤쪽 빈 슬롯 중 갱신 예측이 가장 낮은 곳을 찾음.
    4. 이득 = (지금 갱신 예측 - 그 슬롯 갱신 예측) x kWh 가 람다보다 크면 옮김.
    TODO: 변경을 되돌리는(당겨오는) 경우 처리.
    """
    name = "D2"
    MODEL_PATH = Path(__file__).resolve().parent / "error_model.json"

    _model_cache = None

    def __init__(self, jobs, forecast, lam: float | None = None, error_model: str | None = None,
                 max_changes: int | None = None):
        """lam, error_model, max_changes를 안 주면 config 값을 씁니다 (장기 시뮬레이션에서 바꿔 가며 사용).
        error_model: "learned" (D2) / "delta" = 지금 슬롯 오차만 반영, 미래는 원래 예측대로 (D1) / "rule" = EMA x DECAY^h
        """
        super().__init__(jobs, forecast)
        self.lam = config.LAMBDA_G if lam is None else lam
        self.error_model = error_model or config.ERROR_MODEL
        self.max_changes = config.MAX_CHANGES_PER_DAY if max_changes is None else max_changes
        self.err_ema = 0.0
        self.errors: list[float] = []
        self.log: list[str] = []
        self.events: list[dict] = []   # GUI용 변경 기록
        self.model = None
        if self.error_model == "learned":
            if CorrectingScheduler._model_cache is None:
                CorrectingScheduler._model_cache = json.loads(self.MODEL_PATH.read_text(encoding="utf-8"))
            self.model = CorrectingScheduler._model_cache

    def future_error(self, h: int) -> float:
        """h칸 뒤 오차 추정."""
        if self.error_model == "delta":
            return self.errors[-1] if h == 0 else 0.0
        if self.model is None:
            return self.err_ema * (config.ERROR_DECAY ** h)
        if h == 0:
            return self.errors[-1]
        m = self.model
        k = min(h, m["h_max"]) - 1
        recent = self.errors[::-1][:m["lags"]]
        recent += [0.0] * (m["lags"] - len(recent))   # 하루 시작 직후는 0으로 채움
        return m["intercept"][k] + sum(c * e for c, e in zip(m["coef"][k], recent))

    def updated_forecast(self, t: int, h: int) -> float:
        return self.forecast[t + h] + self.future_error(h)

    def step(self, t: int, observed: float) -> list[str]:
        a = config.ERROR_EMA_ALPHA
        err = observed - self.forecast[t]
        self.err_ema = a * err + (1 - a) * self.err_ema
        self.errors.append(err)

        upd = None  # 갱신 예측 곡선. 필요할 때 슬롯마다 한 번만 계산
        for jid in list(self.plan[t]):
            job = self.jobs[jid]
            if job.urgent or self.changes >= self.max_changes:
                continue
            if upd is None:
                upd = [self.updated_forecast(t, h) for h in range(len(self.forecast) - t)]
            now_val = upd[0]
            best_t, best_val = None, now_val
            for t2 in range(t + 1, job.deadline):
                if len(self.plan[t2]) >= config.FANS_PER_RACK or jid in self.plan[t2]:
                    continue
                v = upd[t2 - t]
                if v < best_val:
                    best_t, best_val = t2, v
            if best_t is None:
                continue
            gain_g = (now_val - best_val) * config.KWH_PER_SLOT
            if gain_g > self.lam:
                self.plan[t].remove(jid)
                self.plan[best_t].append(jid)
                self.changes += 1
                self.log.append(f"t={t}: {jid} → t={best_t} (이득 {gain_g:.1f} g)")
                self.events.append({"t": t, "job": jid, "to": best_t, "gain": round(gain_g, 1)})

        return super().step(t, observed)
