#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# Data Agents — start.sh
# Inicia a UI de Chat (Chainlit, porta 8503) e o App de Monitoramento
# (Streamlit, porta 8501) juntos em segundo plano, com shutdown limpo ao
# pressionar Ctrl+C.
#
# Uso:
#   ./start.sh                # Chat (Chainlit) + Monitoring
#   ./start.sh --chat-only    # somente UI de Chat
#   ./start.sh --monitor-only # somente Monitoramento
#   ./start.sh --biz-monitor  # junto com Business Monitor autônomo
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Cores ─────────────────────────────────────────────────────────────────────
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
BOLD="\033[1m"
RESET="\033[0m"

# ── Portas ────────────────────────────────────────────────────────────────────
CHAINLIT_PORT="${CHAINLIT_PORT:-8503}"
MONITOR_PORT=8501

# ── Raiz do projeto (diretório deste script) ──────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Flags ────────────────────────────────────────────────────────────────────
CHAT_ONLY=false
MONITOR_ONLY=false
BIZ_MONITOR=false
for arg in "$@"; do
  case "$arg" in
    --chat-only)    CHAT_ONLY=true ;;
    --monitor-only) MONITOR_ONLY=true ;;
    --biz-monitor)  BIZ_MONITOR=true ;;
    --help|-h)
      echo ""
      echo "  ${BOLD}./start.sh${RESET} [opções]"
      echo ""
      echo "  Opções:"
      echo "    ${CYAN}--chat-only${RESET}     Inicia somente a UI de Chat Chainlit      (porta $CHAINLIT_PORT)"
      echo "    ${CYAN}--monitor-only${RESET}  Inicia somente o Monitoramento            (porta $MONITOR_PORT)"
      echo "    ${CYAN}--biz-monitor${RESET}   Inicia o Business Monitor autônomo junto com o chat"
      echo "    ${CYAN}--help${RESET}          Exibe esta ajuda"
      echo ""
      echo "  Exemplos:"
      echo "    ./start.sh                    # Chainlit Chat + Monitoring"
      echo "    ./start.sh --biz-monitor      # Chat + Business Monitor autônomo"
      echo "    ./start.sh --monitor-only     # Somente Monitoring"
      echo ""
      exit 0
      ;;
  esac
done

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║       Data Agents — UI Local             ║${RESET}"
echo -e "${BOLD}${CYAN}║       Chat: Chainlit (porta $CHAINLIT_PORT)       ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ── Carrega .env se existir ───────────────────────────────────────────────────
# Usa parser manual (linha a linha) para evitar que valores com caracteres
# especiais ({}, $(), ``, etc.) sejam interpretados pelo bash.
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  echo -e "  ${GREEN}✔${RESET}  Carregando variáveis de ambiente (.env)"
  while IFS= read -r line || [[ -n "$line" ]]; do
    # Ignora linhas vazias e comentários
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    # Aceita apenas linhas no formato KEY=VALUE (KEY pode ter letras, dígitos e _)
    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      val="${BASH_REMATCH[2]}"
      # Remove aspas simples ou duplas envolvendo o valor (se presentes)
      val="${val#\'}" ; val="${val%\'}"
      val="${val#\"}" ; val="${val%\"}"
      export "$key=$val"
    fi
  done < "$SCRIPT_DIR/.env"
else
  echo -e "  ${YELLOW}⚠${RESET}   Arquivo .env não encontrado — usando variáveis de ambiente do sistema"
fi

# ── Detecta / ativa virtualenv ────────────────────────────────────────────────
PYTHON_CMD="python"
STREAMLIT_CMD="streamlit"

