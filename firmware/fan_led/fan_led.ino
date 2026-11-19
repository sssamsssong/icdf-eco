// ICDF_eco 아두이노 펌웨어: 팬 4개 + 조도센서 BH1750 (구름 스테이션)
// 시리얼 115200.
//   받는 명령: 한 줄에 "번호 값" (예: "1 1", "3 0")
//     번호 1~4: 팬 (값 1 = 켜기, 0 = 끄기)
//     번호 9  : LED 바 값. LED 바는 쓰지 않기로 해서 받기만 하고 아무것도 안 함
//   보내는 값: 0.2초마다 "LUX 523.4" (센서를 못 읽으면 "LUX -1")
// 팬 1, 2 = B 랙 (D3, D5) / 팬 3, 4 = D2 랙 (D6, D11)
// 조도센서 BH1750: SDA = A4, SCL = A5, VCC = 5V(또는 3.3V), GND
// 라이브러리 없이 Wire만 사용합니다.

#include <Wire.h>

const int FAN_PINS[4] = {3, 5, 6, 11};
const unsigned long LUX_EVERY_MS = 200;

uint8_t bhAddr = 0;   // 찾은 BH1750 주소 (0x23 또는 0x5C), 없으면 0

void setFan(int idx, bool on) {
  digitalWrite(FAN_PINS[idx], on ? HIGH : LOW);
}

void findSensor() {
  bhAddr = 0;
  const uint8_t addrs[2] = {0x23, 0x5C};
  for (int i = 0; i < 2; i++) {
    Wire.beginTransmission(addrs[i]);
    if (Wire.endTransmission() == 0) { bhAddr = addrs[i]; break; }
  }
  if (Wire.getWireTimeoutFlag()) Wire.clearWireTimeoutFlag();
  if (bhAddr) {
    Wire.beginTransmission(bhAddr); Wire.write(0x01); Wire.endTransmission();  // 전원 켜기
    Wire.beginTransmission(bhAddr); Wire.write(0x10); Wire.endTransmission();  // 연속 고해상도 모드
  }
}

float readLux() {
  if (!bhAddr) return -1;
  if (Wire.requestFrom(bhAddr, (uint8_t)2) != 2) { bhAddr = 0; return -1; }  // 선이 빠지면 다시 찾게 함
  uint16_t raw = (Wire.read() << 8) | Wire.read();
  return raw / 1.2;
}

void handleLine(String line) {
  line.trim();
  if (!line.length()) return;
  int sp = line.indexOf(' ');
  if (sp < 0) { Serial.println("ERR format"); return; }
  int n = line.substring(0, sp).toInt();
  int v = line.substring(sp + 1).toInt();
  if (n >= 1 && n <= 4) {
    setFan(n - 1, v != 0);
    Serial.print("OK fan "); Serial.print(n); Serial.println(v ? " on" : " off");
  } else if (n == 9) {
    // LED 바 없음: 조용히 무시
  } else {
    Serial.println("ERR number");
  }
}

void setup() {
  for (int i = 0; i < 4; i++) {
    pinMode(FAN_PINS[i], OUTPUT);
    digitalWrite(FAN_PINS[i], LOW);  // 시작은 모두 끔
  }
  Serial.begin(115200);
  Serial.setTimeout(50);
  Wire.begin();
  Wire.setWireTimeout(3000, true);  // 센서 선이 붙잡혀도 팬 제어가 멈추지 않게 (3ms)
  findSensor();
  Serial.println("READY");
}

void loop() {
  while (Serial.available()) handleLine(Serial.readStringUntil('\n'));

  static unsigned long lastFind = 0;
  if (!bhAddr && millis() - lastFind >= 2000) {  // 센서가 없으면 2초마다 다시 찾기
    lastFind = millis();
    findSensor();
  }
  static unsigned long lastLux = 0;
  if (millis() - lastLux >= LUX_EVERY_MS) {
    lastLux = millis();
    Serial.print("LUX ");
    Serial.println(readLux(), 1);
  }
}
