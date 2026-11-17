"""B (하루 전 고정, 구글식)와 D2 (단기 예측 + 이득-비용 보정, 우리 방식) 스케줄러.

용어
- 슬롯: 30분 한 칸. 하루 48칸.
- 작업: 필요한 슬롯 수(need)와 마감 슬롯(deadline)을 가짐. 쪼개서 실행 가능.
- 계획(plan): plan[t] = 슬롯 t에 돌릴 작업 id 목록 (최대 FANS_PER_RACK개).
"""
from dataclasses import dataclass, field

from . import config


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
        if placed < job.need:
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
    1. 오차 Δ = 관측 - 예측. 이동평균(EMA)으로 지금 오차 수준을 추정.
    2. 앞으로 h슬롯 뒤 오차 = EMA x DECAY^h 로 남은 시간 예측을 갱신.
    3. 이번 슬롯에 계획된 유연 작업마다, 마감 안의 뒤쪽 빈 슬롯 중 갱신 예측이 가장 낮은 곳을 찾음.
    4. 이득 = (지금 갱신 예측 - 그 슬롯 갱신 예측) x kWh 가 람다보다 크면 옮김.
    TODO: 오차 지속 추정을 학습 모델로 바꾸기, 변경을 되돌리는(당겨오는) 경우 처리.
    """
    name = "D2"

    def __init__(self, jobs, forecast):
        super().__init__(jobs, forecast)
        self.err_ema = 0.0
        self.log: list[str] = []

    def updated_forecast(self, t: int, h: int) -> float:
        return self.forecast[t + h] + self.err_ema * (config.ERROR_DECAY ** h)

    def step(self, t: int, observed: float) -> list[str]:
        a = config.ERROR_EMA_ALPHA
        self.err_ema = a * (observed - self.forecast[t]) + (1 - a) * self.err_ema

        for jid in list(self.plan[t]):
            job = self.jobs[jid]
            if job.urgent or self.changes >= config.MAX_CHANGES_PER_DAY:
                continue
            now_val = self.updated_forecast(t, 0)
            best_t, best_val = None, now_val
            for t2 in range(t + 1, job.deadline):
                if len(self.plan[t2]) >= config.FANS_PER_RACK or jid in self.plan[t2]:
                    continue
                v = self.updated_forecast(t, t2 - t)
                if v < best_val:
                    best_t, best_val = t2, v
            if best_t is None:
                continue
            gain_g = (now_val - best_val) * config.KWH_PER_SLOT
            if gain_g > config.LAMBDA_G:
                self.plan[t].remove(jid)
                self.plan[best_t].append(jid)
                self.changes += 1
                self.log.append(f"t={t}: {jid} → t={best_t} (이득 {gain_g:.1f} g)")

        return super().step(t, observed)