# Procura venv em locais comuns
for VENV_DIR in ".venv" "venv" ".env_venv"; do
  if [[ -f "$SCRIPT_DIR/$VENV_DIR/bin/activate" ]]; then
    echo -e "  ${GREEN}✔${RESET}  Ativando virtualenv: ${CYAN}$VENV_DIR${RESET}"
    # shellcheck disable=SC1090
    source "$SCRIPT_DIR/$VENV_DIR/bin/activate"
    PYTHON_CMD="$SCRIPT_DIR/$VENV_DIR/bin/python"
    STREAMLIT_CMD="$SCRIPT_DIR/$VENV_DIR/bin/streamlit"
    break
  fi
done

# Streamlit ainda é usado pelo dashboard de monitoring (monitoring/app.py)
if ! command -v "$STREAMLIT_CMD" &>/dev/null; then
  if "$PYTHON_CMD" -m streamlit --version &>/dev/null 2>&1; then
    STREAMLIT_CMD="$PYTHON_CMD -m streamlit"
  else
    echo -e "  ${RED}✘${RESET}  Streamlit não encontrado (usado pelo monitoring). Instale com: pip install -e '.[monitoring]'"
    exit 1
  fi
fi

# ── Verifica portas ───────────────────────────────────────────────────────────
port_in_use() {
  lsof -i :"$1" &>/dev/null 2>&1 || ss -tlnp 2>/dev/null | grep -q ":$1 " || false
}

if [[ "$CHAT_ONLY" == false ]] && [[ "$MONITOR_ONLY" == false ]]; then
  if port_in_use "$CHAINLIT_PORT"; then
    echo -e "  ${YELLOW}⚠${RESET}   Porta $CHAINLIT_PORT já em uso — UI de Chat pode já estar rodando"
  fi
  if port_in_use "$MONITOR_PORT"; then
    echo -e "  ${YELLOW}⚠${RESET}   Porta $MONITOR_PORT já em uso — Monitoramento pode já estar rodando"
  fi
fi

# ── Cria diretório de logs e faz rotação ─────────────────────────────────────
mkdir -p "$SCRIPT_DIR/logs"

rotate_log() {
  local log_file="$1"
  local max_size_bytes=10485760  # 10 MB
  local max_backups=3
  if [[ -f "$log_file" ]] && [[ $(wc -c < "$log_file") -ge $max_size_bytes ]]; then
    for i in $(seq $max_backups -1 1); do
      [[ -f "${log_file}.${i}" ]] && mv "${log_file}.${i}" "${log_file}.$((i+1))"
    done
    mv "$log_file" "${log_file}.1"
    echo -e "  ${YELLOW}↻${RESET}  Log rotacionado: $(basename "$log_file")"
  fi
}

rotate_log "$SCRIPT_DIR/logs/chainlit.log"
rotate_log "$SCRIPT_DIR/logs/monitor.log"

# ── PIDs dos processos filhos ─────────────────────────────────────────────────
CHAT_PID=""
MONITOR_PID=""
BIZ_MONITOR_PID=""

# ── Função de shutdown ────────────────────────────────────────────────────────
cleanup() {
  echo ""
  echo -e "  ${YELLOW}⏹${RESET}  Encerrando aplicações..."
  if [[ -n "$CHAT_PID" ]] && kill -0 "$CHAT_PID" 2>/dev/null; then
    kill "$CHAT_PID" 2>/dev/null
    echo -e "  ${GREEN}✔${RESET}  UI de Chat encerrada (PID $CHAT_PID)"
  fi
  if [[ -n "$MONITOR_PID" ]] && kill -0 "$MONITOR_PID" 2>/dev/null; then
    kill "$MONITOR_PID" 2>/dev/null
    echo -e "  ${GREEN}✔${RESET}  Monitoramento encerrado (PID $MONITOR_PID)"
  fi
  if [[ -n "$BIZ_MONITOR_PID" ]] && kill -0 "$BIZ_MONITOR_PID" 2>/dev/null; then
    kill "$BIZ_MONITOR_PID" 2>/dev/null
    echo -e "  ${GREEN}✔${RESET}  Business Monitor encerrado (PID $BIZ_MONITOR_PID)"
  fi
  echo ""
  exit 0
}
trap cleanup SIGINT SIGTERM

