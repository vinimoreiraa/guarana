// Guarana-Luz Serial 2.0: interpretador de comandos pela USB para ESP32 / ESP32-CAM.
//
// Nada de rotina, cor ou pino fixo aqui: o app manda tudo. A unica coisa presa ao hardware e o mapa de pinos
// da camera da placa (AI-Thinker ESP32-CAM), que so entra se HAS_CAMERA for 1.
//
// Comandos (uma linha, terminada em \n; resposta sempre uma linha JSON):
//   P                                   ping: devolve firmware e configuracao atual
//   CFG mode=ws pin=13 n=12 type=GRB flash=4      configura e grava na flash (sobrevive ao reboot)
//   CFG mode=pwm r=12 g=13 b=14 w=15 flash=4      LEDs comuns por PWM em vez de fita enderecavel
//   CFG ir=14                                     pino do LED infravermelho (-1 desliga)
//   S RRGGBBWWII  (ou SRRGGBBWWII)      cor de todos os LEDs + brilho geral (hex)
//   L i RRGGBB                          cor de um LED (sem mostrar)      X   mostra o que foi montado com L
//   B ii                                brilho geral (hex)
//   FL ii                               LED de flash da placa (branco forte, GPIO 4 na ESP32-CAM), 0..FF
//   IR ii                               LED infravermelho (PWM no pino ir= do CFG), 0..FF; a camera do tablet precisa enxergar IR
//   O                                   apaga tudo
//   CAM res=VGA q=12                    resolucao (QVGA, VGA, SVGA, XGA) e qualidade JPEG (menor = melhor)
//   F                                   captura um quadro: responde "FRAME <bytes>\n" seguido do JPEG cru
//
// Serial a 115200 8N1. Um quadro VGA (~40 KB) leva uns 3,5 s nessa velocidade; mude SERIAL_BAUD nos dois lados se precisar.
//
// Bibliotecas: Adafruit NeoPixel. Placa: "AI Thinker ESP32-CAM" (ou ESP32 Dev Module com HAS_CAMERA 0).
// Pinos livres na ESP32-CAM sem cartao SD e com a camera desligada: 13, 14, 15, 2, 16. Evite 12 (strapping) e 4 (e o flash).

#include <Adafruit_NeoPixel.h>
#include <Preferences.h>

#define SERIAL_BAUD 115200
#ifndef HAS_CAMERA
#define HAS_CAMERA 0   // a foto e da camera do tablet; a camera da ESP32-CAM fica desligada (libera RAM e pinos). 1 para ativar o comando F.
#endif

#if HAS_CAMERA
#include "esp_camera.h"
// AI-Thinker ESP32-CAM
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22
bool camReady = false;
#endif

const char* FW = "guarana-luz-serial 2.0";
Preferences prefs;

// ---- configuracao (lida da flash, alterada por CFG) ----
struct Cfg {
  String mode = "ws";     // "ws" (fita enderecavel) ou "pwm"
  int pin = 13, n = 12;   // fita
  String type = "GRB";
  int r = 12, g = 13, b = 14, w = 15;   // pwm
  int flash = 4;          // LED de flash da placa (-1 desliga)
  int ir = -1;            // LED infravermelho por PWM (-1 desliga)
  String res = "VGA";
  int q = 12;
} cfg;

Adafruit_NeoPixel* strip = nullptr;
uint8_t curBri = 255;

void loadCfg() {
  prefs.begin("luz", true);
  cfg.mode = prefs.getString("mode", cfg.mode); cfg.pin = prefs.getInt("pin", cfg.pin); cfg.n = prefs.getInt("n", cfg.n);
  cfg.type = prefs.getString("type", cfg.type); cfg.r = prefs.getInt("r", cfg.r); cfg.g = prefs.getInt("g", cfg.g);
  cfg.b = prefs.getInt("b", cfg.b); cfg.w = prefs.getInt("w", cfg.w); cfg.flash = prefs.getInt("flash", cfg.flash);
  cfg.ir = prefs.getInt("ir", cfg.ir);
  cfg.res = prefs.getString("res", cfg.res); cfg.q = prefs.getInt("q", cfg.q);
  prefs.end();
}
void saveCfg() {
  prefs.begin("luz", false);
  prefs.putString("mode", cfg.mode); prefs.putInt("pin", cfg.pin); prefs.putInt("n", cfg.n); prefs.putString("type", cfg.type);
  prefs.putInt("r", cfg.r); prefs.putInt("g", cfg.g); prefs.putInt("b", cfg.b); prefs.putInt("w", cfg.w); prefs.putInt("flash", cfg.flash);
  prefs.putInt("ir", cfg.ir);
  prefs.putString("res", cfg.res); prefs.putInt("q", cfg.q);
  prefs.end();
}

