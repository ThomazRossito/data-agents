# Monitoramento — Data Agents

Dashboard em tempo real para acompanhar execuções, logs, MCP servers e configurações do projeto.

## Instalação (uma vez só)

```bash
# Ative o ambiente conda do projeto
conda activate multi_agents

# Instale as dependências de monitoramento
pip install -e ".[monitoring]"
```

## Iniciar o dashboard

```bash
# Na raiz do projeto
conda activate multi_agents
streamlit run monitoring/app.py
```

Abre automaticamente em **http://localhost:8501**

## O que o dashboard mostra

| Aba | Conteúdo |
|-----|----------|
| 📊 Overview | KPIs gerais, atividade por data, top ferramentas, status dos MCPs |
| 🤖 Agentes | Os 6 agentes do registry com modelo, tier, tools e MCP servers |
| ⚡ Execuções | Volume de cada ferramenta, chamadas MCP reais, histórico |
| 🔌 MCP Servers | Status real baseado em chamadas do audit.jsonl |
| 📋 Logs | Viewer ao vivo do app.jsonl e audit.jsonl com filtros |
| ⚙️ Configurações | Modelo, budget, max_turns, mapa de arquivos |

## Auto-refresh

Use o seletor **Auto-refresh** na sidebar para atualizar automaticamente enquanto os agentes rodam (opções: 5s, 10s, 30s, 60s).
