// ICDF_eco 아두이노 펌웨어: 팬 4개 + WS2812 LED 바
// 시리얼 115200, 한 줄에 "번호 값" 형식 (예: "1 1", "3 0", "9 75")
//   번호 1~4: 팬 (값 1 = 켜기, 0 = 끄기)
//   번호 9  : LED 바 탄소 값 (0 = 초록, 100 = 빨강)
// 팬 1, 2 = B 랙 (D3, D5) / 팬 3, 4 = D2 랙 (D6, D11)
// 필요 라이브러리: Adafruit NeoPixel

#include <Adafruit_NeoPixel.h>

const int FAN_PINS[4] = {3, 5, 6, 11};
const int LED_PIN = 7;
const int NUM_LEDS = 30;
const int BRIGHTNESS = 60;

Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

void setFan(int idx, bool on) {
  digitalWrite(FAN_PINS[idx], on ? HIGH : LOW);
}

// 0~100 값을 초록 → 노랑 → 빨강으로 표시
void showCarbon(int v) {
  v = constrain(v, 0, 100);
  uint8_t r = map(v, 0, 100, 0, 255);
  uint8_t g = map(v, 0, 100, 255, 0);
  for (int i = 0; i < NUM_LEDS; i++) strip.setPixelColor(i, strip.Color(r, g, 0));
  strip.show();
}

void setup() {
  for (int i = 0; i < 4; i++) {
    pinMode(FAN_PINS[i], OUTPUT);
    digitalWrite(FAN_PINS[i], LOW);  // 시작은 모두 끔
  }
  strip.begin();
  strip.setBrightness(BRIGHTNESS);
  showCarbon(0);
  Serial.begin(115200);
  Serial.println("READY");
}

void loop() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  int sp = line.indexOf(' ');
  if (sp < 0) { Serial.println("ERR format"); return; }

  int n = line.substring(0, sp).toInt();
  int v = line.substring(sp + 1).toInt();

  if (n >= 1 && n <= 4) {
    setFan(n - 1, v != 0);
    Serial.print("OK fan "); Serial.print(n); Serial.println(v ? " on" : " off");
  } else if (n == 9) {
    showCarbon(v);
    Serial.print("OK led "); Serial.println(v);
  } else {
    Serial.println("ERR number");
  }
}
