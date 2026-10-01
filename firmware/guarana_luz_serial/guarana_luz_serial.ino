// Guarana-Luz Serial 2.1: interpretador de comandos pela USB para ESP32 / ESP32-CAM.
//
// Nada de rotina, cor ou pino fixo aqui: o app manda tudo. A unica coisa presa ao hardware e o mapa de pinos
// da camera da placa (AI-Thinker ESP32-CAM), que so entra se HAS_CAMERA for 1.
//
// Comandos (uma linha, terminada em \n; resposta sempre uma linha JSON):
//   P                                   ping: devolve firmware e configuracao atual
//   CFG mode=ws pin=13 n=12 type=GRB flash=4      configura e grava na flash (sobrevive ao reboot)
//   CFG mode=pwm r=12 g=13 b=14 w=15 flash=4      LEDs comuns por PWM em vez de fita enderecavel
//   CFG mode=pwm r=27,33,17 g=-1 b=5,32,2 w=16,26,14 flash=-1   varios LEDs por cor: lista de pinos separada por virgula (ate 4)
//   CFG ir=14                                     pino do LED infravermelho (-1 desliga)
//   S RRGGBBWWII  (ou SRRGGBBWWII)      cor de todos os LEDs + brilho geral (hex)
//   L i RRGGBB                          cor de um LED (sem mostrar)      X   mostra o que foi montado com L
//   B ii                                brilho geral (hex)
//   FL ii                               LED de flash da placa (branco forte, GPIO 4 na ESP32-CAM), 0..FF
//   IR ii                               LED infravermelho (PWM no pino ir= do CFG), 0..FF; a camera do tablet precisa enxergar IR
//   O                                   apaga tudo
//   D                                   diagnostico: pinos de cada grupo e o duty PWM atual de cada um
//   G pin v                             escreve 0/1 direto no pino, sem PWM (teste de ligacao)
//   T                                   teste: acende vermelho, verde, azul e branco, meio segundo cada
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

struct Grupo { int pin[4]; int ch[4]; int n; };   // antes de tudo: o Arduino gera prototipos que usam o tipo

const char* FW = "guarana-luz-serial 2.1";
Preferences prefs;

// ---- configuracao (lida da flash, alterada por CFG) ----
struct Cfg {
  String mode = "pwm";    // "ws" (fita enderecavel) ou "pwm"
  int pin = 13, n = 12;   // fita
  String type = "GRB";
  String r = "27,33,17", g = "-1", b = "5,32,2", w = "16,26,14";   // pwm: pinos de cada cor (lista)
  int flash = -1;         // LED de flash da placa (4 na ESP32-CAM; -1 desliga)
  int ir = -1;            // LED infravermelho por PWM (-1 desliga)
  String res = "VGA";
  int q = 12;
} cfg;

Adafruit_NeoPixel* strip = nullptr;
uint8_t curBri = 255;

void loadCfg() {
  prefs.begin("luz", true);
  cfg.mode = prefs.getString("mode", cfg.mode); cfg.pin = prefs.getInt("pin", cfg.pin); cfg.n = prefs.getInt("n", cfg.n);
  cfg.type = prefs.getString("type", cfg.type); cfg.r = prefs.getString("rs", cfg.r); cfg.g = prefs.getString("gs", cfg.g);
  cfg.b = prefs.getString("bs", cfg.b); cfg.w = prefs.getString("ws", cfg.w); cfg.flash = prefs.getInt("flash", cfg.flash);
  cfg.ir = prefs.getInt("ir", cfg.ir);
  cfg.res = prefs.getString("res", cfg.res); cfg.q = prefs.getInt("q", cfg.q);
  prefs.end();
}
void saveCfg() {
  prefs.begin("luz", false);
  prefs.putString("mode", cfg.mode); prefs.putInt("pin", cfg.pin); prefs.putInt("n", cfg.n); prefs.putString("type", cfg.type);
  prefs.putString("rs", cfg.r); prefs.putString("gs", cfg.g); prefs.putString("bs", cfg.b); prefs.putString("ws", cfg.w); prefs.putInt("flash", cfg.flash);
  prefs.putInt("ir", cfg.ir);
  prefs.putString("res", cfg.res); prefs.putInt("q", cfg.q);
  prefs.end();
}

