"""Simula o Guarana-Luz por HTTP para testar o app sem o ESP32 (emulador acessa o Mac em 10.0.2.2).
Uso: python3 firmware/mock/mock_esp.py 8080   ->   no app, Wi-Fi do ESP, endereco 10.0.2.2:8080
"""
import sys, json, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

def handle(cmd):
    cmd = cmd.strip()
    if not cmd: return {"ok": False, "err": "vazio"}
    op = cmd[0].upper()
    if op == "P": return {"ok": True, "fw": "mock-esp 1.0", "leds": 16}
    if op == "O": return {"ok": True, "state": "off"}
    if op == "S" and len(cmd) >= 11:
        r, g, b, w, i = (int(cmd[k:k+2], 16) for k in (1, 3, 5, 7, 9))
        return {"ok": True, "r": r, "g": g, "b": b, "w": w, "bri": i}
    return {"ok": False, "err": "cmd"}

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path != "/cmd":
            self.send_response(404); self.end_headers(); return
        cmd = parse_qs(u.query).get("c", [""])[0]
        reply = handle(cmd)
        print(time.strftime("%H:%M:%S"), cmd, "->", json.dumps(reply), flush=True)
        body = json.dumps(reply).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
print("mock Guarana-Luz em http://0.0.0.0:%d/cmd?c=P" % port, flush=True)
HTTPServer(("0.0.0.0", port), H).serve_forever()
