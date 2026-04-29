# SQL Patterns Quick Reference

> Tabelas de lookup rápido. Para exemplos completos ver arquivos linkados.

## Window Functions Cheatsheet

| Função | Sintaxe | Use Case |
|--------|---------|----------|
| Deduplicação | `ROW_NUMBER() OVER (PARTITION BY key ORDER BY ts DESC)` | Manter registro mais recente |
| Rank com empate | `RANK() / DENSE_RANK() OVER (...)` | Top-N com ties |
| Lag/Lead | `LAG(col, 1) OVER (ORDER BY ts)` | Delta entre períodos |
| Running total | `SUM(val) OVER (ORDER BY ts ROWS UNBOUNDED PRECEDING)` | Acumulado |
| % do total | `val / SUM(val) OVER (PARTITION BY group)` | Share por grupo |

## DDL Checklist

| Campo obrigatório | Exemplo | Regra |
|------------------|---------|-------|
| Schema explícito | `col STRING NOT NULL` | Nunca inferir |
| Comentário de coluna | `COMMENT 'descrição'` | Toda coluna sensível |
| TBLPROPERTIES | `'delta.minReaderVersion' = '2'` | Tabelas com Liquid Clustering |
| Tag PII | `ALTER TABLE t ALTER COLUMN cpf SET TAG ('pii' = 'true')` | Qualquer dado pessoal |
| Prefixo de camada | `slv_`, `gld_`, `mrt_` | Obrigatório por regra N2 |

## Join Types

| Tipo | Quando usar | Risco |
|------|-------------|-------|
| INNER | Apenas matches bidirecionais | Perda silenciosa de linhas |
| LEFT | Preservar tabela base | NULLs não testados downstream |
| CROSS JOIN LATERAL | Fan-out controlado | Explosão de cardinalidade |
| BROADCAST | Lookup table < 10 MB | OOM se tabela maior que estimado |

## Query Optimization Decision Matrix

| Problema | Solução |
|----------|---------|
| Full table scan | Adicionar partition filter `WHERE data_date = ...` |
| Slow join grande×grande | `ANALYZE TABLE` → AQE auto-broadcast |
| Resultados duplicados | Deduplicar com ROW_NUMBER antes do join |
| Subquery correlacionada lenta | Reescrever como CTE + join |
| `SELECT *` em produção | Listar colunas explicitamente |

## Common Pitfalls

| Evite | Prefira |
|-------|---------|
| `SELECT *` em pipelines | Listar colunas explicitamente |
| JOIN sem ON correto → produto cartesiano | Sempre verificar cardinalidade pós-join |
| Implicit type coercion no join | Cast explícito nas chaves |
| Hardcode de datas: `WHERE dt = '2024-01-01'` | Parâmetro ou `current_date()` |
| `NOT IN` com subquery (NULL-unsafe) | `NOT EXISTS` ou LEFT JOIN IS NULL |

## Related

| Tópico | Arquivo |
|--------|---------|
| Window functions (exemplos) | window-functions.md |
| DDL completo | ddl-patterns.md |
| Star Schema + chaves surrogate | star-schema.md |
| Predicado pushdown, Z-ORDER | query-optimization.md |
