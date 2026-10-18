// AMG8833 (8x8 Grid-EYE) -> WiFi station on "Thermal" hotspot, live web view.
//
// Board : ESP32 classic (DOIT ESP32 DEVKIT V1 / ESP32-D0WD-V3), FQBN
//         esp32:esp32:esp32doit-devkit-v1
//
// Wiring (classic ESP32 defaults):
//   AMG8833 VIN  -> 3V3      (3.3V ONLY, never 5V)
//   AMG8833 GND  -> GND
//   AMG8833 SDA  -> GPIO21
//   AMG8833 SCL  -> GPIO22
//   (addr 0x69 by default; tie A0/addr pin to GND for 0x68)
//
// After boot, open  http://<ip-shown-on-serial>/  from a device on "Thermal".

#include <Wire.h>
#include <WiFi.h>
#include <WebServer.h>
#include <Adafruit_AMG88xx.h>

// ---- config ---------------------------------------------------------------
const char* SSID = "YOUR_WIFI_SSID";
const char* PASS = "YOUR_WIFI_PASSWORD";

#define SDA_PIN 21
#define SCL_PIN 22

// Onboard status LED on most DOIT DevKit V1 boards (active-low). Set to -1 to disable.
#define STATUS_LED 2

// ---- globals --------------------------------------------------------------
Adafruit_AMG88xx amg;
WebServer server(80);
bool sensorOK = false;

// ---- read helper ----------------------------------------------------------
// Returns true and fills out[64] (deg C) on success.
bool readPixels(float out[64]) {
  if (!sensorOK) return false;
  amg.readPixels(out);
  return true;
}

// ---- pages ----------------------------------------------------------------
const char INDEX_HTML[] PROGMEM = R"HTML(
<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AMG8833 Thermal</title>
<style>
  body{font-family:system-ui,Arial;background:#0d0d1a;color:#eee;margin:0;padding:16px;text-align:center}
  h1{color:#e94560;margin:6px 0}
  #grid{image-rendering:pixelated;border-radius:8px;background:#111;box-shadow:0 0 20px #000}
  .row{margin:10px 0;font-size:15px}
  b{color:#ffd700}
  .st{font-size:13px;color:#888}
</style></head><body>
<h1>AMG8833 Thermal</h1>
<canvas id="grid" width="256" height="256"></canvas>
<div class="row">min <b id="mn">-</b> &deg;C &nbsp; max <b id="mx">-</b> &deg;C &nbsp; avg <b id="av">-</b> &deg;C</div>
<div class="row st" id="st">connecting...</div>
<script>
const cv=document.getElementById('grid'),cx=cv.getContext('2d');
const W=256,S=W/8;
function color(t){ // 0..1 cold->hot
  const st=[[0,0,120],[0,120,255],[0,220,120],[255,220,0],[255,0,0]];
  const x=Math.max(0,Math.min(0.999,t))*(st.length-1), i=Math.floor(x), f=x-i;
  const a=st[i],b=st[i+1]||a;
  return `rgb(${a[0]+(b[0]-a[0])*f|0},${a[1]+(b[1]-a[1])*f|0},${a[2]+(b[2]-a[2])*f|0})`;
}
let lo=20,hi=40;
async function tick(){
  try{
    const r=await fetch('/pixels',{cache:'no-store'});
    if(!r.ok) throw 0;
    const j=await r.json();
    if(!j.ok){document.getElementById('st').textContent='sensor not found';return;}
    const p=j.p;
    let mn=1e9,mx=-1e9,sum=0;
    for(const v of p){if(v<mn)mn=v;if(v>mx)mx=v;sum+=v;}
    lo+=(mn-lo)*0.2; hi+=(mx-hi)*0.2; if(hi-lo<1)hi=lo+1;
    for(let i=0;i<64;i++){
      const x=(i%8)*S, y=Math.floor(i/8)*S;
      cx.fillStyle=color((p[i]-lo)/(hi-lo));
      cx.fillRect(x,y,S,S);
    }
    document.getElementById('mn').textContent=mn.toFixed(1);
    document.getElementById('mx').textContent=mx.toFixed(1);
    document.getElementById('av').textContent=(sum/64).toFixed(1);
    document.getElementById('st').textContent='live';
  }catch(e){document.getElementById('st').textContent='connection lost';}
  setTimeout(tick,150);
}
tick();
</script></body></html>
)HTML";

void handleRoot() {
  server.send_P(200, "text/html", INDEX_HTML);
}

void handlePixels() {
  float p[64];
  String out = "{\"ok\":";
  if (readPixels(p)) {
    out += "true,\"p\":[";
    for (int i = 0; i < 64; i++) {
      out += String(p[i], 2);
      if (i < 63) out += ",";
    }
    out += "]}";
  } else {
    out += "false}";
  }
  server.send(200, "application/json", out);
}

void handleStatus() {
  float p[64];
  bool ok = readPixels(p);
  String out = "{";
  out += "\"sensor\":";  out += ok ? "true" : "false";
  out += ",\"rssi\":";   out += String(WiFi.RSSI());
  out += ",\"ip\":\"";   out += WiFi.localIP().toString(); out += "\"";
  if (ok) {
    float mn = 1e9, mx = -1e9, sum = 0;
    for (int i = 0; i < 64; i++) { mn = min(mn, p[i]); mx = max(mx, p[i]); sum += p[i]; }
    out += ",\"min\":"; out += String(mn, 2);
    out += ",\"max\":"; out += String(mx, 2);
    out += ",\"avg\":"; out += String(sum / 64.0, 2);
  }
  out += "}";
  server.send(200, "application/json", out);
}

// ---- setup ----------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(400);
  Serial.println("\n=== AMG8833 -> Thermal (STA) ===");

  Wire.begin(SDA_PIN, SCL_PIN);

  // I2C scan so wiring problems are obvious on serial.
  Serial.print("I2C scan:");
  int found = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) { Serial.printf(" 0x%02X", a); found++; }
  }
  if (!found) Serial.print(" (none)");
  Serial.println();

  sensorOK = amg.begin();
  Serial.printf("AMG8833 begin(): %s\n", sensorOK ? "OK" : "FAILED");

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);          // keep latency low for streaming
  Serial.printf("Connecting to \"%s\" ...\n", SSID);
  WiFi.begin(SSID, PASS);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(300); Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("CONNECTED!");
    Serial.printf("  IP:    %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("  GW:    %s\n", WiFi.gatewayIP().toString().c_str());
    Serial.printf("  RSSI:  %d dBm\n", WiFi.RSSI());
    Serial.printf("  BSSID: %s\n", WiFi.BSSIDstr().c_str());
    Serial.printf("  Open:  http://%s/\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("WiFi connect FAILED (will keep retrying in loop)");
  }

  server.on("/", handleRoot);
  server.on("/pixels", handlePixels);
  server.on("/status", handleStatus);
  server.begin();
  Serial.println("HTTP server started on port 80");
}

// ---- loop -----------------------------------------------------------------
void loop() {
  // Keep the WiFi link up if the hotspot drops us.
  if (WiFi.status() != WL_CONNECTED) {
    static unsigned long lastTry = 0;
    if (millis() - lastTry > 5000) {
      lastTry = millis();
      Serial.printf("[net] status=%d, reconnecting...\n", (int)WiFi.status());
      WiFi.disconnect();
      WiFi.begin(SSID, PASS);
    }
  }
  server.handleClient();
  delay(2);
}
