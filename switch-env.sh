#!/bin/bash
# =============================================================
# Alterna entre configuração pessoal Anthropic e proxy Flow CI&T
# Uso: ./switch-env.sh personal | flow | status
# =============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

show_status() {
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        echo "⚠️  Nenhum .env ativo encontrado."
        return
    fi

    base_url=$(grep -E "^ANTHROPIC_BASE_URL=" "$SCRIPT_DIR/.env" | cut -d= -f2 | tr -d '"')
    model=$(grep -E "^DEFAULT_MODEL=" "$SCRIPT_DIR/.env" | cut -d= -f2)

    if [ -n "$base_url" ]; then
        echo "🏢 Ambiente ativo: Flow CI&T"
        echo "   ANTHROPIC_BASE_URL: $base_url"
    else
        echo "👤 Ambiente ativo: Conta Pessoal Anthropic"
    fi
    echo "   DEFAULT_MODEL: $model"
}

case "$1" in
    personal)
        if [ ! -f "$SCRIPT_DIR/.env.personal" ]; then
            echo "❌ Arquivo .env.personal não encontrado."
            exit 1
        fi
        cp "$SCRIPT_DIR/.env.personal" "$SCRIPT_DIR/.env"
        echo "✅ Usando conta pessoal Anthropic (api.anthropic.com)"
        echo "   T1 → claude-opus-4-6"
        echo "   T2 → claude-sonnet-4-6"
        echo "   T3 → claude-opus-4-6"
        ;;
    flow)
        if [ ! -f "$SCRIPT_DIR/.env.flow" ]; then
            echo "❌ Arquivo .env.flow não encontrado."
            exit 1
        fi
        cp "$SCRIPT_DIR/.env.flow" "$SCRIPT_DIR/.env"
        echo "✅ Usando proxy Flow CI&T (flow.ciandt.com)"
        echo "   Todos os tiers → bedrock/anthropic.claude-4-6-sonnet"
        echo "   ⚠️  Lembre de atualizar o JWT em .env.flow se expirou."
        ;;
    status)
        show_status
        ;;
    *)
        echo "Uso: ./switch-env.sh [personal|flow|status]"
        echo ""
        echo "  personal  → Conta pessoal Anthropic (api.anthropic.com)"
        echo "  flow      → Proxy Flow CI&T (flow.ciandt.com)"
        echo "  status    → Mostra qual ambiente está ativo"
        exit 1
        ;;
esac
