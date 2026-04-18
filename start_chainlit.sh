#!/usr/bin/env bash
# start_chainlit.sh — Inicia a interface Chainlit do Data Agents (porta 8503)
#
# Uso:
#   ./start_chainlit.sh               # Chainlit + Business Monitor (padrão)
#   ./start_chainlit.sh --no-monitor  # Chainlit sem o Business Monitor
#   CHAINLIT_PORT=8504 ./start_chainlit.sh
#
# Para parar o Business Monitor sem encerrar o chat:
#   /monitor stop   (no chat)
#   /monitor off    (pausa os ciclos, daemon continua vivo)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${CHAINLIT_PORT:-8503}"
BIZ_MONITOR=true   # padrão: sempre ativo

for arg in "$@"; do
  case "$arg" in
    --no-monitor) BIZ_MONITOR=false ;;
  esac
done

# ── Carrega .env — garante que as variáveis corretas sobrescrevem o shell ──────
# Crítico: sem isso, variáveis exportadas por start.sh (ex: ANTHROPIC_BASE_URL
# de uma sessão Flow anterior) ficam ativas e o Chainlit usa config errada.
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      val="${BASH_REMATCH[2]}"
      val="${val#\'}" ; val="${val%\'}"
      val="${val#\"}" ; val="${val%\"}"
      export "$key=$val"
    fi
  done < "$SCRIPT_DIR/.env"
fi

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

# ── Business Monitor daemon ───────────────────────────────────────────────────
PID_FILE="$SCRIPT_DIR/config/monitor_daemon.pid"

if [[ "$BIZ_MONITOR" == true ]]; then
  # Mata instância anterior se ainda estiver rodando
  if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
      echo "   ♻️  Encerrando monitor anterior (PID $OLD_PID)..."
      kill "$OLD_PID" 2>/dev/null || true
      sleep 1
    fi
  fi

  mkdir -p logs
  python scripts/monitor_daemon.py > logs/biz_monitor.log 2>&1 &
  BIZ_MONITOR_PID=$!
  echo "$BIZ_MONITOR_PID" > "$PID_FILE"

  echo "   📡 Business Monitor   : ativo (ciclos 08h–23h)"
  echo "   PID                   : $BIZ_MONITOR_PID"
  echo "   Logs                  : logs/biz_monitor.log"
  echo "   Para parar no chat    : /monitor stop"
  echo ""
else
  echo "   ⏸️  Business Monitor   : desativado (use sem --no-monitor para ativar)"
  echo ""
fi

chainlit run ui/chainlit_app.py \
    --port "$PORT" \
    --host 0.0.0.0
