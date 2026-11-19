"""아두이노에 팬 명령을 보내고, 조도센서 값(LUX)을 받습니다. dry_run이면 아무것도 보내지 않습니다."""
import threading
import time

from . import config


class Arduino:
    def __init__(self, port: str | None, dry_run: bool = False):
        self.dry_run = dry_run or port is None
        self.ser = None
        self.lux: float | None = None      # 가장 최근 조도 (센서가 없으면 None)
        self.lux_time = 0.0
        self._acc: list[float] = []        # take_lux()가 가져가기 전까지 모은 값
        self._lock = threading.Lock()
        if not self.dry_run:
            import serial  # pyserial
            self.ser = serial.Serial(port, config.BAUD, timeout=0.2)
            time.sleep(2)  # 포트를 열면 아두이노가 리셋되므로 잠깐 기다림
            self.ser.reset_input_buffer()
            threading.Thread(target=self._read_loop, daemon=True).start()

    def _read_loop(self):
        """아두이노가 0.2초마다 보내는 "LUX 523.4" 줄을 읽습니다."""
        while self.ser is not None:
            try:
                line = self.ser.readline().decode("ascii", errors="ignore").strip()
            except Exception:
                return
            if not line.startswith("LUX "):
                continue
            try:
                v = float(line[4:])
            except ValueError:
                continue
            with self._lock:
                if v < 0:
                    self.lux = None
                else:
                    self.lux, self.lux_time = v, time.monotonic()
                    self._acc.append(v)
                    del self._acc[:-50]

    def sensor_ok(self) -> bool:
        return self.lux is not None and time.monotonic() - self.lux_time < 2.0

    def take_lux(self) -> float | None:
        """지난번 호출 이후 받은 조도의 평균 (없으면 가장 최근 값). 센서가 없으면 None."""
        with self._lock:
            acc, self._acc = self._acc, []
        if not self.sensor_ok():
            return None
        return sum(acc) / len(acc) if acc else self.lux

    def send(self, n: int, v: int):
        line = f"{n} {v}\n"
        if self.dry_run:
            return
        self.ser.write(line.encode())

    def set_fan(self, n: int, on: bool):
        self.send(n, 1 if on else 0)

    def set_led(self, value_0_100: int):
        self.send(9, max(0, min(100, int(value_0_100))))

    def all_off(self):
        for n in range(1, 5):
            self.set_fan(n, False)

    def close(self):
        if self.ser:
            self.all_off()
            time.sleep(0.1)
            ser, self.ser = self.ser, None
            ser.close()
