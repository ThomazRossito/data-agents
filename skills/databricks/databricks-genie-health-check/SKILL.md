---
skill: databricks-genie-health-check
type: operational-playbook
agents: [semantic-modeler]
tools: [mcp__databricks_genie__genie_ask, mcp__databricks_genie__list_spaces, mcp__databricks__execute_sql, mcp__databricks__get_query_history]
updated_at: 2026-04-30
---

# Genie Health Check — 20 Verificações Automatizadas de Genie Spaces

<!-- type: concept -->
## O que é

Playbook de diagnóstico completo para Genie Spaces no Databricks. Executa 20 verificações
distribuídas em 5 dimensões para avaliar a saúde, cobertura e qualidade de um Space.
Resultado: relatório com nota A-F por dimensão e ações corretivas priorizadas.

---

<!-- type: pattern -->
## Protocolo de Execução

### Pré-condição

```python
# 1. Listar Spaces disponíveis
spaces = mcp__databricks_genie__list_spaces()

# 2. Identificar o Space alvo (por nome ou ID)
# Se não especificado pelo usuário, listar e perguntar
space_id = "<id-do-space>"
```

### As 5 Dimensões e 20 Verificações

---

<!-- type: pattern -->
## Dimensão 1 — Cobertura de Dados (0–20 pts)

**C1 — Tabelas referenciadas existem no Unity Catalog**
```sql
-- Verificar se cada tabela declarada no Space existe no catálogo
SELECT table_name, table_catalog, table_schema
FROM system.information_schema.tables
WHERE CONCAT(table_catalog, '.', table_schema, '.', table_name)
  IN (/* lista de tabelas do Space */);
-- ✓ Todas existem: 4 pts | Alguma ausente: 0 pts
```

**C2 — Cobertura de tabelas Gold/fct_* no Space**
```sql
-- % de tabelas fct_* e dim_* do catálogo referenciadas no Space
SELECT
  COUNT(CASE WHEN table_name LIKE 'fct_%' OR table_name LIKE 'dim_%' THEN 1 END) AS gold_total,
  COUNT(CASE WHEN /* tabela está no Space */ THEN 1 END) AS gold_in_space
FROM system.information_schema.tables
WHERE table_schema = 'gold';
-- ✓ ≥ 80%: 4 pts | 50-79%: 2 pts | < 50%: 0 pts
```

**C3 — Curated Questions cobrem os principais KPIs**

Verificar se há ao menos 1 curated question para cada categoria:
- Receita / Vendas
- Volume / Quantidade
- Tempo / Período
- Comparação / Ranking

```
# Via API Genie: get_space_questions(space_id)
# Classificar perguntas por categoria via NLP simples (keywords)
# ✓ Todas 4 categorias cobertas: 4 pts | 3 categorias: 2 pts | ≤ 2: 0 pts
```

**C4 — Métricas calculadas (measures) declaradas explicitamente**
```
# Verificar se o Space tem measures definidas (não apenas colunas brutas)
# measures = campos com fórmulas, ex: revenue = SUM(amount)
# ✓ ≥ 5 measures: 4 pts | 1-4: 2 pts | nenhuma: 0 pts
```

**C5 — Filtros de data disponíveis em perguntas de período**
```
# Verificar se ao menos uma coluna de data/timestamp está mapeada para filtro
# ex: data_pedido, admission_ts, billing_date
# ✓ Presente: 4 pts | Ausente: 0 pts
```

---

<!-- type: pattern -->
## Dimensão 2 — Qualidade de Respostas (0–20 pts)

**Q1 — Taxa de sucesso das últimas 50 perguntas**
```sql
-- Verificar query history do warehouse associado ao Space
SELECT
  COUNT(*) AS total_queries,
  SUM(CASE WHEN status = 'FINISHED' THEN 1 ELSE 0 END) AS successful,
  ROUND(SUM(CASE WHEN status = 'FINISHED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS success_rate
FROM system.query.history
WHERE warehouse_id = '<warehouse_id>'
  AND statement_type = 'SELECT'
  AND start_time >= current_timestamp() - INTERVAL 7 DAYS
LIMIT 1;
-- ✓ ≥ 90%: 5 pts | 70-89%: 3 pts | < 70%: 0 pts
```

