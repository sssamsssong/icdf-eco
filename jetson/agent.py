"""Jetson 에이전트: 메인 PC 명령으로 AI 작업을 켜고 끄고, 보드 전력을 알려 줍니다.

Jetson에서 (랙 하나에 Jetson 하나):
    python3 agent.py                 # 0.0.0.0:8100
    python3 agent.py --port 8100 --workers 2

메인 PC에서 Jetson 없이 시험:
    python agent.py --mock --port 8101       # 가짜 전력값 (작업 수에 따라 올라감)

HTTP
    GET  /status         → {"jobs", "workers", "source", "idle_mw", "workload"}
    POST /jobs?n=2       → 작업 n개 실행 (0 = 모두 멈춤). 응답은 /status와 같음
    GET  /power          → 지난 /power 이후 평균 전력 {"avg_mw", "last_mw", "samples", "jobs", "idle_mw"}

안전장치: 메인 PC에서 WATCHDOG_S초 동안 /jobs 명령이 없으면 작업을 모두 멈춥니다.
표준 라이브러리만 씁니다. 작업은 PyTorch(CUDA)가 있으면 GPU 행렬곱, 없으면 numpy, 그것도 없으면 순수 파이썬 계산입니다.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import random
import re
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

WATCHDOG_S = 30
# Orin Nano (JetPack 5/6): "VDD_IN 4936mW/4936mW", 예전 Nano: "POM_5V_IN 2510/2510"
POWER_RE = re.compile(r"(?:VDD_IN|POM_5V_IN)\s+(\d+)(?:mW)?/")


# ---------------- 작업 (별도 프로세스) ----------------

def worker(active, ready, kind_out):
    """active가 켜져 있는 동안 계산을 반복합니다. 시작할 때 한 번만 준비해서 켜고 끄기가 빠릅니다."""
    step, kind = _make_workload()
    kind_out.value = kind.encode()[:31]
    ready.set()
    while True:
        if active.is_set():
            step()
        else:
            time.sleep(0.02)


def _make_workload():
    try:
        import torch
        if torch.cuda.is_available():
            a = torch.randn(1024, 1024, device="cuda", dtype=torch.float16)
            b = torch.randn(1024, 1024, device="cuda", dtype=torch.float16)

            def step():
                for _ in range(20):
                    torch.matmul(a, b)
                torch.cuda.synchronize()
            step()  # CUDA 초기화
            return step, "torch-cuda"
    except Exception:
        pass
    try:
        import numpy as np
        a = np.random.rand(256, 256).astype(np.float32)

        def step():
            a @ a
        return step, "numpy-cpu"
    except Exception:
        pass

    def step():
        s = 0
        for i in range(20000):
            s += i * i
    return step, "python-cpu"


# ---------------- 전력 측정 ----------------

class PowerMeter:
    """tegrastats를 읽어 샘플을 모읍니다. mock이면 작업 수에 맞춰 가짜 값을 만듭니다."""

    def __init__(self, mock: bool, get_jobs, interval_ms: int = 250):
        self.mock = mock
        self.get_jobs = get_jobs
        self.interval_ms = interval_ms
        self.lock = threading.Lock()
        self.samples: list[int] = []
        self.last_mw: int | None = None
        self.source = "mock" if mock else "tegrastats"
        self.error: str | None = None
        threading.Thread(target=self._run, daemon=True).start()

    def _add(self, mw: int):
        with self.lock:
            self.samples.append(mw)
            self.last_mw = mw

    def _run(self):
        if self.mock:
            while True:
                self._add(int(5000 + 2500 * self.get_jobs() + random.uniform(-150, 150)))
                time.sleep(self.interval_ms / 1000)
        exe = shutil.which("tegrastats") or "/usr/bin/tegrastats"
        try:
            proc = subprocess.Popen([exe, "--interval", str(self.interval_ms)],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except OSError as e:
            self.error = f"tegrastats 실행 실패: {e}"
            print(self.error)
            return
        warned = False
        for line in proc.stdout:
            m = POWER_RE.search(line)
            if m:
                self._add(int(m.group(1)))
            elif not warned:
                warned = True
                self.error = "VDD_IN 항목 없음: " + line.strip()[:160]
                print(self.error, "\n→ POWER_RE를 실제 출력에 맞게 고치세요.")

    def take(self) -> dict:
        """지난 호출 이후 평균을 돌려주고 비웁니다."""
        with self.lock:
            s, self.samples = self.samples, []
            last = self.last_mw
        avg = sum(s) / len(s) if s else last
        return {"avg_mw": None if avg is None else round(avg), "last_mw": last, "samples": len(s)}

    def average_for(self, seconds: float) -> int | None:
        self.take()
        time.sleep(seconds)
        return self.take()["avg_mw"]


# ---------------- 에이전트 ----------------

class Agent:
    def __init__(self, n_workers: int, mock: bool):
        self.n_workers = n_workers
        self.mock = mock
        self.jobs = 0
        self.last_cmd = time.monotonic()
        self.lock = threading.Lock()
        self.flags = []
        self.kinds = []
        if not mock:
            ctx = mp.get_context("spawn")
            readies = []
            for _ in range(n_workers):
                active, ready, kind = ctx.Event(), ctx.Event(), ctx.Array("c", 32)
                ctx.Process(target=worker, args=(active, ready, kind), daemon=True).start()
                self.flags.append(active)
                readies.append(ready)
                self.kinds.append(kind)
            print(f"작업 프로세스 {n_workers}개 준비 중…")
            for r in readies:
                r.wait(120)
        self.meter = PowerMeter(mock, lambda: self.jobs)
        print("대기 전력 재는 중 (3초)…")
        self.idle_mw = self.meter.average_for(3.0)
        print(f"준비 완료. 작업 종류 {self.workload()}, 대기 전력 {self.idle_mw} mW, 전력 출처 {self.meter.source}")
        threading.Thread(target=self._watchdog, daemon=True).start()

    def workload(self) -> str:
        if self.mock:
            return "mock"
        return ",".join(sorted({k.value.decode() for k in self.kinds})) or "?"

    def set_jobs(self, n: int):
        n = max(0, min(self.n_workers, n))
        with self.lock:
            self.last_cmd = time.monotonic()
            if n != self.jobs:
                for i, f in enumerate(self.flags):
                    f.set() if i < n else f.clear()
                self.jobs = n

    def _watchdog(self):
        while True:
            time.sleep(1)
            if self.jobs and time.monotonic() - self.last_cmd > WATCHDOG_S:
                print(f"{WATCHDOG_S}초 동안 명령이 없어 작업을 모두 멈춥니다.")
                self.set_jobs(0)

    def status(self) -> dict:
        return {"jobs": self.jobs, "workers": self.n_workers, "source": self.meter.source,
                "idle_mw": self.idle_mw, "workload": self.workload(), "error": self.meter.error}


def serve(agent: Agent, host: str, port: int):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/status":
                self._json(agent.status())
            elif path == "/power":
                self._json({**agent.meter.take(), "jobs": agent.jobs, "idle_mw": agent.idle_mw})
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            u = urlparse(self.path)
            if u.path != "/jobs":
                return self._json({"error": "not found"}, 404)
            try:
                n = int(parse_qs(u.query).get("n", ["0"])[0])
            except ValueError:
                return self._json({"error": "n은 정수"}, 400)
            agent.set_jobs(n)
            self._json(agent.status())

        def log_message(self, *args):
            pass

    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"http://{host}:{port}/status 에서 대기 중 (Ctrl+C 종료)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        agent.set_jobs(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--workers", type=int, default=2, help="최대 작업 수 (랙의 팬 수와 같게)")
    ap.add_argument("--mock", action="store_true", help="Jetson 없이 가짜 전력값으로 시험")
    args = ap.parse_args()
    serve(Agent(args.workers, args.mock), args.host, args.port)


if __name__ == "__main__":
    main()