// ---- PWM compativel com core 2.x e 3.x ----
void pwmSetup(int pin, int ch) {
  if (pin < 0) return;
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(pin, 5000, 8);
#else
  ledcSetup(ch, 5000, 8); ledcAttachPin(pin, ch);
#endif
}
void pwmWrite(int pin, int ch, uint8_t v) {
  if (pin < 0) return;
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(pin, v);
#else
  ledcWrite(ch, v);
#endif
}

neoPixelType typeFlags() {
  String t = cfg.type; t.toUpperCase();
  neoPixelType f = NEO_GRB;
  if (t == "RGB") f = NEO_RGB; else if (t == "GRBW") f = NEO_GRBW; else if (t == "RGBW") f = NEO_RGBW; else if (t == "BRG") f = NEO_BRG;
  return f + NEO_KHZ800;
}

void applyHardware() {
  if (strip) { strip->clear(); strip->show(); delete strip; strip = nullptr; }
  if (cfg.mode == "ws") {
    strip = new Adafruit_NeoPixel(cfg.n, cfg.pin, typeFlags());
    strip->begin(); strip->setBrightness(curBri); strip->clear(); strip->show();
  } else {
    pwmSetup(cfg.r, 0); pwmSetup(cfg.g, 1); pwmSetup(cfg.b, 2); pwmSetup(cfg.w, 3);
  }
  pwmSetup(cfg.flash, 4); pwmWrite(cfg.flash, 4, 0);
  pwmSetup(cfg.ir, 6); pwmWrite(cfg.ir, 6, 0);
}

bool hasW() { String t = cfg.type; t.toUpperCase(); return t.endsWith("W"); }

void fillAll(uint8_t r, uint8_t g, uint8_t b, uint8_t w, uint8_t bri) {
  curBri = bri;
  if (cfg.mode == "ws" && strip) {
    strip->setBrightness(bri);
    for (int i = 0; i < cfg.n; i++) {
      if (hasW()) strip->setPixelColor(i, strip->Color(r, g, b, w));
      else strip->setPixelColor(i, strip->Color(min(255, r + w), min(255, g + w), min(255, b + w)));
    }
    strip->show();
  } else {
    pwmWrite(cfg.r, 0, r * bri / 255); pwmWrite(cfg.g, 1, g * bri / 255); pwmWrite(cfg.b, 2, b * bri / 255); pwmWrite(cfg.w, 3, w * bri / 255);
  }
}

void allOff() {
  if (strip) { strip->clear(); strip->show(); }
  pwmWrite(cfg.r, 0, 0); pwmWrite(cfg.g, 1, 0); pwmWrite(cfg.b, 2, 0); pwmWrite(cfg.w, 3, 0); pwmWrite(cfg.flash, 4, 0); pwmWrite(cfg.ir, 6, 0);
}

static uint8_t hex2(const String& s, int i) { return (uint8_t) strtol(s.substring(i, i + 2).c_str(), nullptr, 16); }

String kv(const String& line, const String& key, const String& def) {
  int i = line.indexOf(" " + key + "=");
  if (i < 0) return def;
  int a = i + key.length() + 2, e = line.indexOf(' ', a);
  return e < 0 ? line.substring(a) : line.substring(a, e);
}

String status() {
  String s = "{\"ok\":true,\"fw\":\"" + String(FW) + "\",\"mode\":\"" + cfg.mode + "\",\"pin\":" + cfg.pin + ",\"n\":" + cfg.n +
             ",\"type\":\"" + cfg.type + "\",\"flash\":" + cfg.flash + ",\"ir\":" + cfg.ir + ",\"cam\":";
#if HAS_CAMERA
  s += camReady ? "true" : "false";
#else
  s += "false";
#endif
  s += ",\"res\":\"" + cfg.res + "\",\"q\":" + cfg.q + "}";
  return s;
}

#if HAS_CAMERA
framesize_t frameSize() {
  String r = cfg.res; r.toUpperCase();
  if (r == "QVGA") return FRAMESIZE_QVGA; if (r == "SVGA") return FRAMESIZE_SVGA; if (r == "XGA") return FRAMESIZE_XGA;
  if (r == "HD") return FRAMESIZE_HD; if (r == "SXGA") return FRAMESIZE_SXGA; if (r == "UXGA") return FRAMESIZE_UXGA;
  return FRAMESIZE_VGA;
}
bool camInit() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_5; c.ledc_timer = LEDC_TIMER_1;   // nao conflitar com o PWM dos LEDs
  c.pin_d0 = Y2_GPIO_NUM; c.pin_d1 = Y3_GPIO_NUM; c.pin_d2 = Y4_GPIO_NUM; c.pin_d3 = Y5_GPIO_NUM; c.pin_d4 = Y6_GPIO_NUM;
  c.pin_d5 = Y7_GPIO_NUM; c.pin_d6 = Y8_GPIO_NUM; c.pin_d7 = Y9_GPIO_NUM; c.pin_xclk = XCLK_GPIO_NUM; c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM; c.pin_sccb_sda = SIOD_GPIO_NUM; c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM; c.pin_reset = RESET_GPIO_NUM; c.xclk_freq_hz = 20000000; c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = frameSize(); c.jpeg_quality = cfg.q; c.fb_count = psramFound() ? 2 : 1;
  c.grab_mode = CAMERA_GRAB_LATEST; c.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  if (camReady) esp_camera_deinit();
  camReady = (esp_camera_init(&c) == ESP_OK);
  return camReady;
}
void sendFrame() {
  if (!camReady) { Serial.println("{\"ok\":false,\"err\":\"sem camera\"}"); return; }
  camera_fb_t* fb = esp_camera_fb_get();          // descarta um quadro antigo do buffer
  if (fb) { esp_camera_fb_return(fb); fb = esp_camera_fb_get(); }
  if (!fb) { Serial.println("{\"ok\":false,\"err\":\"captura\"}"); return; }
  Serial.printf("FRAME %u\n", (unsigned) fb->len);
  Serial.write(fb->buf, fb->len);
  Serial.flush();
  esp_camera_fb_return(fb);
}
#endif