**Q2 — Latência média das queries geradas pelo Genie**
```sql
SELECT AVG(duration / 1000.0) AS avg_duration_seconds
FROM system.query.history
WHERE warehouse_id = '<warehouse_id>'
  AND start_time >= current_timestamp() - INTERVAL 7 DAYS;
-- ✓ < 5s: 5 pts | 5-15s: 3 pts | > 15s: 0 pts
```

**Q3 — Ausência de fallback para "não sei responder"**
```
# Verificar respostas com "I don't know", "cannot answer", "unclear"
# nos logs de conversação do Genie
# ✓ < 10% de fallbacks: 5 pts | 10-25%: 2 pts | > 25%: 0 pts
```

**Q4 — Diversidade de SQL gerado (não repete a mesma query)**
```sql
-- Verificar % de queries únicas vs repetidas
SELECT
  COUNT(*) AS total,
  COUNT(DISTINCT query_hash) AS unique_queries,
  ROUND(COUNT(DISTINCT query_hash) * 100.0 / COUNT(*), 1) AS diversity_pct
FROM system.query.history
WHERE warehouse_id = '<warehouse_id>'
  AND start_time >= current_timestamp() - INTERVAL 7 DAYS;
-- ✓ ≥ 70% únicas: 5 pts | 40-69%: 2 pts | < 40%: 0 pts
```

---

<!-- type: pattern -->
## Dimensão 3 — Calibração e Instruções (0–20 pts)

**K1 — Space tem descrição preenchida (não vazia)**
```
# Verificar campo description via get_space(space_id)
# ✓ Descrição ≥ 50 chars: 5 pts | < 50 chars: 2 pts | vazia: 0 pts
```

**K2 — Instruções de negócio presentes (business context)**
```
# Verificar campo instructions / business_context do Space
# Deve conter: definições de métricas, regras de negócio, glossário
# ✓ Instruções ≥ 200 chars com definições: 5 pts | presentes mas curtas: 2 pts | ausentes: 0 pts
```

**K3 — Curated Questions têm SQL validado (não apenas texto)**
```
# Cada curated question deve ter SQL associado e testado
# Verificar via execute de cada SQL das curated questions
# ✓ ≥ 90% com SQL válido: 5 pts | 60-89%: 2 pts | < 60%: 0 pts
```

**K4 — Aliases de métricas definidos (evitar ambiguidade)**
```
# Verificar se métricas com nomes ambíguos têm aliases
# ex: "receita" → definida como net_revenue vs gross_revenue?
# ✓ Aliases para todos os termos ambíguos: 5 pts | parcial: 2 pts | ausente: 0 pts
```

---

<!-- type: pattern -->
## Dimensão 4 — Governança e Segurança (0–20 pts)

**G1 — Warehouse associado ao Space é dedicado ou serverless**
```sql
SELECT warehouse_type, size, auto_stop_mins
FROM system.compute.warehouses
WHERE id = '<warehouse_id>';
-- ✓ Serverless ou Pro ≥ Medium: 5 pts | Starter: 2 pts | Shared Classic: 0 pts
```

**G2 — Acesso ao Space restrito por grupo (não público)**
```
# Verificar permissões do Space via Unity Catalog permissions
# ✓ Restrito a grupos específicos: 5 pts | Aberto a workspace: 2 pts | Público: 0 pts
```

**G3 — Tabelas com PII têm Dynamic Views ou RLS no Space**
```sql
-- Verificar se tabelas com colunas PII (cpf, email, phone) têm row-level security
SELECT t.table_name, c.column_name
FROM system.information_schema.columns c
JOIN system.information_schema.tables t USING (table_catalog, table_schema, table_name)
WHERE c.column_name REGEXP 'cpf|email|phone|ssn|dob|birth'
  AND t.table_schema IN (/* schemas do Space */)
  AND t.table_name NOT LIKE '%_view%';
-- ✓ Nenhuma PII exposta diretamente: 5 pts | Algumas com view: 2 pts | PII sem proteção: 0 pts
```

