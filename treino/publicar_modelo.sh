#!/bin/bash
# Publica um modelo treinado no app: marca confiabilidade por dominio, avalia offline (TTA + casos reais),
# regenera o conjunto de validacao do aparelho, troca os assets e compila o APK.
# Uso: treino/publicar_modelo.sh ocular_v21
set -e
G="$(cd "$(dirname "$0")/.." && pwd)"; V="${1:?versao, ex. ocular_v21}"; PY="$G/.venv/bin/python"
cd "$G"
echo "== confiabilidade por dominio"; $PY treino/marcar_confiabilidade.py --versao "$V"
echo "== avaliacao offline (vistas do app + casos reais)"; $PY treino/avaliar.py --versao "$V" --tta | tail -25
echo "== conjunto de validacao do aparelho"; $PY treino/gerar_conjunto_validacao.py --versao "$V"
A="$G/guarana-app/app/src/main/assets"
rm -f "$A"/ocular_v*.onnx; cp "saida/$V.onnx" "$A/"; cp saida/model_card.json "$A/"
echo "== assets:"; ls -la "$A" | awk '{print $5, $9}'
cd "$G/guarana-app" && export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home && ./gradlew assembleRelease -q 2>&1 | grep -E "^e:|error:|FAILED" -A3 | head -20 || true
ls -la app/build/outputs/apk/release/app-release.apk | awk '{print "APK", $5, $6, $7, $8}'
