# KB: Pipeline — Medallion Pattern

## Responsabilidades por Camada

### Raw (raw_)
- **O quê**: dado exatamente como chegou da origem
- **Formato**: Delta com schema preservado (sem normalização)
- **Retenção**: longa (source of truth para reprocessamento)
- **Transformações**: nenhuma além de parsing de formato (JSON → colunas, CSV → Delta)
- **Particionamento**: por data de ingestão (`ingested_date`)

### Bronze (brz_)
- **O quê**: dado limpo mas ainda fiel à origem
- **Transformações permitidas**: deduplicação, cast de tipos, renome de colunas
- **Não permitido**: regras de negócio, joins entre domínios
- **Qualidade mínima**: schema validado, nulos críticos rejeitados

### Silver (slv_)
- **O quê**: dado conformado, enriquecido, com histórico (SCD2)
- **Transformações**: joins com dimensões, SCD2, normalização semântica
- **Chaves**: surrogate key + business key
- **Qualidade**: constraints declaradas, expectations validadas

### Gold / Mart (gld_ / mrt_)
- **O quê**: agrupamentos, KPIs, modelos para consumo analítico
- **Formato**: star schema ou flat wide table para BI
- **Performance**: Z-ORDER por dimensões mais filtradas, ANALYZE TABLE
- **Governança**: RLS habilitado se contiver dados sensíveis

## Estrutura de Job Típica

```
Job: pipeline_customers
├── Task 1: ingest_raw        → raw.raw_customers
├── Task 2: clean_bronze      → bronze.brz_customers     (depende de 1)
├── Task 3: enrich_silver     → silver.slv_customers     (depende de 2)
├── Task 4: validate_quality  → (expectations check)     (depende de 3)
└── Task 5: load_gold         → gold.gld_customer_kpis   (depende de 4)
```

## Handoff entre camadas

```python
# Sempre ler da camada imediatamente anterior
# Nunca pular camadas (não ler raw na Silver)
df_bronze = spark.table("catalog.bronze.brz_customers")

# Sempre escrever com MERGE (não overwrite) em Silver+
delta_table.alias("t").merge(
    df_bronze.alias("s"),
    "t.source_id = s.source_id"
).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
```

## Anti-patterns

- ❌ Ler da mesma camada que escreve (loop)
- ❌ Transformações de negócio na Bronze
- ❌ Gold sem agregação (Gold é destino analítico, não passthrough)
- ❌ Schema inference em qualquer camada