# ── Inicia Monitoramento ──────────────────────────────────────────────────────
if [[ "$CHAT_ONLY" == false ]]; then
  echo -e "  ${GREEN}▶${RESET}  Monitoramento  →  ${BOLD}http://localhost:$MONITOR_PORT${RESET}"
  $STREAMLIT_CMD run monitoring/app.py \
    --server.port "$MONITOR_PORT" \
    --server.headless true \
    --browser.gatherUsageStats false \
    --theme.base dark \
    > logs/monitor.log 2>&1 &
  MONITOR_PID=$!
fi

# ── Inicia Business Monitor autônomo (daemon) ─────────────────────────────────
if [[ "$BIZ_MONITOR" == true ]]; then
  echo -e "  ${GREEN}▶${RESET}  Business Monitor  →  daemon (ciclos 08h–18h)"
  $PYTHON_CMD scripts/monitor_daemon.py \
    > logs/biz_monitor.log 2>&1 &
  BIZ_MONITOR_PID=$!
fi

# ── Inicia UI de Chat (Chainlit) ──────────────────────────────────────────────
if [[ "$MONITOR_ONLY" == false ]]; then
  CHAINLIT_CMD=""
  if command -v chainlit &>/dev/null; then
    CHAINLIT_CMD="chainlit"
  elif "$PYTHON_CMD" -m chainlit --version &>/dev/null 2>&1; then
    CHAINLIT_CMD="$PYTHON_CMD -m chainlit"
  else
    echo -e "  ${RED}✘${RESET}  Chainlit não encontrado. Instale com: pip install -e '.[ui]'"
    exit 1
  fi
  echo -e "  ${GREEN}▶${RESET}  UI de Chat     →  ${BOLD}http://localhost:$CHAINLIT_PORT${RESET}"
  $CHAINLIT_CMD run ui/chainlit_app.py \
    --port "$CHAINLIT_PORT" \
    --host 0.0.0.0 \
    > logs/chainlit.log 2>&1 &
  CHAT_PID=$!
fi

echo ""
echo -e "  ${CYAN}Pressione Ctrl+C para encerrar.${RESET}"
echo ""

# ── Abre o browser (melhor esforço) ──────────────────────────────────────────
sleep 2
if [[ "$MONITOR_ONLY" == true ]]; then
  MAIN_URL="http://localhost:$MONITOR_PORT"
else
  MAIN_URL="http://localhost:$CHAINLIT_PORT"
fi

if command -v open &>/dev/null; then          # macOS
  open "$MAIN_URL" 2>/dev/null || true
elif command -v xdg-open &>/dev/null; then    # Linux
  xdg-open "$MAIN_URL" 2>/dev/null || true
fi

# ── Aguarda processos filhos ──────────────────────────────────────────────────
# Mantém o script vivo até Ctrl+C; monitora se algum filho morreu inesperadamente
while true; do
  if [[ -n "$CHAT_PID" ]] && ! kill -0 "$CHAT_PID" 2>/dev/null; then
    echo -e "  ${RED}✘${RESET}  UI de Chat encerrou inesperadamente. Verifique logs/chainlit.log"
    CHAT_PID=""
  fi
  if [[ -n "$MONITOR_PID" ]] && ! kill -0 "$MONITOR_PID" 2>/dev/null; then
    echo -e "  ${RED}✘${RESET}  Monitoramento encerrou inesperadamente. Verifique logs/monitor.log"
    MONITOR_PID=""
  fi
  # Se ambos morreram, sai
  if [[ -z "$CHAT_PID" ]] && [[ -z "$MONITOR_PID" ]]; then
    echo -e "  ${RED}✘${RESET}  Todos os processos encerraram. Saindo."
    exit 1
  fi
  sleep 3
done