// ---- PWM compativel com core 2.x e 3.x ----
void pwmSetup(int pin, int ch) {
  if (pin < 0) return;
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcDetach(pin); ledcAttach(pin, 5000, 8);
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

// ---- grupos de LEDs por cor: ate 4 pinos cada, canal LEDC proprio por pino ----
Grupo gR, gG, gB, gW;
int proxCanal = 7;   // 4 = flash, 6 = IR; core 2.x usa canais 7..15 para os grupos

void montaGrupo(Grupo& g, const String& lista) {
  g.n = 0;
  int a = 0;
  while (a <= (int) lista.length() && g.n < 4) {
    int e = lista.indexOf(',', a); if (e < 0) e = lista.length();
    int pin = lista.substring(a, e).toInt();
    if (lista.substring(a, e).length() && pin >= 0) { g.pin[g.n] = pin; g.ch[g.n] = proxCanal++; pwmSetup(pin, g.ch[g.n]); g.n++; }
    a = e + 1;
  }
}
void escreveGrupo(const Grupo& g, uint8_t v) { for (int i = 0; i < g.n; i++) pwmWrite(g.pin[i], g.ch[i], v); }
String listaJson(const String& l) { return "[" + (l == "-1" ? String("") : l) + "]"; }

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
    proxCanal = 7;
    montaGrupo(gR, cfg.r); montaGrupo(gG, cfg.g); montaGrupo(gB, cfg.b); montaGrupo(gW, cfg.w);
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
    escreveGrupo(gR, r * bri / 255); escreveGrupo(gG, g * bri / 255); escreveGrupo(gB, b * bri / 255); escreveGrupo(gW, w * bri / 255);
  }
}

void allOff() {
  if (strip) { strip->clear(); strip->show(); }
  if (cfg.mode != "ws") { escreveGrupo(gR, 0); escreveGrupo(gG, 0); escreveGrupo(gB, 0); escreveGrupo(gW, 0); }
  pwmWrite(cfg.flash, 4, 0); pwmWrite(cfg.ir, 6, 0);
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
             ",\"type\":\"" + cfg.type + "\",\"r\":" + listaJson(cfg.r) + ",\"g\":" + listaJson(cfg.g) + ",\"b\":" + listaJson(cfg.b) +
             ",\"w\":" + listaJson(cfg.w) + ",\"flash\":" + cfg.flash + ",\"ir\":" + cfg.ir + ",\"cam\":";
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
  if (cmd == "D") {
    String r = "{\"ok\":true";
    const Grupo* gs[4] = {&gR, &gG, &gB, &gW}; const char* nm[4] = {"r", "g", "b", "w"};
    for (int k = 0; k < 4; k++) {
      r += ",\"" + String(nm[k]) + "\":[";
      for (int i = 0; i < gs[k]->n; i++) {
        if (i) r += ",";
#if ESP_ARDUINO_VERSION_MAJOR >= 3
        r += "[" + String(gs[k]->pin[i]) + "," + String(ledcRead(gs[k]->pin[i])) + "]";
#else
        r += "[" + String(gs[k]->pin[i]) + "," + String(ledcRead(gs[k]->ch[i])) + "]";
#endif
      }
      r += "]";
    }
    return r + "}";
  }
  if (cmd == "G") {
    int sp2 = rest.indexOf(' ');
    if (sp2 < 0) return "{\"ok\":false,\"err\":\"G pin v\"}";
    int pin = rest.substring(0, sp2).toInt(), v = rest.substring(sp2 + 1).toInt();
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcDetach(pin);
#endif
    pinMode(pin, OUTPUT); digitalWrite(pin, v ? HIGH : LOW);
    return "{\"ok\":true,\"pin\":" + String(pin) + ",\"v\":" + String(digitalRead(pin)) + "}";
  }
  if (cmd == "T") {
    const uint8_t seq[4][4] = {{255, 0, 0, 0}, {0, 255, 0, 0}, {0, 0, 255, 0}, {0, 0, 0, 255}};
    for (auto& c : seq) { fillAll(c[0], c[1], c[2], c[3], 255); delay(500); }
    allOff(); return "{\"ok\":true}";
  }
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
    cfg.type = kv(l, "type", cfg.type); cfg.r = kv(l, "r", cfg.r); cfg.g = kv(l, "g", cfg.g);
    cfg.b = kv(l, "b", cfg.b); cfg.w = kv(l, "w", cfg.w); cfg.flash = kv(l, "flash", String(cfg.flash)).toInt();
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
