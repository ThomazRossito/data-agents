---
name: fabric-direct-lake
description: Direct Lake mode para Semantic Models no Fabric — leitura direta de Parquet Delta via OneLake (VertiPaq).
updated_at: 2026-01-15
---

# SKILL: Microsoft Fabric — Direct Lake Mode

> **Fonte:** Microsoft Learn (learn.microsoft.com/fabric/fundamentals/direct-lake-overview)
> **Atualizado:** Janeiro 2026
> **Uso:** Leia este arquivo ANTES de projetar pipelines com destino Power BI / Semantic Models no Fabric.

---

## O que é Direct Lake?

Direct Lake é o modo de acesso padrão dos Semantic Models (antes chamados de "Datasets") no Microsoft Fabric. Em vez de importar dados para um cache in-memory (modo Import) ou fazer queries em tempo real ao banco (DirectQuery), o Direct Lake **lê arquivos Parquet Delta diretamente do OneLake** usando o engine VertiPaq do Power BI.

| Modo         | Fonte             | Velocidade | Atualização     |
|--------------|-------------------|------------|-----------------|
| Import       | Cache in-memory   | Máxima     | Manual/agendada |
| DirectQuery  | Banco em tempo real| Variável  | Tempo real      |
| **Direct Lake** | **OneLake (Parquet Delta)** | **Import-like** | **Quasi real-time** |

---

## Requisitos para Direct Lake

1. **Formato Delta Parquet obrigatório** — tabelas devem estar no formato `.delta` no OneLake.
2. **Armazenamento em OneLake** — tabelas de Lakehouse ou Warehouse nativos do Fabric.
3. **V-Order habilitado** — otimização de escrita que reorganiza os dados para o VertiPaq do Power BI.
4. **Tabelas, não Views** — views T-SQL complexas causam fallback para DirectQuery. Sempre materializar em tabelas Delta.
5. **Schema compatível** — evite tipos não suportados pelo VertiPaq (ex: tipos complexos aninhados sem unnesting).

---

## V-Order — Regra Mandatória

V-Order é uma otimização de escrita nos arquivos Parquet que organiza os dados internamente para o engine VertiPaq do Power BI. Isso resulta em:
- **Carregamento de colunas mais rápido** (streaming comprimido sem descompressão)
- **Scans VertiScan mais eficientes** — computa diretamente sobre dados comprimidos
- **Redução de cold starts** no Direct Lake

### Status do V-Order por engine no Fabric

| Engine                         | V-Order padrão?    | Ação necessária                          |
|--------------------------------|--------------------|------------------------------------------|
| Spark Notebooks (Fabric)       | ✅ SIM             | Nenhuma — habilitado por padrão          |
| Data Factory Pipelines         | ✅ SIM             | Nenhuma — habilitado por padrão          |
| Dataflows Gen2                 | ✅ SIM             | Nenhuma — habilitado por padrão          |
| Spark externo (ex: Databricks) | ❌ NÃO             | Configurar explicitamente                |
| Escrita manual via SDK Python  | ❌ NÃO             | Configurar explicitamente                |

### Habilitação explícita (engines externos ou por segurança)

```python
# Para garantir V-Order em qualquer engine Spark
spark.conf.set("spark.sql.parquet.vorder.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.enabled", "true")

# Escrita com V-Order explícito na tabela Gold
df_gold.write \
    .format("delta") \
    .option("vorder", "true") \
    .mode("overwrite") \
    .saveAsTable("gold.dim_clientes")
```

```sql
-- Via SparkSQL — confirmar V-Order na sessão
SET spark.sql.parquet.vorder.enabled = true;

-- Criar tabela com V-Order
CREATE OR REPLACE TABLE gold.fato_vendas
USING DELTA
TBLPROPERTIES ('delta.parquet.vorder.enabled' = 'true')
AS SELECT ...
```

---

## Fallback para DirectQuery — Causas e Prevenção

Quando o Power BI não consegue usar o Direct Lake para uma query, ele faz **fallback para DirectQuery automaticamente**. Isso degrada a performance. Causas comuns:

| Causa de Fallback                                | Como Prevenir                                                     |
|--------------------------------------------------|-------------------------------------------------------------------|
| Views T-SQL complexas referenciadas no modelo    | Materializar como tabela Delta — não usar views no modelo         |
| Funções DAX não suportadas no Direct Lake        | Testar com `Analyze in Excel` antes de publicar                   |
| Tabelas com tipos de dados complexos (arrays)    | Fazer unnesting/flatten na camada Silver antes da Gold            |
| Exceder limite de linhas do SKU                  | Aumentar SKU ou agregar dados na Gold                             |
| Tabela sem V-Order (arquivo mal formatado)       | Executar OPTIMIZE + reescrita com V-Order                         |
| Mais de 1 Delta log file por tabela (fragmentado)| Executar OPTIMIZE para consolidar                                 |

### Como verificar se está usando Direct Lake ou DirectQuery

```python
# No Power BI Desktop / Service: verificar no Query Diagnostics
# Ou via DAX:
# INFO.STORAGETABLECOLUMNS() retorna "DL" para Direct Lake, "DQ" para DirectQuery
```

---

## Limites por SKU (referência 2025)

| SKU Fabric   | Max linhas por tabela (Direct Lake) | Max tabelas no modelo |
|--------------|-------------------------------------|-----------------------|
| F2           | 300 milhões                         | 1.000                 |
| F4           | 300 milhões                         | 1.000                 |
| F8           | 3 bilhões                           | 5.000                 |
| F16          | 3 bilhões                           | 5.000                 |
| F32+         | Sem limite (fallback desativável)   | Sem limite prático    |

> **Nota:** Estes limites são para Direct Lake. Em SKUs menores, tabelas grandes causam fallback automático.

---

## Otimização OPTIMIZE para Direct Lake

```python
# Executar após cargas de dados significativas
# Consolida small files → melhora throughput do Direct Lake
spark.sql("OPTIMIZE gold.fato_vendas")
spark.sql("OPTIMIZE gold.dim_clientes")
spark.sql("OPTIMIZE gold.dim_produtos")

# Limpar versões antigas do Delta log (manter 7 dias)
spark.sql("VACUUM gold.fato_vendas RETAIN 168 HOURS")
```

---

## Automatic Framing — Atualização Quasi Real-Time

O **Automatic Framing** é a tecnologia que permite ao Direct Lake ler versões atualizadas dos dados automaticamente, sem necessidade de refresh explícito no modelo semântico. Ele é ativado por padrão em Semantic Models sobre Lakehouses do Fabric.

```
Dados chegam no Lakehouse (Spark/Pipeline)
         ↓
  Delta Log atualizado
         ↓
  Semantic Model detecta nova versão (Automatic Framing)
         ↓
  Direct Lake lê nova versão automaticamente
         ↓
  Power BI exibe dados atualizados (latência: segundos)
```

> Para forçar atualização imediata (ex: após OPTIMIZE), use o endpoint REST de refresh do Semantic Model.

---

## Boas Práticas — Gold Layer para Direct Lake

```python
# Estrutura Star Schema recomendada para Direct Lake
# 1. Dimensões pequenas (< 10M linhas) — cargam rápido no VertiPaq
# 2. Fato central com chaves inteiras (evite string joins)
# 3. Sem colunas desnecessárias — cada coluna extra consome memória VertiPaq

spark.sql("""
CREATE OR REPLACE TABLE gold.dim_clientes
USING DELTA
TBLPROPERTIES ('delta.parquet.vorder.enabled' = 'true')
AS
SELECT
    CAST(ROW_NUMBER() OVER (ORDER BY customer_id) AS INT) AS sk_cliente,  -- surrogate key inteira
    customer_id,
    name,
    region,
    segment
FROM silver.silver_clientes
WHERE is_active = true
""")
```

---

## Checklist Direct Lake

- [ ] Todas as tabelas do modelo estão em formato Delta no OneLake
- [ ] V-Order habilitado em todas as tabelas Gold
- [ ] Nenhuma view T-SQL complexa exposta diretamente no modelo semântico
- [ ] `OPTIMIZE` executado após cargas para consolidar arquivos
- [ ] Tipos de dados são escalares (sem arrays/structs não-expandidos)
- [ ] SKU do workspace suporta o volume de linhas das tabelas maiores
- [ ] Surrogate keys inteiras usadas em tabelas Fato (melhor performance VertiPaq)
- [ ] Automatic Framing habilitado (padrão — verificar se não foi desabilitado)

---

## Referências

- [Direct Lake overview](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-overview)
- [Delta Optimization and V-Order in Fabric](https://learn.microsoft.com/en-us/fabric/data-engineering/delta-optimization-and-v-order)
- [Understand Direct Lake query performance](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-understand-storage)
