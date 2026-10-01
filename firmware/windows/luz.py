"""Controle serial do Guarana-Luz a partir do PC (Windows/Mac/Linux). Requer: pip install pyserial

Uso:
  python luz.py                      lista portas e entra no modo interativo
  python luz.py --port COM5 P        manda um comando e mostra a resposta
  python luz.py --port COM5 "S FF000000FF" O
  python luz.py --port COM5 --rotina   executa branco, azul, vermelho, ambiente (so os LEDs; a foto e do tablet)
"""
import sys, time, argparse
try:
    import serial, serial.tools.list_ports
except ImportError:
    sys.exit("instale: python -m pip install pyserial")

def portas():
    return list(serial.tools.list_ports.comports())

def escolher(pref=None):
    ps = portas()
    if pref:
        return pref
    for p in ps:
        d = (p.description or "") + " " + (p.manufacturer or "") + " " + (p.hwid or "")
        if any(k in d.upper() for k in ("CH340", "CH341", "CP210", "FTDI", "USB SERIAL", "SILICON", "303A", "1A86", "10C4", "0403")):
            return p.device
    return ps[0].device if ps else None

def abrir(port, baud):
    s = serial.Serial(port, baud, timeout=0.3, dsrdtr=False, rtscts=False)
    s.dtr = True; s.rts = True   # evita reset/bootloader em placas com auto-reset
    time.sleep(1.5)              # se a placa reiniciou, espera o boot
    s.reset_input_buffer()
    return s

def cmd(s, c, espera=2.0):
    s.write((c.strip() + "\n").encode()); t0 = time.time(); linhas = []
    while time.time() - t0 < espera:
        l = s.readline().decode(errors="replace").strip()
        if l:
            linhas.append(l)
            if l.startswith("{"): break
    return linhas

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port"); ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--rotina", action="store_true"); ap.add_argument("comandos", nargs="*")
    a = ap.parse_args()
    print("portas:", [(p.device, p.description) for p in portas()])
    port = escolher(a.port)
    if not port:
        sys.exit("nenhuma porta serial encontrada")
    print("usando", port, "@", a.baud)
    s = abrir(port, a.baud)
    if a.rotina:
        for rot, c in [("branco", "SFFFFFFFF99"), ("azul", "S0000FF00FF"), ("vermelho", "SFF000000FF"), ("ambiente", "O")]:
            print(rot, "->", cmd(s, c)); time.sleep(1.0)
        return
    if a.comandos:
        for c in a.comandos:
            print(c, "->", cmd(s, c))
        return
    print("modo interativo: P, O, SFFFFFFFF99, CFG mode=ws pin=13 n=12 type=GRB flash=4, FL C8 ... (Ctrl+C sai)")
    try:
        while True:
            c = input("> ").strip()
            if c: print(cmd(s, c))
    except (KeyboardInterrupt, EOFError):
        pass

if __name__ == "__main__":
    main()
