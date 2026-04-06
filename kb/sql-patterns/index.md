# KB: Padrões SQL — Índice

**Domínio:** Geração e otimização de SQL para Databricks e Fabric.
**Agentes:** sql-expert

---

## Conteúdo Disponível

| Arquivo                    | Conteúdo                                                              |
|----------------------------|-----------------------------------------------------------------------|
| `ddl-patterns.md`          | Padrões de DDL para tabelas Delta, views e schemas                    |
| `star-schema-rules.md`     | Regras críticas para Star Schema (dim_*, fact_*, dim_data)            |
| `query-optimization.md`    | Boas práticas de otimização: CLUSTER BY, CTEs, predicate pushdown     |
| `dialect-conversion.md`    | Guia de conversão entre Spark SQL, T-SQL e KQL                        |

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
