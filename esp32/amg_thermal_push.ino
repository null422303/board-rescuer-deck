// AMG8833 -> "Thermal" hotspot -> VPS.  Sends ONLY thermal data, as fast as possible.
//
// Board : ESP32 classic (DOIT ESP32 DEVKIT V1 / ESP32-D0WD-V3)
//         FQBN esp32:esp32:esp32doit-devkit-v1
//   AMG8833 SDA -> GPIO21   SCL -> GPIO22   VIN -> 3V3
//
// Wire format: one HTTP/1.1 request, body = 128 bytes = 64 x int16 (degC x100).
// No JSON, no metadata. Persistent keep-alive + fire-and-forget (no RTT wait).

#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <Adafruit_AMG88xx.h>

const char* SSID = "YOUR_WIFI_SSID";
const char* PASS = "YOUR_WIFI_PASSWORD";
const char* HOST = "thermal.144.202.52.34.nip.io";
const char* TOKEN = "YOUR_DEVICE_TOKEN";
#define INGEST_PORT 443

#define SDA_PIN 21
#define SCL_PIN 22
#define STATUS_LED 2

#define POST_INTERVAL_MS 100UL   // = AMG8833 hardware max (10 fps); no duplicate frames
#define WIFI_TIMEOUT_MS  20000UL

Adafruit_AMG88xx amg;
WiFiClientSecure tls;
bool sensorOK = false;
uint32_t sent = 0, fails = 0;
int16_t payload[64];

void connectWiFi() {
  Serial.printf("[wifi] joining \"%s\"\n", SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(SSID, PASS);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < WIFI_TIMEOUT_MS) {
    delay(300); Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED)
    Serial.printf("[wifi] up ip=%s rssi=%d ch=%d\n",
                  WiFi.localIP().toString().c_str(), WiFi.RSSI(), WiFi.channel());
  else
    Serial.println("[wifi] FAILED");
}

unsigned long connAt = 0;
bool ensureConn() {
  if (tls.connected()) return true;
  tls.stop();
  tls.setInsecure();
  unsigned long t0 = millis();
  bool ok = tls.connect(HOST, INGEST_PORT);
  if (ok) connAt = millis();
  Serial.printf("[tls] %s (%lums)\n", ok ? "up" : "FAIL", millis() - t0);
  return ok;
}

uint32_t drainedBytes = 0;
void drain() {          // MUST keep up with responses or the server's writes block
  int budget = 4096;    // cap per call so the send path never starves
  static uint8_t tmp[512];
  while (budget > 0) {
    int avail = tls.available();
    if (avail <= 0) break;
    if (avail > (int)sizeof(tmp)) avail = sizeof(tmp);
    int n = tls.read(tmp, avail);
    if (n <= 0) break;
    drainedBytes += n;
    budget -= n;
  }
}

void push() {
  float p[64];
  if (sensorOK) amg.readPixels(p);
  else for (int i = 0; i < 64; i++) p[i] = 0;
  for (int i = 0; i < 64; i++) payload[i] = (int16_t)lroundf(p[i] * 100.0f);

  if (!ensureConn()) { fails++; return; }

  char hdr[256];
  int hl = snprintf(hdr, sizeof(hdr),
                    "POST /api/ingest HTTP/1.1\r\nHost: %s\r\nX-Auth-Token: %s\r\n"
                    "Content-Type: application/octet-stream\r\nContent-Length: 128\r\n"
                    "Connection: keep-alive\r\n\r\n", HOST, TOKEN);

  // header + payload in ONE write (single TCP segment, no Nagle stall)
  static uint8_t pkt[256 + 128];
  memcpy(pkt, hdr, hl);
  memcpy(pkt + hl, payload, 128);
  size_t w = tls.write(pkt, hl + 128);
  if (w != (size_t)(hl + 128)) {
    fails++;
    Serial.printf("[push] short write %u/%u -> reconnect\n", (unsigned)w, (unsigned)(hl + 128));
    tls.stop();
    return;
  }
  sent++;
  digitalWrite(STATUS_LED, LOW); delayMicroseconds(300); digitalWrite(STATUS_LED, HIGH);
}

void setup() {
  Serial.begin(115200);
  delay(400);
  Serial.println("\n=== AMG8833 -> VPS (128B binary, keep-alive) ===");
  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(STATUS_LED, HIGH);

  Wire.begin(SDA_PIN, SCL_PIN);
  Serial.print("[i2c] scan:");
  int found = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) { Serial.printf(" 0x%02X", a); found++; }
  }
  if (!found) Serial.print(" (none)");
  Serial.println();

  sensorOK = amg.begin();
  Serial.printf("[amg] begin(): %s\n", sensorOK ? "OK" : "FAILED");
  connectWiFi();
  tls.setInsecure();
}

void loop() {
  static unsigned long lastPost = 0, lastLog = 0, lastWatch = 0;
  static uint32_t wSent = 0, wDrained = 0;

  if (WiFi.status() != WL_CONNECTED) {
    tls.stop();
    static unsigned long lastTry = 0;
    if (millis() - lastTry > 5000) { lastTry = millis(); connectWiFi(); }
    delay(100); return;
  }
  if (millis() - lastPost >= POST_INTERVAL_MS) { lastPost = millis(); push(); }
  drain();

  if (millis() - lastWatch > 10000) {
    if ((sent - wSent) > 40 && drainedBytes == wDrained) {
      Serial.printf("[watch] no acks (sent=%u drained=%u) -> reconnect\n", sent, drainedBytes);
      tls.stop();
    }
    wSent = sent; wDrained = drainedBytes; lastWatch = millis();
  }
  // safety net: recycle the connection every 5 min so no backlog can build up
  if (connAt && millis() - connAt > 300000UL) {
    Serial.println("[tls] periodic recycle");
    tls.stop();
  }
  if (millis() - lastLog > 3000) {
    lastLog = millis();
    Serial.printf("[stat] sent=%u drained=%u fails=%u rssi=%d heap=%u\n",
                  sent, drainedBytes, fails, WiFi.RSSI(), (unsigned)ESP.getFreeHeap());
  }
  delay(1);
}
