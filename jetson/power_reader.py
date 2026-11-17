"""tegrastats 출력에서 보드 전력(mW)을 읽어 출력합니다. (Jetson에서 실행)

    python3 power_reader.py

TODO: 출력 대신 메인 PC로 전송 (UDP/HTTP).
"""
import re
import subprocess

# 예: "VDD_IN 4500mW/4500mW". JetPack 버전에 따라 이름이 다르면 여기를 고치세요.
PATTERN = re.compile(r"VDD_IN (\d+)mW")


def main():
    proc = subprocess.Popen(["tegrastats", "--interval", "1000"], stdout=subprocess.PIPE, text=True)
    for line in proc.stdout:
        m = PATTERN.search(line)
        if m:
            print(int(m.group(1)), "mW")
        else:
            print("VDD_IN 항목 없음:", line.strip()[:120])


if __name__ == "__main__":
    main()
