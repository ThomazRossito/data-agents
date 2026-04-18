# ═══════════════════════════════════════════════════════════════════
# Data Agents — Makefile
# Automação de tarefas comuns de desenvolvimento e deploy
# ═══════════════════════════════════════════════════════════════════

.PHONY: help install dev bootstrap demo evals test lint format type-check security clean run health-databricks health-fabric fabric-env deploy-staging deploy-prod refresh-skills refresh-skills-dry refresh-skills-force

# Cores para output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

help: ## Exibe esta ajuda
	@echo ""
	@echo "$(CYAN)Data Agents — Comandos disponíveis:$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ─── Setup ────────────────────────────────────────────────────────

install: ## Instala dependências de produção
	pip install -e .

dev: ## Instala dependências de desenvolvimento + UI
	pip install -e ".[dev,ui,monitoring]"

bootstrap: ## Wizard interativo para criar .env mínimo (primeira vez)
	python scripts/bootstrap.py

demo: ## Executa query canônica (/geral) — smoke test end-to-end
	python scripts/demo.py

evals: ## Roda queries canônicas (~$$0.08) e gera scoreboard
	python -m evals.runner

# ─── Quality ──────────────────────────────────────────────────────

test: ## Executa testes com cobertura
	pytest tests/ -v --tb=short \
		--cov=agents --cov=config --cov=hooks --cov=commands \
		--cov-report=term-missing \
		--cov-fail-under=80

lint: ## Executa linter (ruff check)
	ruff check . --output-format=full

format: ## Formata código (ruff format)
	ruff format .

type-check: ## Verifica tipos (mypy)
	mypy agents/ config/ hooks/ commands/

security: ## Scan de segurança (bandit)
	bandit -r agents/ config/ hooks/ commands/ -ll --skip B101

# ─── Execução ─────────────────────────────────────────────────────

run: ## Inicia o Data Agents em modo interativo
	python main.py

ui: ## Inicia a UI de Chat + Monitoring (./start.sh)
	./start.sh

ui-chat: ## Inicia somente a UI de Chat Chainlit (porta 8503)
	./start.sh --chat-only

ui-monitor: ## Inicia somente o Monitoring (porta 8501)
	./start.sh --monitor-only

health-databricks: ## Verifica conectividade e credenciais do Databricks
	python tools/databricks_health_check.py

health-fabric: ## Verifica conectividade e credenciais do Microsoft Fabric
	python tools/fabric_health_check.py

fabric-env: ## Cria ambiente conda para Fabric Notebooks (fabric_environment.yml)
	conda env create -f fabric_environment.yml --force
	@echo "$(GREEN)Ambiente 'data_agents_fabric_env' criado. Ative com: conda activate data_agents_fabric_env$(RESET)"

# ─── Deploy ───────────────────────────────────────────────────────

deploy-staging: ## Deploy para Databricks Staging
	databricks bundle deploy --target staging

deploy-prod: ## Deploy para Databricks Production
	databricks bundle deploy --target production

# ─── Skill Refresh ────────────────────────────────────────────────

refresh-skills: ## Atualiza Skills desatualizadas (respeita SKILL_REFRESH_INTERVAL_DAYS)
	python scripts/refresh_skills.py

refresh-skills-dry: ## Lista Skills que seriam atualizadas (sem modificar)
	python scripts/refresh_skills.py --dry-run

refresh-skills-force: ## Força atualização de TODAS as Skills (ignora intervalo)
	python scripts/refresh_skills.py --force

skill-stats: ## Relatório de uso de Skills (últimos 7 dias)
	python scripts/skill_stats.py

skill-stats-full: ## Relatório completo: skills usadas + não usadas (30 dias)
	python scripts/skill_stats.py --days 30 --not-used

# ─── Limpeza ──────────────────────────────────────────────────────

clean: ## Remove arquivos temporários e cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov coverage.xml
	rm -rf dist build *.egg-info
	@echo "$(GREEN)Limpeza concluída.$(RESET)"
