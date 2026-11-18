"""메인 PC → Jetson 연결 (jetson/agent.py와 통신).

config.JETSON_HOSTS가 비어 있으면 아무것도 하지 않습니다 (지금까지와 똑같이 동작).
Jetson이 응답하지 않으면 그 랙은 '연결 안 됨'으로 두고, JETSON_RETRY_S초마다 다시 시도합니다.
시연이 Jetson 때문에 멈추지 않도록 요청마다 JETSON_TIMEOUT_S초만 기다립니다.
"""
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import config


class _Link:
    def __init__(self, rack: str, url: str):
        self.rack = rack
        self.url = url.rstrip("/")
        self.online = False
        self.next_try = 0.0
        self.idle_mw = None
        self.workload = None
        self.last_w = None      # 마지막 측정 전력 (W)

    def _req(self, method: str, path: str) -> dict:
        req = urllib.request.Request(self.url + path, method=method)
        with urllib.request.urlopen(req, timeout=config.JETSON_TIMEOUT_S) as r:
            return json.loads(r.read().decode("utf-8"))

    def call(self, method: str, path: str) -> dict | None:
        if not self.online and time.monotonic() < self.next_try:
            return None
        try:
            d = self._req(method, path)
        except Exception:
            if self.online:
                print(f"Jetson {self.rack} ({self.url}) 연결 끊김. 가정 전력값으로 계속합니다.")
            self.online = False
            self.next_try = time.monotonic() + config.JETSON_RETRY_S
            return None
        if not self.online:
            print(f"Jetson {self.rack} 연결됨 ({self.url})")
        self.online = True
        if "idle_mw" in d:
            self.idle_mw = d["idle_mw"]
        if "workload" in d:
            self.workload = d["workload"]
        return d


class Jetsons:
    def __init__(self, hosts: dict[str, str] | None = None):
        hosts = config.JETSON_HOSTS if hosts is None else hosts
        self.links = {rack: _Link(rack, url) for rack, url in hosts.items() if url}
        self.pool = ThreadPoolExecutor(max_workers=max(1, len(self.links)))
        for link in self.links.values():
            link.call("GET", "/status")

    @property
    def enabled(self) -> bool:
        return bool(self.links)

    def _all(self, fn):
        """랙마다 동시에 요청해서 기다리는 시간이 겹치게 합니다."""
        futs = {rack: self.pool.submit(fn, link) for rack, link in self.links.items()}
        return {rack: f.result() for rack, f in futs.items()}

    def set_jobs(self, counts: dict[str, int]):
        self._all(lambda l: l.call("POST", f"/jobs?n={counts.get(l.rack, 0)}"))

    def read_power(self) -> dict[str, float | None]:
        """랙별로 지난 읽기 이후 평균 전력 중 '작업 때문에 늘어난 부분'(W)을 돌려줍니다. 연결 안 되면 None."""
        def one(link):
            d = link.call("GET", "/power")
            if not d or d.get("avg_mw") is None:
                return None
            total_w = d["avg_mw"] / 1000
            link.last_w = total_w
            idle_w = (link.idle_mw or 0) / 1000 if config.JETSON_SUBTRACT_IDLE else 0.0
            return max(0.0, total_w - idle_w)
        return self._all(one)

    def stop_all(self):
        self._all(lambda l: l.call("POST", "/jobs?n=0"))

    def summary(self) -> dict:
        return {rack: {"online": l.online, "watts": None if l.last_w is None else round(l.last_w, 2),
                       "idle_w": None if l.idle_mw is None else round(l.idle_mw / 1000, 2),
                       "workload": l.workload}
                for rack, l in self.links.items()}
