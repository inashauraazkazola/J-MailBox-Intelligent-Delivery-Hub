#include <WiFi.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include "esp_camera.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

// ===================== WIFI =====================
static const char* WIFI_SSID     = "YOUR_WIFI_SSID";
static const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ===================== HTTP =====================
static const char* HTTP_HOST = "YOUR_DOMAIN_OR_VPS_IP";
static const int   HTTP_PORT = 80;

// ===================== MQTT =====================
static const char* MQTT_HOST     = "YOUR_MQTT_BROKER_IP";
static const int   MQTT_PORT     = 1883;
static const char* MQTT_USER     = "YOUR_MQTT_USERNAME";
static const char* MQTT_PASS     = "YOUR_MQTT_PASSWORD";

static const char* TOPIC_SUB     = "alat/status";
static const char* TOPIC_PUB     = "alat/cam_status";

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

// ===================== CAMERA PINS (AI Thinker ESP32-CAM) =====================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ===================== HELPERS =====================
static String sanitizeResi(const String& in) {
  String r;
  r.reserve(in.length());
  for (size_t i = 0; i < in.length(); i++) {
    char c = in[i];
    if ((c >= '0' && c <= '9') ||
        (c >= 'A' && c <= 'Z') ||
        (c >= 'a' && c <= 'z') ||
        c == '-' || c == '_' || c == '.') {
      r += c;
    }
  }
  if (r.length() > 64) r = r.substring(0, 64);
  return r;
}

static void publishStatus(const String& resi, bool ok, int code, size_t bytes, const String& msg) {
  StaticJsonDocument<256> doc;
  doc["type"] = "cam_upload";
  doc["resi"] = resi;
  doc["ok"] = ok;
  doc["code"] = code;
  doc["bytes"] = (uint32_t)bytes;
  doc["message"] = msg;

  char out[320];
  size_t n = serializeJson(doc, out, sizeof(out));
  mqtt.publish(TOPIC_PUB, out, n);
}

static int readHttpStatus(WiFiClient& client) {
  // status line: HTTP/1.1 200 OK
  String line = client.readStringUntil('\n');
  line.trim();
  if (!line.startsWith("HTTP/")) return -1;
  int sp1 = line.indexOf(' ');
  if (sp1 < 0) return -1;
  int sp2 = line.indexOf(' ', sp1 + 1);
  String codeStr = (sp2 > 0) ? line.substring(sp1 + 1, sp2) : line.substring(sp1 + 1);
  return codeStr.toInt();
}

// ===================== WIFI =====================
void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("Connecting WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(" OK");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println(" FAILED");
  }
}

// ===================== CAMERA =====================
bool initCamera() {
  // Reduce brownout resets on ESP32-CAM
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;

  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Settings stabil untuk upload (nggak kebesaran)
  config.frame_size   = FRAMESIZE_VGA;  // 640x480
  config.jpeg_quality = 12;             // 10-15 OK
  config.fb_count     = 1;

  esp_err_t err = esp_camera_init(&config);
  return (err == ESP_OK);
}

