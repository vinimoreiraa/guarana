# Grava o firmware Guarana-Luz num ESP32 / ESP32-CAM a partir do Windows, sem Arduino IDE.
# Uso (PowerShell):  .\flash.ps1 [-Port COM5] [-Board esp32cam|esp32]
# Precisa de Python 3 (https://www.python.org, marque "Add to PATH"). O script instala esptool/pyserial via pip.
# ESP32-CAM sem placa-base com auto-reset: segure GPIO0 no GND (botao IO0/BOOT) ao ligar, solte depois de gravar.
param([string]$Port = "", [string]$Board = "esp32cam", [int]$Baud = 460800)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$bin = Join-Path $here "build\$Board"
if (-not (Test-Path $bin)) { throw "pasta de binarios nao encontrada: $bin" }

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { throw "Python nao encontrado. Instale em https://www.python.org e marque 'Add python.exe to PATH'." }
& $py.Source -m pip install --quiet --disable-pip-version-check esptool pyserial

if ($Port -eq "") {
  $ports = & $py.Source -c "import serial.tools.list_ports as l; print('\n'.join(p.device+'|'+(p.description or '') for p in l.comports()))"
  Write-Host "portas:`n$ports"
  $cand = ($ports -split "`n") | Where-Object { $_ -match "CH340|CH341|CP210|FTDI|USB Serial|Silicon" } | Select-Object -First 1
  if (-not $cand) { $cand = ($ports -split "`n") | Select-Object -First 1 }
  if (-not $cand) { throw "nenhuma porta serial; plugue o ESP e confira o driver CH340/CP210x" }
  $Port = ($cand -split "\|")[0]
}
Write-Host "gravando $Board em $Port ..."

$merged = Get-ChildItem $bin -Filter "*.merged.bin" | Select-Object -First 1
if ($merged) {
  & $py.Source -m esptool --chip esp32 --port $Port --baud $Baud --before default_reset --after hard_reset write_flash -z 0x0 $merged.FullName
} else {
  $boot = Get-ChildItem $bin -Filter "*.bootloader.bin" | Select-Object -First 1
  $part = Get-ChildItem $bin -Filter "*.partitions.bin" | Select-Object -First 1
  $app  = Get-ChildItem $bin -Filter "*.ino.bin" | Select-Object -First 1
  $app0 = Join-Path $bin "boot_app0.bin"
  & $py.Source -m esptool --chip esp32 --port $Port --baud $Baud --before default_reset --after hard_reset write_flash -z `
      0x1000 $boot.FullName 0x8000 $part.FullName 0xE000 $app0 0x10000 $app.FullName
}
Write-Host "pronto. teste:  python luz.py --port $Port P"