String handle(String line) {
  line.trim();
  if (line.length() == 0) return "{\"ok\":false,\"err\":\"vazio\"}";
  String up = line; up.toUpperCase();
  int sp = up.indexOf(' ');
  String cmd = sp < 0 ? up : up.substring(0, sp);
  String rest = sp < 0 ? "" : line.substring(sp + 1);
  rest.trim();

  if (cmd == "P") return status();
  if (cmd == "O") { allOff(); return "{\"ok\":true}"; }
  if (cmd == "X") { if (strip) strip->show(); return "{\"ok\":true}"; }
  if (cmd == "B" && rest.length() >= 2) { curBri = hex2(rest, 0); if (strip) { strip->setBrightness(curBri); strip->show(); } return "{\"ok\":true}"; }
  if (cmd == "FL" && rest.length() >= 2) { pwmWrite(cfg.flash, 4, hex2(rest, 0)); return "{\"ok\":true}"; }
  if (cmd == "IR" && rest.length() >= 2) { pwmWrite(cfg.ir, 6, hex2(rest, 0)); return "{\"ok\":true}"; }
  if (cmd.startsWith("S")) {
    String h = cmd.length() > 1 ? cmd.substring(1) : rest;   // aceita "SFF..." e "S FF..."
    h.replace(" ", "");
    if (h.length() < 10) return "{\"ok\":false,\"err\":\"S RRGGBBWWII\"}";
    fillAll(hex2(h, 0), hex2(h, 2), hex2(h, 4), hex2(h, 6), hex2(h, 8));
    return "{\"ok\":true}";
  }
  if (cmd == "L") {
    int sp2 = rest.indexOf(' ');
    if (sp2 < 0 || !strip) return "{\"ok\":false,\"err\":\"L i RRGGBB\"}";
    int i = rest.substring(0, sp2).toInt(); String h = rest.substring(sp2 + 1); h.trim();
    if (i < 0 || i >= cfg.n || h.length() < 6) return "{\"ok\":false,\"err\":\"indice\"}";
    strip->setPixelColor(i, strip->Color(hex2(h, 0), hex2(h, 2), hex2(h, 4)));
    return "{\"ok\":true}";
  }
  if (cmd == "CFG") {
    String l = " " + rest;
    cfg.mode = kv(l, "mode", cfg.mode); cfg.pin = kv(l, "pin", String(cfg.pin)).toInt(); cfg.n = kv(l, "n", String(cfg.n)).toInt();
    cfg.type = kv(l, "type", cfg.type); cfg.r = kv(l, "r", String(cfg.r)).toInt(); cfg.g = kv(l, "g", String(cfg.g)).toInt();
    cfg.b = kv(l, "b", String(cfg.b)).toInt(); cfg.w = kv(l, "w", String(cfg.w)).toInt(); cfg.flash = kv(l, "flash", String(cfg.flash)).toInt();
    cfg.ir = kv(l, "ir", String(cfg.ir)).toInt();
    saveCfg(); applyHardware();
    return status();
  }
#if HAS_CAMERA
  if (cmd == "CAM") {
    String l = " " + rest;
    cfg.res = kv(l, "res", cfg.res); cfg.q = kv(l, "q", String(cfg.q)).toInt();
    saveCfg(); camInit();
    return status();
  }
  if (cmd == "F") { sendFrame(); return ""; }
#endif
  return "{\"ok\":false,\"err\":\"cmd\"}";
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  Serial.setTimeout(50);
  loadCfg();
  applyHardware();
#if HAS_CAMERA
  camInit();
#endif
  Serial.println(status());   // o app le esta linha depois do reset
}

String buf;
void loop() {
  while (Serial.available()) {
    char c = (char) Serial.read();
    if (c == '\n' || c == '\r') {
      if (buf.length()) { String r = handle(buf); if (r.length()) Serial.println(r); }
      buf = "";
    } else if (buf.length() < 200) {
      buf += c;
    }
  }
  delay(1);
}
