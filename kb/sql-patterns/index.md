---
mcp_validated: "2026-04-15"
---

# KB: Padrões SQL — Índice

**Domínio:** Geração e otimização de SQL para Databricks e Fabric.
**Agentes:** sql-expert

---

## Conteúdo Disponível

### Conceitos (`concepts/`)

| Arquivo                                        | Conteúdo                                                           |
|------------------------------------------------|--------------------------------------------------------------------|
| `concepts/star-schema-source-of-truth.md`      | **CANONICAL** Star Schema: regras invioláveis dim_*/fact_*/dim_data |
| `concepts/ddl-concepts.md`                     | Delta DDL: CREATE TABLE, schemas, types, constraints — conceitos  |
| `concepts/query-concepts.md`                   | Otimização: CBO, predicate pushdown, AQE, CLUSTER BY — conceitos  |
| `concepts/dialect-concepts.md`                 | Spark SQL vs T-SQL vs KQL — diferenças e equivalências            |

### Padrões (`patterns/`)

| Arquivo                    | Conteúdo                                                              |
|----------------------------|-----------------------------------------------------------------------|
| `patterns/ddl-patterns.md`          | SQL DDL completo: tabelas Delta, views, schemas, CTAS          |
| `patterns/query-patterns.md`        | CTEs, Window Functions, EXPLAIN, predicate pushdown SQL        |
| `patterns/dialect-patterns.md`      | Tabela de conversão Spark↔T-SQL↔KQL com exemplos completos     |

---

## Regras de Negócio Críticas

### Star Schema (Gold Layer)
- `dim_*` NUNCA derivam de tabelas transacionais (silver_*).
- `dim_data` usa `SEQUENCE(DATE '2020-01-01', DATE '2030-12-31', INTERVAL 1 DAY)` + `EXPLODE`. NUNCA `SELECT DISTINCT data FROM silver_*`.
- `fact_*` DEVE fazer `INNER JOIN` com TODAS as dimensões relacionadas.
- Use `CLUSTER BY` nas tabelas Gold. NUNCA `PARTITION BY` + `ZORDER BY` em `MATERIALIZED VIEW`.

### Dialetos por Plataforma
- **Databricks** → Spark SQL
- **Fabric Lakehouse** → T-SQL (Synapse)
- **Fabric Eventhouse** → KQL

### Otimização Obrigatória
- Sempre use CTEs para queries complexas (legibilidade e otimização pelo planner).
- Evite `SELECT *` em produção — liste colunas explicitamente.
- Use `CLUSTER BY` em vez de `ZORDER BY` para tabelas Delta modernas.
- Aplique predicate pushdown: filtre antes de joins.
