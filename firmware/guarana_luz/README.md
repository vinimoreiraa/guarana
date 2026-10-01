# Guarana-Luz (firmware do anel de luz)

ESP32 + anel WS2812B controlado pelo app Guaraná. Mesmo protocolo por Bluetooth LE e por Wi-Fi.

## Montagem

| Anel WS2812B | ESP32 |
|---|---|
| DIN | GPIO 5, com resistor de 330 Ω em série |
| 5V | 5V (VIN). Acima de 16 LEDs em brilho alto, use fonte 5 V externa e junte os GNDs |
| GND | GND |

Capacitor de 1000 µF entre 5 V e GND junto do anel. Se o WS2812B não aceitar o sinal de 3,3 V, use um conversor de nível ou um LED "sacrificial" como repetidor.

## Gravar

1. Arduino IDE: Placas → instalar "esp32 by Espressif Systems". Bibliotecas → instalar "Adafruit NeoPixel".
2. Abrir `guarana_luz.ino`, ajustar `LED_PIN` e `NUM_LEDS`, escolher a placa ESP32 Dev Module, gravar.
3. Ao ligar, o anel pisca verde duas vezes. Monitor serial em 115200 mostra o IP e o nome Bluetooth.

## Testar sem o app

```
# pelo Wi-Fi: conecte na rede Guarana-Luz (senha guarana123)
curl "http://192.168.4.1/cmd?c=P"
curl "http://192.168.4.1/cmd?c=SFF0000FF80"   # vermelho, brilho 50%
curl "http://192.168.4.1/cmd?c=O"
# pelo monitor serial: digite P, O ou SFFFFFFFF99 e Enter
```

Bluetooth: qualquer app "BLE scanner" mostra `Guarana-Luz` com o serviço 6e400001-…; escreva o comando em texto na característica 6e400002-….

## Protocolo

- `S` + `RRGGBBWWII` em hex: cor, canal branco (somado aos três canais, pois o WS2812B não tem branco dedicado) e brilho geral.
- `O`: apaga. `P`: ping, responde `{"ok":true,"fw":"…","leds":16}`.

Rotina padrão do app: branco 30%, 60% e 100%, vermelho, verde, azul, ambiente (apagado), com uma foto por passo. O quadro "Branco 60%" é o que entra na análise; os demais ficam guardados na análise para calibração de cor.

## Adaptar

- ESP8266: sem Bluetooth. Deixe `ENABLE_BLE 0`, troque `WiFi.h` por `ESP8266WiFi.h` e `WebServer.h` por `ESP8266WebServer.h`. No app, escolha "Wi-Fi do ESP".
- LEDs comuns por PWM (não endereçáveis): substitua `fill()` por `ledcWrite` nos canais R, G, B e W.
- Anel RGBW (SK6812): use `NEO_GRBW` e passe `w` direto no quarto canal em `strip.Color(r, g, b, w)`.
