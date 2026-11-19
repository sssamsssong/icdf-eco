// 하드웨어 시험용: 팬 4개를 D3 → D5 → D6 → D11 순서로 하나씩 돌립니다.
// 한 팬씩 3초 켜고 1초 쉬고, 마지막에 4개를 함께 3초 켠 뒤 처음부터 반복합니다.
// 시리얼 모니터 115200 (줄 끝: 새 줄)
//   x = 멈추고 모두 끄기, r = 다시 순서대로 돌리기
//   1~4 = 그 팬만 켜 두기 (1 = D3, 2 = D5, 3 = D6, 4 = D11), a = 모두 켜기
// 1, 2번은 B 랙 / 3, 4번은 D2 랙

const int FAN_PINS[4] = {3, 5, 6, 11};
const unsigned long ON_MS = 3000;
const unsigned long GAP_MS = 1000;

bool running = true;    // 순서대로 자동으로 돌리는 중인지
int step = 0;           // 0~3 = 팬 하나씩, 4 = 모두
bool inGap = false;
unsigned long stepStart = 0;

void allOff() {
  for (int i = 0; i < 4; i++) digitalWrite(FAN_PINS[i], LOW);
}

void only(int idx) {
  allOff();
  digitalWrite(FAN_PINS[idx], HIGH);
}

void allOn() {
  for (int i = 0; i < 4; i++) digitalWrite(FAN_PINS[i], HIGH);
}

void announce() {
  if (step < 4) {
    Serial.print(step + 1); Serial.print("번 팬 (D"); Serial.print(FAN_PINS[step]); Serial.println(") 켜짐");
  } else {
    Serial.println("4개 모두 켜짐");
  }
}

void startStep() {
  inGap = false;
  stepStart = millis();
  if (step < 4) only(step); else allOn();
  announce();
}

void setup() {
  for (int i = 0; i < 4; i++) {
    pinMode(FAN_PINS[i], OUTPUT);
    digitalWrite(FAN_PINS[i], LOW);
  }
  Serial.begin(115200);
  Serial.println("팬 순서 시험: D3 → D5 → D6 → D11 → 모두");
  Serial.println("x = 멈춤, r = 다시 시작, 1~4 = 그 팬만, a = 모두 켜기");
  startStep();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'x') { running = false; allOff(); Serial.println("멈춤, 모두 꺼짐"); }
    else if (c == 'r') { running = true; step = 0; startStep(); }
    else if (c >= '1' && c <= '4') {
      running = false; only(c - '1');
      Serial.print(c); Serial.print("번 팬 (D"); Serial.print(FAN_PINS[c - '1']); Serial.println(")만 켜 둠. r = 다시 순서대로");
    }
    else if (c == 'a') { running = false; allOn(); Serial.println("4개 모두 켜 둠. r = 다시 순서대로"); }
  }

  if (!running) return;
  unsigned long now = millis();
  if (!inGap && now - stepStart >= ON_MS) {
    allOff();
    inGap = true;
    stepStart = now;
  } else if (inGap && now - stepStart >= GAP_MS) {
    step = (step + 1) % 5;
    if (step == 0) Serial.println("--- 처음부터 ---");
    startStep();
  }
}
