// Guarana-Luz: anel de LEDs controlado pelo app Guaraná por Bluetooth LE e/ou Wi-Fi.
//
// Placa: ESP32 (qualquer DevKit). Placas > Gerenciador: "esp32" by Espressif.
// Biblioteca: "Adafruit NeoPixel" (Gerenciador de bibliotecas).
// LEDs: anel WS2812B / NeoPixel. Dados no GPIO 5 (resistor de 330 R em serie), 5 V e GND.
//       Capacitor de 1000 uF entre 5 V e GND perto do anel. Se o anel tiver > 16 LEDs, alimente com fonte 5 V externa,
//       nao pelo USB do ESP. Nivel logico 3,3 V costuma funcionar com WS2812B; se falhar, use um conversor de nivel.
//
// Protocolo (o mesmo por BLE e HTTP):
//   "S" + RRGGBBWWII (hex)  -> cor r,g,b, canal branco w (misturado nos 3 canais) e brilho geral i. Ex.: SFFFFFFFF99
//   "O"                     -> apaga
//   "P"                     -> ping, responde JSON
// BLE:  servico 6e400001-b5a3-f393-e0a9-e50e24dcca9e, escreva na caracteristica 6e400002-... ; resposta por notify em 6e400003-...
// HTTP: conecte no Wi-Fi "Guarana-Luz" (senha guarana123) e acesse http://192.168.4.1/cmd?c=SFF0000FF80
//
// Teste rapido no terminal:  curl "http://192.168.4.1/cmd?c=P"

#include <Adafruit_NeoPixel.h>

#define ENABLE_BLE 1
#define ENABLE_WIFI 1

#define LED_PIN 5
#define NUM_LEDS 16
#define LED_TYPE (NEO_GRB + NEO_KHZ800)

const char* DEVICE_NAME = "Guarana-Luz";
const char* AP_SSID = "Guarana-Luz";
const char* AP_PASS = "guarana123";
const char* FW = "guarana-luz 1.0";

#if ENABLE_WIFI
#include <WiFi.h>
#include <WebServer.h>
WebServer server(80);
#endif

#if ENABLE_BLE
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#define SERVICE_UUID "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define RX_UUID      "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
#define TX_UUID      "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
BLECharacteristic* txChar = nullptr;
#endif

Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, LED_TYPE);

static uint8_t hex2(const String& s, int i) {
  return (uint8_t) strtol(s.substring(i, i + 2).c_str(), nullptr, 16);
}

void fill(uint8_t r, uint8_t g, uint8_t b, uint8_t w, uint8_t bri) {
  // WS2812B nao tem canal branco: o "w" entra somado nos tres canais
  uint8_t rr = min(255, (int) r + w), gg = min(255, (int) g + w), bb = min(255, (int) b + w);
  strip.setBrightness(bri);
  for (int i = 0; i < NUM_LEDS; i++) strip.setPixelColor(i, strip.Color(rr, gg, bb));
  strip.show();
}

String handle(String cmd) {
  cmd.trim();
  cmd.replace(" ", "");   // aceita "S FF..." e "SFF..."
  if (cmd.length() == 0) return "{\"ok\":false,\"err\":\"vazio\"}";
  char op = toupper(cmd.charAt(0));
  if (op == 'P') return String("{\"ok\":true,\"fw\":\"") + FW + "\",\"leds\":" + NUM_LEDS + "}";
  if (op == 'O') { strip.clear(); strip.show(); return "{\"ok\":true}"; }
  if (op == 'S' && cmd.length() >= 11) {
    fill(hex2(cmd, 1), hex2(cmd, 3), hex2(cmd, 5), hex2(cmd, 7), hex2(cmd, 9));
    return "{\"ok\":true}";
  }
  return "{\"ok\":false,\"err\":\"cmd\"}";
}

#if ENABLE_BLE
class RxCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    String v = c->getValue().c_str();
    String reply = handle(v);
    if (txChar) { txChar->setValue((uint8_t*) reply.c_str(), reply.length()); txChar->notify(); }
  }
};
class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer*) override {}
  void onDisconnect(BLEServer*) override { BLEDevice::startAdvertising(); }
};
#endif

void blink(uint8_t r, uint8_t g, uint8_t b) {
  fill(r, g, b, 0, 60); delay(150); strip.clear(); strip.show(); delay(100);
}

void setup() {
  Serial.begin(115200);
  strip.begin();
  strip.clear();
  strip.show();

#if ENABLE_WIFI
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASS);
  server.on("/cmd", []() { server.send(200, "application/json", handle(server.arg("c"))); });
  server.on("/", []() { server.send(200, "text/plain", String(FW) + "\nuse /cmd?c=P  /cmd?c=O  /cmd?c=SRRGGBBWWII\n"); });
  server.begin();
  Serial.print("Wi-Fi AP "); Serial.print(AP_SSID); Serial.print(" em "); Serial.println(WiFi.softAPIP());
#endif

#if ENABLE_BLE
  BLEDevice::init(DEVICE_NAME);
  BLEServer* srv = BLEDevice::createServer();
  srv->setCallbacks(new ServerCallbacks());
  BLEService* svc = srv->createService(SERVICE_UUID);
  txChar = svc->createCharacteristic(TX_UUID, BLECharacteristic::PROPERTY_NOTIFY);
  txChar->addDescriptor(new BLE2902());
  BLECharacteristic* rx = svc->createCharacteristic(RX_UUID, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  rx->setCallbacks(new RxCallbacks());
  svc->start();
  BLEAdvertising* adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(SERVICE_UUID);
  adv->setScanResponse(true);
  BLEDevice::startAdvertising();
  Serial.print("BLE anunciando como "); Serial.println(DEVICE_NAME);
#endif

  blink(0, 255, 0); blink(0, 255, 0);   // pronto: pisca verde duas vezes
}

void loop() {
#if ENABLE_WIFI
  server.handleClient();
#endif
  if (Serial.available()) {              // tambem aceita comandos pelo monitor serial, para testar sem app
    String line = Serial.readStringUntil('\n');
    Serial.println(handle(line));
  }
  delay(2);
}
