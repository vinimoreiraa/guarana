# Firmwares do anel de luz

| Pasta | Placa | Ligação com o tablet | Uso |
|---|---|---|---|
| `guarana_luz_serial/` | ESP32-CAM (AI-Thinker) ou ESP32 comum | **USB (serial)** | Padrão. Nada fixo: pinos, quantidade e tipo de LED e o flash são configurados pelo app por comandos e gravados na flash |
| `guarana_luz/` | ESP32 | Bluetooth LE ou Wi-Fi do próprio ESP | Alternativa sem cabo |
| `mock/mock_esp.py` | nenhum | HTTP no Mac | Simula o firmware para testar o app no emulador |

## Serial (padrão)

Ligação: ESP32-CAM na placa-base com CH340 (ESP32-CAM-MB) ou adaptador USB-serial → cabo USB → adaptador OTG → tablet. O Android pergunta "Abrir Guaraná para este dispositivo?" ao plugar; aceite e a permissão fica dada.

LEDs: fita/anel WS2812B com DIN num pino livre da ESP32-CAM (13, 14, 15 ou 2; não use 12 nem 4), 5 V e GND. Resistor de 330 Ω no dado, capacitor de 1000 µF na alimentação. O LED de flash da placa (GPIO 4) também é controlável (`FL`), e serve como luz branca forte.

Gravar: Arduino IDE → placa "AI Thinker ESP32-CAM" (ou "ESP32 Dev Module" com `#define HAS_CAMERA 0`), biblioteca Adafruit NeoPixel. Na ESP32-CAM sem USB nativo, gravar exige GPIO 0 no GND durante o upload (a placa-base MB faz isso com o botão).

Protocolo (115200 8N1, uma linha por comando, resposta JSON em uma linha):

```
P                                  -> {"ok":true,"fw":"guarana-luz-serial 2.0","mode":"ws","pin":13,"n":12,...,"cam":true}
CFG mode=ws pin=13 n=12 type=GRB flash=4     configura e grava; o app manda isto ao conectar
CFG mode=pwm r=12 g=13 b=14 w=15 flash=4     LEDs comuns por PWM
S FFFFFFFF99  (ou SFFFFFFFF99)     todos os LEDs: RR GG BB WW + brilho II, em hex
L 3 FF0000   /  X                  um LED por vez, depois mostrar
B 80                               brilho geral
FL C8                              flash da placa em 200/255
O                                  apaga tudo
CAM res=VGA q=12                   resolução e qualidade da câmera
F                                  quadro JPEG: "FRAME <bytes>\n" + bytes crus
```

Teste sem o app: monitor serial da IDE a 115200, digite `P` e Enter.

## O que o app controla (Ajustes → Anel de luz)

- **Transporte:** USB, Bluetooth ou Wi-Fi.
- **Configuração enviada ao conectar:** uma linha `CFG …` editável. Mudou o pino ou a quantidade de LEDs? Edite no app, não no firmware.
- **Rotina de cores:** texto editável, uma linha por passo: `rótulo; comando; espera em ms; foto`. A linha marcada com `*` é o quadro analisado. Qualquer comando do protocolo vale, inclusive `FL` e `L`.
- **A foto é sempre da câmera do tablet.** A ESP32-CAM entra só como controladora de LEDs; a câmera dela fica desligada no firmware (`HAS_CAMERA 0`). O comando `F` existe para um uso futuro.
