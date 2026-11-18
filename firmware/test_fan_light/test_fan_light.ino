// 하드웨어 시험용: 팬 1개(D3) + 조도센서 BH1750 (I2C: A4 = SDA, A5 = SCL)
// 시리얼 115200. 센서가 없으면 2초마다 다시 찾고, 1초마다 조도(lux)를 출력하고, 입력으로 팬을 켜고 끕니다.
//   "1" = 팬 켜기, "0" = 팬 끄기, "s" = I2C 장치 다시 찾기
// 라이브러리 없이 Wire만 사용합니다.

#include <Wire.h>

const int FAN_PIN = 3;
uint8_t bhAddr = 0;      // 찾은 BH1750 주소 (0x23 또는 0x5C)
bool fanOn = false;

// 아두이노 내부 풀업을 끄고 A4/A5를 읽음. 센서 모듈에 전원이 있으면 모듈의 풀업 저항 때문에 1이 나와야 함
void checkPullups() {
  Wire.end();
  pinMode(A4, INPUT); pinMode(A5, INPUT);
  delay(5);
  int hi4 = 0, hi5 = 0;
  for (int i = 0; i < 20; i++) { hi4 += digitalRead(A4); hi5 += digitalRead(A5); delay(1); }
  Serial.print("  내부 풀업 끔: A4(SDA) 1이 나온 횟수 "); Serial.print(hi4);
  Serial.print("/20, A5(SCL) "); Serial.print(hi5); Serial.println("/20  (20/20이면 센서 쪽 풀업 있음 = 모듈 전원 OK)");
  Wire.begin();
  Wire.setWireTimeout(3000, true);
}

// 내부 1.1V 기준으로 아두이노 자신의 전원 전압(mV)을 잼 (USB 전원 확인용)
long readVcc() {
  ADMUX = _BV(REFS0) | _BV(MUX3) | _BV(MUX2) | _BV(MUX1);
  delay(2);
  ADCSRA |= _BV(ADSC);
  while (bit_is_set(ADCSRA, ADSC));
  long r = ADCL; r |= ADCH << 8;
  return 1125300L / r;
}

void scanI2C() {
  Serial.println("I2C 장치 찾는 중...");
  Serial.print("  아두이노 전원 전압: "); Serial.print(readVcc()); Serial.println(" mV (4750 이상이면 정상)");
  checkPullups();
  bhAddr = 0;
  int found = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.print("  발견: 0x");
      Serial.println(a, HEX);
      found++;
      if (a == 0x23 || a == 0x5C) bhAddr = a;
    }
  }
  if (Wire.getWireTimeoutFlag()) {
    Serial.println("  I2C 타임아웃: SDA/SCL 선이 LOW에 붙잡혀 있음 (접촉 불량, GND와 닿음, 센서 전원 없음)");
    Wire.clearWireTimeoutFlag();
  }
  Serial.print("  핀 상태: A4(SDA)=");
  Serial.print(digitalRead(A4));
  Serial.print(" A5(SCL)=");
  Serial.println(digitalRead(A5));
  if (!found) Serial.println("  I2C 장치 없음 (배선: SDA=A4, SCL=A5, VCC, GND 확인)");
  if (bhAddr) {
    Wire.beginTransmission(bhAddr); Wire.write(0x01); Wire.endTransmission();  // 전원 켜기
    Wire.beginTransmission(bhAddr); Wire.write(0x10); Wire.endTransmission();  // 연속 고해상도 모드
    Serial.print("BH1750 사용: 0x");
    Serial.println(bhAddr, HEX);
    delay(180);
  }
}

float readLux() {
  if (!bhAddr) return -1;
  if (Wire.requestFrom(bhAddr, (uint8_t)2) != 2) return -1;
  uint16_t raw = (Wire.read() << 8) | Wire.read();
  return raw / 1.2;
}

void setup() {
  pinMode(FAN_PIN, OUTPUT);
  digitalWrite(FAN_PIN, LOW);
  Serial.begin(115200);
  Wire.begin();
  Wire.setWireTimeout(3000, true);  // 선이 붙잡혀도 멈추지 않게 (3ms)
  Serial.println("TEST READY (1 = 팬 켜기, 0 = 끄기, s = I2C 다시 찾기)");
  scanI2C();
}

void loop() {
  while (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() != 1) continue;
    char c = line[0];
    if (c == '1') { fanOn = true;  digitalWrite(FAN_PIN, HIGH); Serial.println("팬 켜짐"); }
    if (c == '0') { fanOn = false; digitalWrite(FAN_PIN, LOW);  Serial.println("팬 꺼짐"); }
    if (c == 's') scanI2C();
  }
  static unsigned long lastScan = 0;
  if (!bhAddr && millis() - lastScan >= 2000) {  // 센서가 없으면 2초마다 다시 찾기 (선 만지며 확인용)
    lastScan = millis();
    scanI2C();
  }
  static unsigned long last = 0;
  if (millis() - last >= 1000) {
    last = millis();
    float lux = readLux();
    Serial.print("조도 ");
    if (lux < 0) Serial.print("읽기 실패"); else { Serial.print(lux, 1); Serial.print(" lux"); }
    Serial.print("  |  팬 ");
    Serial.println(fanOn ? "켜짐" : "꺼짐");
  }
}
