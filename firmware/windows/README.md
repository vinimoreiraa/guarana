# Gravar e controlar pelo Windows (sem Arduino IDE)

1. Instale o Python 3 (python.org, marcar "Add to PATH") e o driver da porta serial da placa (CH340 ou CP210x), se o Windows não reconhecer.
2. Copie esta pasta `windows/` e a pasta `build/` (binários compilados no Mac) para o PC.
3. PowerShell na pasta: `.\flash.ps1` (detecta a porta; `-Port COM5` para forçar; `-Board esp32` para DevKit comum).
4. Teste: `python luz.py P` → deve responder `{"ok":true,"fw":"guarana-luz-serial 2.0",...}`.
5. Configure os LEDs sem recompilar: `python luz.py "CFG mode=ws pin=13 n=12 type=GRB flash=4"` e acenda: `python luz.py SFF000000FF`.

Pelo SSH a partir do Mac, os mesmos comandos rodam remotamente: `ssh usuario@ip "python C:\guarana\luz.py P"`.
