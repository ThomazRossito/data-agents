# SQL Rules — Regras Centralizadas de Execução

Regras obrigatórias para geração e execução de SQL em qualquer plataforma (Databricks, Fabric, PostgreSQL).
Todos os agentes que geram ou executam SQL **devem** verificar estas regras antes de executar.

> Complementa `kb/shared/anti-patterns.md`. As regras aqui são **pré-execução** (checklist antes de rodar);
> os anti-padrões são referência de design.

---

## Regras de Execução Obrigatórias

### R01 — Nunca `SELECT *` sem `LIMIT` em tabelas desconhecidas

```sql
-- ❌ Nunca
SELECT * FROM catalog.schema.events;

-- ✓ Sempre
SELECT * FROM catalog.schema.events LIMIT 100;

-- ✓ Ou especificar colunas + filtro
SELECT event_id, event_ts, user_id
FROM catalog.schema.events
WHERE event_date = current_date()
LIMIT 500;
```

**Por quê:** tabelas em produção podem ter bilhões de linhas. Full scan desperdicia compute e pode causar timeout ou OOM.

---

### R02 — DDL destrutivo exige confirmação explícita do usuário

Antes de executar qualquer uma das operações abaixo, **parar e confirmar** com o usuário:

| Operação | Risco | Ação obrigatória |
|----------|-------|-----------------|
| `DROP TABLE` | Irreversível fora do período Delta | Confirmar + verificar backup/snapshot |
| `DROP DATABASE` / `DROP SCHEMA` | Cascata — apaga todas as tabelas | Confirmar + listar o que será deletado |
| `TRUNCATE TABLE` | Remove todos os dados | Confirmar + verificar se tabela é downstream |
| `DELETE FROM` sem WHERE | Apaga tudo | Bloquear — exigir WHERE explícito |
| `ALTER TABLE DROP COLUMN` | Perda de schema em Parquet | Confirmar + checar dependências |

---

### R03 — `UPDATE` e `DELETE` sempre com cláusula `WHERE`

```sql
-- ❌ Nunca
DELETE FROM catalog.schema.users;
UPDATE catalog.schema.orders SET status = 'cancelled';

-- ✓ Sempre com WHERE específico
DELETE FROM catalog.schema.users WHERE user_id = 'abc123' AND deleted_at IS NOT NULL;
UPDATE catalog.schema.orders SET status = 'cancelled' WHERE order_id = 42 AND status = 'pending';
```

---

### R04 — Qualificar sempre com catálogo.esquema.tabela no Databricks

```sql
-- ❌ Dependência implícita do schema da sessão — não determinístico
SELECT * FROM orders LIMIT 10;
SELECT * FROM schema.orders LIMIT 10;

-- ✓ Sempre totalmente qualificado
SELECT * FROM main.sales.orders LIMIT 10;
SELECT * FROM hive_metastore.default.orders LIMIT 10;
```

**Por quê:** o schema padrão da sessão varia por cluster e usuário. Queries sem qualificação completa têm comportamento não determinístico.

---

### R05 — `MERGE` deve incluir todas as cláusulas relevantes

```sql
-- ✓ MERGE completo no Databricks
MERGE INTO catalog.schema.target AS t
USING catalog.schema.source AS s
ON t.id = s.id
WHEN MATCHED AND s.deleted = true THEN DELETE
WHEN MATCHED THEN UPDATE SET t.value = s.value, t.updated_at = current_timestamp()
WHEN NOT MATCHED THEN INSERT (id, value, created_at) VALUES (s.id, s.value, current_timestamp())
-- Considerar também: WHEN NOT MATCHED BY SOURCE (para deletes lógicos)
;
```

**Atenção:** `WHEN NOT MATCHED BY SOURCE` é disponível em Databricks Runtime 12.2+. Sem ele, registros deletados na fonte permanecem na tabela destino.

---

### R06 — Queries KQL (Fabric RTI / Kusto) sempre com `| limit`

```kql
// ❌ Nunca em Eventhouses de produção
events
| where timestamp > ago(1h)

// ✓ Sempre com limit explícito
events
| where timestamp > ago(1h)
| limit 500

// ✓ Aggregation sem limit é OK
events
| where timestamp > ago(1h)
| summarize count() by bin(timestamp, 5m)
```

---

### R07 — Joins sem predicado devem ser explicitados como `CROSS JOIN`

```sql
-- ❌ Cross join acidental — produto cartesiano silencioso
SELECT a.*, b.* FROM customers a, dates b;

-- ✓ Explícito quando intencional
SELECT a.*, b.* FROM customers a CROSS JOIN dates b;

-- ✓ Sempre verificar que joins têm ON condition
SELECT o.*, c.name
FROM orders o
JOIN customers c ON o.customer_id = c.id  -- predicado obrigatório
```

---

### R08 — Tabelas particionadas devem filtrar pela coluna de partição

```sql
-- ❌ Ignora partition pruning — lê todas as partições
SELECT * FROM catalog.schema.events WHERE user_id = '123' LIMIT 100;

-- ✓ Filtra pela coluna de partição (ex: event_date) + condição adicional
SELECT * FROM catalog.schema.events
WHERE event_date = '2026-04-30'
  AND user_id = '123'
LIMIT 100;
```

**Como verificar:** `DESCRIBE DETAIL catalog.schema.events` mostra `partitionColumns`.

---

### R09 — Queries de análise exploratória em sandbox, não em produção

Quando o objetivo é explorar dados sem uma query final definida:
1. Usar `LIMIT 100` em todas as queries intermediárias
2. Preferir `SAMPLE` quando disponível: `SELECT * FROM table TABLESAMPLE (10 PERCENT)`
3. Nunca cachear (`CACHE TABLE`) tabelas grandes sem instrução explícita do usuário

---

### R10 — PII identificada → mascarar antes de exibir no output

Se uma query retorna colunas com nomes suspeitos de PII (cpf, ssn, email, phone, password, credit_card, token):

```sql
-- ✓ Mascarar automaticamente no output
SELECT
  SHA2(cpf, 256)          AS cpf_hash,
  REGEXP_REPLACE(email, '(.{2})(.*)(@.*)', '$1***$3') AS email_masked,
  LEFT(phone, 4) || '****' AS phone_partial
FROM catalog.schema.customers
LIMIT 10;
```

**Exceção:** usuário explicitamente solicita PII não mascarada E tem permissão documentada.

---

## Checklist Rápido Pré-Execução

Antes de executar qualquer SQL gerado, verificar:

- [ ] **R01** — `SELECT *` tem `LIMIT` ou colunas específicas?
- [ ] **R02** — Há DDL destrutivo? Se sim, confirmação do usuário obtida?
- [ ] **R03** — `UPDATE`/`DELETE` tem cláusula `WHERE`?
- [ ] **R04** — Tabelas Databricks estão com `catalogo.esquema.tabela`?
- [ ] **R07** — Todos os JOINs têm predicado `ON`?
- [ ] **R08** — Tabela é particionada? Filtro de partição presente?
- [ ] **R10** — Output pode conter PII? Mascaramento aplicado?

---

## Referências

| Regra | Anti-padrão relacionado | Constituição |
|-------|------------------------|--------------|
| R01 | C01 (`SELECT *`) | S3 |
| R02 | C02 (`DROP TABLE`) | S5 |
| R04 | H12 (qualificação Unity Catalog) | S3 |
| R05 | H11 (MERGE incompleto) | S3 |
| R10 | C03 (PII sem mascaramento) | S5 |

> Arquivo canônico: `kb/shared/sql-rules.md`
> Complementa: `kb/shared/anti-patterns.md`
