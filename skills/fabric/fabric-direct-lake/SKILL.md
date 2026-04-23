---
name: fabric-direct-lake
description: Direct Lake mode para Semantic Models no Fabric — leitura direta de Parquet Delta via OneLake (VertiPaq).
updated_at: 2026-04-23
source: web_search
---

# SKILL: Microsoft Fabric — Direct Lake Mode

> **Fonte:** Microsoft Learn (learn.microsoft.com/fabric/fundamentals/direct-lake-overview), Microsoft Fabric Blog
> **Atualizado:** Abril 2026
> **Uso:** Leia este arquivo ANTES de projetar pipelines com destino Power BI / Semantic Models no Fabric.

---

> ⚠️ **Breaking change em abril 2025 / setembro 2025 — leia antes de continuar:**
>
> 1. **Direct Lake agora tem dois sabores** (desde abril 2025): o modo original foi renomeado para **Direct Lake on SQL** e um novo modo **Direct Lake on OneLake** foi introduzido. O comportamento de fallback, fontes suportadas e forma de criação diferem entre eles. Veja a seção [Dois Sabores de Direct Lake](#dois-sabores-de-direct-lake) abaixo.
> 2. **Default Semantic Models foram descontinuados** a partir de 5 de setembro de 2025: warehouses, lakehouses e databases **não geram mais** um Semantic Model automaticamente. Modelos existentes foram desacoplados e tornaram-se modelos independentes. Todo novo Semantic Model deve ser criado explicitamente.

---

## O que é Direct Lake?

Direct Lake é o modo de acesso dos Semantic Models no Microsoft Fabric. Em vez de importar dados para um cache in-memory (modo Import) ou fazer queries em tempo real ao banco (DirectQuery), o Direct Lake **lê arquivos Parquet Delta diretamente do OneLake** usando o engine VertiPaq do Power BI.

| Modo            | Fonte                            | Velocidade      | Atualização        |
|-----------------|----------------------------------|-----------------|--------------------|
| Import          | Cache in-memory                  | Máxima          | Manual/agendada    |
| DirectQuery     | Banco em tempo real              | Variável        | Tempo real         |
| **Direct Lake** | **OneLake (Parquet Delta)**      | **Import-like** | **Quasi real-time**|

---

## Dois Sabores de Direct Lake

> ⚠️ **Breaking change em abril 2025:** A nomenclatura e a arquitetura do Direct Lake foram divididas em dois modos distintos. O modo original agora se chama **Direct Lake on SQL**. Um novo modo, **Direct Lake on OneLake**, foi introduzido.

Desde abril de 2025, existem **dois sabores** de Direct Lake, com comportamentos significativamente diferentes:

### Direct Lake on SQL (modo original, renomeado)

- O modo que existia antes de abril de 2025. O nome mudou; o comportamento é o mesmo.
- Conecta ao OneLake **via SQL analytics endpoint** do Lakehouse ou Warehouse.
- Suporta **fallback automático para DirectQuery** quando o Direct Lake não consegue ler um Delta table (ex: source é uma SQL view, ou granular access control via SQL está ativo).
- Limitado a **uma única fonte Fabric** por modelo semântico.
- Criado a partir da interface web do Fabric (e depois editável no Power BI Desktop).

### Direct Lake on OneLake (novo modo, public preview)

- Conecta **diretamente aos Delta tables do OneLake**, sem passar pelo SQL analytics endpoint.
- **Sem fallback para DirectQuery** — se uma query não puder usar Direct Lake, ela simplesmente falha. Exige que todos os objetos referenciados sejam Delta tables materializados.
- Suporta **múltiplas fontes Fabric** em um único modelo (ex: tabelas de Lakehouse A + Warehouse B + Lakehouse C no mesmo modelo semântico).
- Suporta **composite models**: Direct Lake on OneLake + tabelas em Import mode de qualquer fonte.
- Criado e gerenciado a partir do **Power BI Desktop** (via OneLake Catalog).
- Segurança: RLS/OLS via SQL endpoint **não se aplica** — use OneLake Security ou RLS definido no próprio modelo semântico.
- **Atenção:** SQL views não materializadas e Lakehouse shortcuts **não são suportados** como fonte no modo OneLake (public preview).

### Tabela comparativa

| Característica                        | Direct Lake on SQL         | Direct Lake on OneLake         |
|---------------------------------------|----------------------------|---------------------------------|
| Passagem pelo SQL endpoint            | ✅ Sim                     | ❌ Não                          |
| Fallback para DirectQuery             | ✅ Sim (configurável)      | ❌ Não (erro se limite atingido)|
| Múltiplas fontes Fabric               | ❌ Não (1 fonte apenas)    | ✅ Sim                          |
| Composite model com Import            | ❌ Não                     | ✅ Sim (public preview)         |
| SQL views como fonte                  | ✅ Sim (via DQ fallback)   | ❌ Não (deve materializar)      |
| Criação                               | Web Fabric                 | Power BI Desktop                |
| RLS via SQL endpoint                  | ✅ Aplicável               | ❌ Não aplicável                |
| Status (abr/2026)                     | GA                         | Public preview                  |

> **Opinião do projeto:** Para novos modelos em ambientes controlados (Gold layer bem estruturada, sem SQL views), prefira **Direct Lake on OneLake** — elimina dependência do SQL endpoint e habilita multi-source. Use **Direct Lake on SQL** quando precisar de views T-SQL, fallback seguro ou governança via SQL endpoint permissions.

---

## Default Semantic Models — Descontinuados

> ⚠️ **Breaking change em setembro 2025:** Desde 5 de setembro de 2025, **Default Semantic Models não são mais criados automaticamente** ao criar warehouses, lakehouses, SQL databases ou mirrored databases.

- Modelos padrão existentes foram **desacoplados** dos itens pai e tornaram-se Semantic Models independentes que requerem um responsável.
- Todo novo Semantic Model deve ser criado **explicitamente** via botão "New Semantic Model" na interface do Fabric ou via Power BI Desktop.
- Opções como "New Report", "Manage default semantic model" e "Automatically update semantic model" foram removidas do contexto de Warehouses e SQL analytics endpoints.

**Impacto nos pipelines do projeto:** Qualquer processo que assumia a existência automática de um Default Semantic Model sobre um Lakehouse deve ser revisado para criar o modelo explicitamente.

---

## Requisitos para Direct Lake

1. **Formato Delta Parquet obrigatório** — tabelas devem estar no formato `.delta` no OneLake.
2. **Armazenamento em OneLake** — tabelas de Lakehouse ou Warehouse nativos do Fabric.
3. **V-Order habilitado** — otimização de escrita que reorganiza os dados para o VertiPaq do Power BI.
4. **Tabelas, não Views (especialmente no modo OneLake)** — views T-SQL complexas causam fallback para DirectQuery no modo SQL, ou erro direto no modo OneLake. Sempre materializar em tabelas Delta.
5. **Schema compatível** — evite tipos não suportados pelo VertiPaq (ex: tipos complexos aninhados sem unnesting). Tipos não mapeáveis são descartados no processo de sync.

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

> **Importante:** O fallback automático para DirectQuery existe apenas no modo **Direct Lake on SQL**. No modo **Direct Lake on OneLake**, queries que excedem guardrails causam **falha de refresh** (modelo não pode ser consultado até que os Delta tables estejam dentro dos limites do SKU) — não há fallback silencioso.

Quando o Direct Lake on SQL não consegue usar o Direct Lake para uma query, ele faz **fallback para DirectQuery automaticamente**. Isso degrada a performance. Causas comuns:

| Causa de Fallback                                | Como Prevenir                                                     |
|--------------------------------------------------|-------------------------------------------------------------------|
| Views T-SQL complexas referenciadas no modelo    | Materializar como tabela Delta — não usar views no modelo         |
| Funções DAX não suportadas no Direct Lake        | Testar com `Analyze in Excel` antes de publicar                   |
| Tabelas com tipos de dados complexos (arrays)    | Fazer unnesting/flatten na camada Silver antes da Gold            |
| Exceder limite de linhas/tamanho do SKU          | Aumentar SKU ou agregar dados na Gold                             |
| Tabela sem V-Order (arquivo mal formatado)       | Executar OPTIMIZE + reescrita com V-Order                         |
| Mais de 1 Delta log file por tabela (fragmentado)| Executar OPTIMIZE para consolidar                                 |
| Modelo publicado via XMLA sem reframe            | Executar refresh/reframe após publicação via XMLA                 |

### Como verificar o modo de armazenamento em uso

```python
# No Power BI Desktop / Service: verificar no Query Diagnostics
# Ou via DAX:
# INFO.STORAGETABLECOLUMNS() retorna "DL" para Direct Lake, "DQ" para DirectQuery

# Para verificar se o modelo é "on SQL" ou "on OneLake":
# - No TMDL view (Power BI Desktop): expressão compartilhada contém "DirectLake" → OneLake
# - No TMDL view: expressão contém "DatabaseQuery" → SQL endpoint
```

---

## Limites por SKU — Guardrails Direct Lake

> **Nota:** Os limites abaixo são guardrails avaliados **por query** (exceto Max model size on disk, que é avaliado no nível do modelo). Consulte sempre [learn.microsoft.com/fabric/fundamentals/direct-lake-overview](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-overview) para valores atualizados — a Microsoft revisa esses números regularmente.

| SKU Fabric | Max linhas por tabela (aprox.) | Comportamento ao exceder (DL/SQL)       | Comportamento ao exceder (DL/OneLake)  |
|------------|--------------------------------|-----------------------------------------|-----------------------------------------|
| F2 / F4    | 300 milhões                    | Fallback automático para DirectQuery    | Refresh falha; modelo indisponível      |
| F8 / F16   | 300 milhões                    | Fallback automático para DirectQuery    | Refresh falha; modelo indisponível      |
| F32 / F64  | 1,5 bilhão                     | Fallback automático para DirectQuery    | Refresh falha; modelo indisponível      |
| F128+      | Ver docs oficiais              | Fallback automático para DirectQuery    | Refresh falha; modelo indisponível      |

> **Atenção para Direct Lake on OneLake:** Não há fallback — se a tabela exceder o guardrail do SKU, o refresh falha e o modelo não pode ser consultado até que os Delta tables sejam otimizados ou o SKU seja aumentado. Monitore proativamente o tamanho das tabelas.

**Script de diagnóstico (verificar saúde das tabelas para Direct Lake):**

```python
# Verificar número de linhas, rowgroups e arquivos por tabela no Lakehouse padrão
# Compare com os limites do seu SKU antes de publicar o modelo

import pandas as pd

tables = spark.sql("SHOW TABLES IN gold").toPandas()
for _, row in tables.iterrows():
    table = f"gold.{row['tableName']}"
    count = spark.sql(f"SELECT COUNT(*) as cnt FROM {table}").collect()[0]['cnt']
    detail = spark.sql(f"DESCRIBE DETAIL {table}").toPandas()
    print(f"{table}: {count:,} linhas | {detail['numFiles'].values[0]} arquivos")
```

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

> Para forçar atualização imediata (ex: após OPTIMIZE), use o endpoint REST de refresh do Semantic Model. No modo Composite (Direct Lake on OneLake + Import), o refresh atualiza também as tabelas Import e executa um schema sync em todas as tabelas.

---

## Composite Semantic Models — Direct Lake + Import (Public Preview)

Desde o início de 2026, é possível criar **Composite Semantic Models** misturando tabelas Direct Lake on OneLake com tabelas em modo Import de qualquer fonte (centenas de conectores do Power Query Online).

**Quando usar:**
- Dimensões pequenas que precisam de **calculated columns** ou hierarquias para Analyze in Excel → mover para Import
- Tabelas de fato grandes → manter em Direct Lake on OneLake
- Dados externos (fora do OneLake) que precisam estar no mesmo modelo

```
# Exemplo de design recomendado para Composite Model
# Fato grande → Direct Lake on OneLake
gold.fato_vendas          → Direct Lake on OneLake

# Dimensão pequena com calculated column → Import
gold.dim_calendario       → Import (com colunas calculadas de DAX)

# Dimensão externa (ex: dados de CRM) → Import
external.dim_clientes_crm → Import (via conector Power Query)
```

> **Opinião do projeto:** O Composite Model é uma alternativa poderosa ao fallback involuntário. Se uma dimensão pequena precisa de recursos não suportados pelo Direct Lake on OneLake (calculated columns, hierarquias MDX), converta-a explicitamente para Import — em vez de depender de fallback implícito do modo SQL.

---

## Boas Práticas — Gold Layer para Direct Lake

```python
# Estrutura Star Schema recomendada para Direct Lake
# 1. Dimensões pequenas (< 10M linhas) — carregam rápido no VertiPaq
# 2. Fato central com chaves inteiras (evite string joins)
# 3. Sem colunas desnecessárias — cada coluna extra consome memória VertiPaq
# 4. Sem SQL views expostas diretamente no modelo (especialmente no modo OneLake)

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
- [ ] Nenhuma view T-SQL complexa exposta diretamente no modelo semântico (crítico no modo OneLake — view sem materialização causa erro)
- [ ] `OPTIMIZE` executado após cargas para consolidar arquivos
- [ ] Tipos de dados são escalares (sem arrays/structs não-expandidos)
- [ ] SKU do workspace suporta o volume de linhas das tabelas maiores (verificar guardrails)
- [ ] Surrogate keys inteiras usadas em tabelas Fato (melhor performance VertiPaq)
- [ ] Automatic Framing habilitado (padrão — verificar se não foi desabilitado)
- [ ] Definido explicitamente qual sabor de Direct Lake usar: **on SQL** ou **on OneLake**
- [ ] Semantic Model criado **explicitamente** (não depender de Default Semantic Model — descontinuado desde set/2025)
- [ ] Se usando Direct Lake on OneLake: RLS/OLS definido no modelo semântico ou via OneLake Security (RLS do SQL endpoint não se aplica)
- [ ] Se usando Direct Lake on OneLake: monitorar guardrails proativamente (sem fallback — falha de refresh ao exceder)

---

## Referências

- [Direct Lake overview](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-overview)
- [Delta Optimization and V-Order in Fabric](https://learn.microsoft.com/en-us/fabric/data-engineering/delta-optimization-and-v-order)
- [Understand Direct Lake query performance](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-understand-storage)
- [Direct Lake on OneLake vs. on SQL — Microsoft docs](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-overview)
- [Sunsetting Default Semantic Models — Microsoft Fabric Blog](https://blog.fabric.microsoft.com/en-us/blog/sunsetting-default-semantic-models-microsoft-fabric)
- [Composite Semantic Models with Direct Lake and Import tables](https://powerbi.microsoft.com/en-us/blog/deep-dive-into-composite-semantic-models-with-direct-lake-and-import-tables/)
- [Power BI Embedded with Direct Lake Mode — GA (março 2025)](https://blog.fabric.microsoft.com/en-US/blog/introducing-power-bi-embedded-with-direct-lake-mode-preview/)