// ===================== HTTP UPLOAD (multipart) =====================
bool uploadPhotoHTTP(const String& resi, int& httpCode, size_t& bytesSent) {
  httpCode = -1;
  bytesSent = 0;

  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb || fb->len == 0) {
    if (fb) esp_camera_fb_return(fb);
    return false;
  }

  WiFiClient client;
  client.setTimeout(20);

  if (!client.connect(HTTP_HOST, HTTP_PORT)) {
    Serial.println("HTTP connect failed");
    esp_camera_fb_return(fb);
    return false;
  }

  const char* boundary = "----ESP32CAMBOUNDARY";
  String path = "/upload_wajah/" + resi;

  String bodyStart =
    String("--") + boundary + "\r\n" +
    "Content-Disposition: form-data; name=\"image\"; filename=\"cam.jpg\"\r\n" +
    "Content-Type: image/jpeg\r\n\r\n";

  String bodyEnd = "\r\n--" + String(boundary) + "--\r\n";

  uint32_t contentLength = bodyStart.length() + fb->len + bodyEnd.length();

  client.print(String("POST ") + path + " HTTP/1.1\r\n");
  client.print(String("Host: ") + HTTP_HOST + "\r\n");
  client.print("User-Agent: ESP32-CAM\r\n");
  client.print(String("Content-Type: multipart/form-data; boundary=") + boundary + "\r\n");
  client.print(String("Content-Length: ") + contentLength + "\r\n");
  client.print("Connection: close\r\n\r\n");

  client.print(bodyStart);

  const uint8_t* p = fb->buf;
  size_t remaining = fb->len;
  const size_t chunk = 1024;

  while (remaining > 0) {
    size_t toWrite = remaining > chunk ? chunk : remaining;
    size_t written = client.write(p, toWrite);
    if (written == 0) break;
    p += written;
    remaining -= written;
  }

  client.print(bodyEnd);

  bytesSent = fb->len;

  httpCode = readHttpStatus(client);
  Serial.print("HTTP code: ");
  Serial.println(httpCode);

  // drain a bit
  unsigned long t0 = millis();
  while (client.connected() && millis() - t0 < 2000) {
    while (client.available()) client.read();
    delay(10);
  }
  client.stop();

  esp_camera_fb_return(fb);

  return (httpCode >= 200 && httpCode < 300);
}

// ===================== MQTT =====================
void ensureMQTT() {
  if (mqtt.connected()) return;

  mqtt.setServer(MQTT_HOST, MQTT_PORT);

  String clientId = "esp32cam-http-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  Serial.print("MQTT connecting as ");
  Serial.println(clientId);

  if (mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASS)) {
    mqtt.subscribe(TOPIC_SUB);
    Serial.println("MQTT connected & subscribed");

    StaticJsonDocument<192> doc;
    doc["type"] = "cam_online";
    doc["ip"] = WiFi.localIP().toString();
    char out[220];
    size_t n = serializeJson(doc, out, sizeof(out));
    mqtt.publish(TOPIC_PUB, out, n);
  } else {
    Serial.print("MQTT FAIL rc=");
    Serial.println(mqtt.state());
  }
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  String t = String(topic);

  String s;
  s.reserve(length + 1);
  for (unsigned int i = 0; i < length; i++) s += (char)payload[i];

  Serial.print("MQTT RX ");
  Serial.print(t);
  Serial.print(" => ");
  Serial.println(s);

  StaticJsonDocument<256> doc;
  if (deserializeJson(doc, s) != DeserializationError::Ok) return;

  const char* ev = nullptr;
  if (doc.containsKey("type")) ev = doc["type"].as<const char*>();
  if (!ev && doc.containsKey("event")) ev = doc["event"].as<const char*>();
  if (!ev) return;

  if (String(ev) != "resi_scanned") return;

  const char* r = doc["resi"].as<const char*>();
  if (!r) return;

  String resi = sanitizeResi(String(r));
  if (resi.length() < 3) return;

  Serial.print("Trigger upload for resi=");
  Serial.println(resi);

  int httpCode = -1;
  size_t bytes = 0;
  bool ok = uploadPhotoHTTP(resi, httpCode, bytes);

  publishStatus(resi, ok, httpCode, bytes, ok ? "uploaded_http" : "upload_failed_http");
}

// ===================== SETUP / LOOP =====================
void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println("=== ESP32-CAM HTTP UPLOADER START ===");

  if (!initCamera()) {
    Serial.println("Camera init FAILED (check board/pins/power)");
    delay(2000);
  } else {
    Serial.println("Camera init OK");
  }

  ensureWiFi();

  mqtt.setCallback(onMqttMessage);
  mqtt.setBufferSize(1024);
}

void loop() {
  ensureWiFi();
  ensureMQTT();
  mqtt.loop();
  delay(10);
}
