"""아두이노에 팬/LED 명령을 보냅니다. dry_run이면 화면에만 출력합니다."""
import time

from . import config


class Arduino:
    def __init__(self, port: str | None, dry_run: bool = False):
        self.dry_run = dry_run or port is None
        self.ser = None
        if not self.dry_run:
            import serial  # pyserial
            self.ser = serial.Serial(port, config.BAUD, timeout=0.1)
            time.sleep(2)  # 포트를 열면 아두이노가 리셋되므로 잠깐 기다림
            self.ser.reset_input_buffer()

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
        self.set_led(0)

    def close(self):
        if self.ser:
            self.all_off()
            time.sleep(0.1)
            self.ser.close()