**G4 — Auditoria de acessos ao Space habilitada**
```sql
-- Verificar se system.access.audit captura acessos ao Space
SELECT COUNT(*) AS audit_events_7d
FROM system.access.audit
WHERE service_name = 'databricksSQL'
  AND action_name = 'runCommand'
  AND DATE(event_time) >= current_date() - 7;
-- ✓ Auditoria ativa com eventos: 5 pts | Sem eventos recentes: 0 pts
```

---

<!-- type: pattern -->
## Dimensão 5 — Adoção e Uso (0–20 pts)

**A1 — Usuários únicos nos últimos 30 dias**
```sql
SELECT COUNT(DISTINCT user_name) AS unique_users
FROM system.query.history
WHERE warehouse_id = '<warehouse_id>'
  AND start_time >= current_timestamp() - INTERVAL 30 DAYS;
-- ✓ ≥ 10 usuários: 5 pts | 3-9: 3 pts | 1-2: 1 pt | 0: 0 pts
```

**A2 — Frequência de uso: queries por dia (últimos 30 dias)**
```sql
SELECT AVG(daily_queries) AS avg_queries_per_day
FROM (
  SELECT DATE(start_time) AS day, COUNT(*) AS daily_queries
  FROM system.query.history
  WHERE warehouse_id = '<warehouse_id>'
    AND start_time >= current_timestamp() - INTERVAL 30 DAYS
  GROUP BY DATE(start_time)
);
-- ✓ ≥ 20/dia: 5 pts | 5-19: 3 pts | 1-4: 1 pt | 0: 0 pts
```

**A3 — Trend de uso (crescendo ou estável)**
```sql
SELECT
  DATE_TRUNC('week', start_time) AS week,
  COUNT(*) AS queries
FROM system.query.history
WHERE warehouse_id = '<warehouse_id>'
  AND start_time >= current_timestamp() - INTERVAL 28 DAYS
GROUP BY DATE_TRUNC('week', start_time)
ORDER BY week;
-- ✓ Trend positivo ou estável: 5 pts | Declínio > 30%: 0 pts
```

**A4 — Curated Questions mais usadas vs menos usadas**
```
# Identificar as 3 mais usadas e as 3 menos (ou nunca) usadas
# Curated Questions não usadas há 30+ dias → candidatas a remoção ou melhoria
# ✓ Todas usadas pelo menos 1x: 5 pts | 50%+ sem uso: 2 pts | 80%+ sem uso: 0 pts
```

---

<!-- type: example -->
## Output do Health Check

```
🏥 Genie Health Check — Space: "Vendas & Performance"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Space ID: abc-123 | Warehouse: serverless-m | Tabelas: 8

  Cobertura de Dados   ████████████████░░░░  16/20  B
  Qualidade Respostas  ████████████░░░░░░░░  12/20  D
  Calibração           ████████████████████  20/20  A
  Governança           ████████████░░░░░░░░  12/20  D
  Adoção               ████████░░░░░░░░░░░░   8/20  E

  SCORE TOTAL: 68/100  → Nota Global: C

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ Top 5 Ações Corretivas (por impacto):

  1. [Adoção E→B] Divulgar Space para 3 times ainda não conectados (+12 pts potencial)
  2. [Qualidade D→B] Otimizar queries lentas: 4 curated questions com avg > 12s (+6 pts)
  3. [Governança D→B] Adicionar RLS em dim_customers.cpf_hash (+5 pts)
  4. [Qualidade D→C] Adicionar curated questions para categoria "Comparação/Ranking" (+3 pts)
  5. [Adoção E→D] Revisar 5 curated questions sem uso nos últimos 30 dias (+2 pts)

Relatório salvo em: output/catalog/genie_health_<space_id>_<date>.md
```

---

<!-- type: constraint -->
## Restrições

1. **NUNCA** executar queries de escrita durante o health check — somente SELECT e GET
2. Se `system.query.history` não estiver disponível, marcar verificações Q1/Q2/A1/A2/A3 como `N/A (0 pts)` e alertar o usuário
3. Se o Space tiver menos de 7 dias de histórico, normalizar os scores proporcionalmente
4. Salvar relatório em `output/catalog/genie_health_{space_id}_{date}.md` via Write
5. Ao final, sugerir: `/ship genie-health-<space-name>` para arquivar lições aprendidas
