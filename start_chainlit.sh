#!/usr/bin/env bash
# start_chainlit.sh — Inicia a interface Chainlit do Data Agents (porta 8503)
#
# Uso:
#   ./start_chainlit.sh              # porta padrão 8503
#   CHAINLIT_PORT=8504 ./start_chainlit.sh
#
# O Streamlit (start.sh) continua funcionando normalmente na porta 8502.
# Este script é adicional e independente.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${CHAINLIT_PORT:-8503}"

# Verifica se chainlit está instalado
if ! command -v chainlit &> /dev/null; then
    echo "❌ chainlit não encontrado."
    echo "   Instale com: pip install -e '.[ui]'"
    exit 1
fi

echo "🚀 Iniciando Data Agents — Interface Chainlit"
echo "   Porta : $PORT"
echo "   URL   : http://localhost:$PORT"
echo "   App   : ui/chainlit_app.py"
echo ""
echo "   Modo 1 — Data Agents  : Supervisor + agentes especialistas"
echo "   Modo 2 — Dev Assistant: Claude + ferramentas de desenvolvimento"
echo ""
echo "   Streamlit continua disponível em: http://localhost:8502 (start.sh)"
echo ""

chainlit run ui/chainlit_app.py \
    --port "$PORT" \
    --host 0.0.0.0
