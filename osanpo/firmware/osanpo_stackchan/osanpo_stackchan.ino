// お散歩Claude — StackChan(M5Stack CoreS3相当) 側スケッチ 【実機未検証の草案】
//
// 動き: Wi-Fi接続 → 撮影 → JPEGにして受信サーバへPOST → コメントを取りに行って画面に表示 → 待つ → 繰り返し
//
// 必要なもの (Arduino IDE / PlatformIO):
//   - ボード: M5Stack (esp32) ボードマネージャ → "M5CoreS3"
//   - ライブラリ: M5CoreS3 (M5Unified/M5GFXが一緒に入る)
//   - 下の SSID / PASS / SERVER / TOKEN を自分の環境に書き換える
//
// 注意: 公式StackChanの出荷時ファームは消える。戻したくなった時のためにM5Burnerの存在は覚えておくこと。

#include <M5CoreS3.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "esp_camera.h"   // frame2jpg()

const char* SSID   = "YOUR_WIFI_SSID";
const char* PASS   = "YOUR_WIFI_PASSWORD";
// 家の中でのテスト: "http://192.168.0.10:5072"
// Cloudflare Tunnel経由:  "https://osanpo.ortiz-ai.partners"
const char* SERVER = "http://192.168.0.10:5072";
const char* TOKEN  = "YOUR_SECRET_TOKEN";   // server.py の OSANPO_TOKEN と同じ文字列
const uint32_t INTERVAL_MS = 5UL * 60UL * 1000UL;  // 5分ごと
const int JPEG_QUALITY = 80;

void say(const char* msg) {
  CoreS3.Display.fillScreen(BLACK);
  CoreS3.Display.setCursor(0, 0);
  CoreS3.Display.println(msg);
  Serial.println(msg);
}

WiFiClientSecure tls;
WiFiClient plain;

// http:// と https:// を自動で使い分ける。
// https は実験中は証明書検証なし(setInsecure)。動いたら tls.setCACert(...) に置き換えること。
bool beginHttp(HTTPClient& http, const String& url) {
  if (url.startsWith("https://")) {
    tls.setInsecure();
    return http.begin(tls, url);
  }
  return http.begin(plain, url);
}

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  say("Wi-Fi...");
  WiFi.begin(SSID, PASS);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(500);
  say(WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString().c_str() : "Wi-Fi NG");
}

bool shootAndPost() {
  if (!CoreS3.Camera.get()) { say("camera NG"); return false; }
  uint8_t* jpg = nullptr;
  size_t len = 0;
  bool ok = frame2jpg(CoreS3.Camera.fb, JPEG_QUALITY, &jpg, &len);  // GC0308はRGB565出力なのでここでJPEG化
  CoreS3.Camera.free();
  if (!ok) { say("jpeg NG"); return false; }

  HTTPClient http;
  beginHttp(http, String(SERVER) + "/upload");
  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("X-Osanpo-Token", TOKEN);
  int code = http.POST(jpg, len);
  http.end();
  free(jpg);
  Serial.printf("POST %u bytes -> %d\n", (unsigned)len, code);
  return code == 200;
}

void fetchAndShowComment() {
  HTTPClient http;
  beginHttp(http, String(SERVER) + "/latest.txt");
  http.addHeader("X-Osanpo-Token", TOKEN);
  int code = http.GET();
  if (code == 200) {
    String text = http.getString();
    say(text.c_str());
    // TODO: フェーズ3でここをTTS再生に差し替える (AIｽﾀｯｸﾁｬﾝ2の喋る部分を流用予定)
  }
  http.end();
}

void setup() {
  auto cfg = M5.config();
  CoreS3.begin(cfg);
  CoreS3.Display.setTextSize(2);
  CoreS3.Display.setTextWrap(true);
  Serial.begin(115200);
  say("osanpo claude");
  connectWifi();
  if (!CoreS3.Camera.begin()) say("camera init NG");
}

void loop() {
  connectWifi();
  if (shootAndPost()) {
    delay(20000);            // claude が見終わるのを待つ（雑に20秒）
    fetchAndShowComment();
  }
  delay(INTERVAL_MS);        // TODO: 電池を持たせたければ light sleep に置き換える
}
