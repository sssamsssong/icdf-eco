"""GUI용 작은 웹 서버. 시연 엔진과 같은 프로세스에서 별도 스레드로 돕니다.

GET  /        → gui/index.html
GET  /state   → 지금 상태 (JSON)
POST /cloud   → 구름 켜기/끄기
POST /start   → 시작 (끝난 뒤에는 처음부터 다시)
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

GUI_HTML = Path(__file__).resolve().parent.parent / "gui" / "index.html"


class Shared:
    """엔진과 서버가 함께 보는 상태."""

    def __init__(self):
        self.lock = threading.Lock()
        self.state: dict = {"status": "ready"}
        self.cloud = False
        self.sensor: dict | None = None   # 조도센서 실시간 값 (화면 표시용)
        self.start_event = threading.Event()

    def set_state(self, state: dict):
        with self.lock:
            self.state = state

    def get_json(self) -> bytes:
        with self.lock:
            s = dict(self.state)
        s["cloud"] = self.cloud
        s["sensor"] = self.sensor
        return json.dumps(s, ensure_ascii=False).encode("utf-8")

    def toggle_cloud(self) -> bool:
        with self.lock:
            self.cloud = not self.cloud
            return self.cloud


def start_server(shared: Shared, port: int = 8000) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, ctype: str, code: int = 200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(GUI_HTML.read_bytes(), "text/html; charset=utf-8")
            elif self.path.strip("/").removesuffix(".html") in ("classic", "detail", "ko"):  # 다른 화면 (자세한 화면, 예전 화면, 한국어 화면)
                name = self.path.strip("/").removesuffix(".html") + ".html"
                self._send(GUI_HTML.with_name(name).read_bytes(), "text/html; charset=utf-8")
            elif self.path.startswith("/state"):
                self._send(shared.get_json(), "application/json; charset=utf-8")
            else:
                self._send(b"not found", "text/plain", 404)

        def do_POST(self):
            if self.path == "/cloud":
                shared.toggle_cloud()
            elif self.path == "/start":
                shared.start_event.set()
            else:
                return self._send(b"not found", "text/plain", 404)
            self._send(shared.get_json(), "application/json; charset=utf-8")

        def log_message(self, *args):  # 요청마다 찍히는 로그 끄기
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
