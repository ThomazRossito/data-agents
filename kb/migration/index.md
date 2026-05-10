# Knowledge Base — Migração de Bancos Relacionais

Base de conhecimento para o agente `migration-expert`. Cobre migração de SQL Server e
PostgreSQL para Databricks (Spark SQL / Delta Lake) e Microsoft Fabric (T-SQL / Lakehouse).

---

## Protocolo KB-First

Antes de qualquer decisão de migração:
1. Consulte esta KB para mapeamentos de tipos e anti-padrões
2. Identifique o destino (Databricks ou Fabric) — **nunca** assume
3. Aplique os mapeamentos canônicos desta KB ao gerar DDL alvo
4. Use `migration_source_*` para validar antes de propor

---

## Fluxo de Migração (5 Fases)

```
ASSESS → ANALYZE → DESIGN → TRANSPILE → RECONCILE
```

| Fase | Objetivo | Tools Principais |
|------|----------|-----------------|
| ASSESS | Inventário completo da fonte | `migration_source_get_schema_summary`, `migration_source_list_tables`, `migration_source_sample_table` |
| ANALYZE | Classificar complexidade, detectar incompatibilidades | `migration_source_describe_table`, `migration_source_list_procedures` |
| DESIGN | Propor estrutura Medallion no destino | KB + raciocínio do agente |
| TRANSPILE | Gerar DDL + jobs PySpark/T-SQL | `migration_source_get_table_ddl`, Write |
| RECONCILE | Validar contagens e integridade | `mcp__databricks__execute_sql` ou `mcp__fabric_sql__fabric_sql_execute` |

---

## Mapeamento de Tipos — SQL Server → Spark SQL (Databricks)

| SQL Server | Spark SQL | Observações |
|-----------|-----------|-------------|
| `INT` | `INT` | Direto |
| `BIGINT` | `BIGINT` | Direto |
| `SMALLINT` | `SMALLINT` | Direto |
| `TINYINT` | `TINYINT` | Direto |
| `BIT` | `BOOLEAN` | |
| `DECIMAL(p,s)` / `NUMERIC(p,s)` | `DECIMAL(p,s)` | Preservar precisão |
| `FLOAT` / `REAL` | `DOUBLE` / `FLOAT` | FLOAT(53)→DOUBLE, FLOAT(24)→FLOAT |
| `MONEY` / `SMALLMONEY` | `DECIMAL(19,4)` / `DECIMAL(10,4)` | Nunca usar FLOAT para valores monetários |
| `CHAR(n)` / `NCHAR(n)` | `STRING` | Spark não tem CHAR fixo |
| `VARCHAR(n)` / `NVARCHAR(n)` | `STRING` | Ignorar comprimento (Spark é unbounded) |
| `VARCHAR(MAX)` / `NVARCHAR(MAX)` | `STRING` | |
| `TEXT` / `NTEXT` | `STRING` | Tipos legados — sempre mapear para STRING |
| `DATETIME` / `DATETIME2` | `TIMESTAMP` | |
| `SMALLDATETIME` | `TIMESTAMP` | Precisão reduzida — documentar |
| `DATE` | `DATE` | Direto |
| `TIME` | `STRING` | Spark SQL não tem TIME nativo — use STRING ou BIGINT (ms) |
| `DATETIMEOFFSET` | `TIMESTAMP` | Perda de timezone offset — documentar |
| `UNIQUEIDENTIFIER` | `STRING` | UUID como string — documentar |
| `BINARY(n)` / `VARBINARY(n)` | `BINARY` | |
| `IMAGE` | `BINARY` | Tipo legado |
| `XML` | `STRING` | XML como string |
| `JSON` (varchar com JSON) | `STRING` / `MAP<STRING,STRING>` | Avaliar caso a caso |
| `GEOGRAPHY` / `GEOMETRY` | `STRING` (WKT) | Sem suporte nativo — converter para WKT |
| `ROWVERSION` / `TIMESTAMP` | `BINARY` | Apenas para auditoria |
| `IDENTITY` | sem equivalente | Documentar como surrogate key — gerar no pipeline |
| `HIERARCHYID` | `STRING` | Sem suporte nativo |

---

## Mapeamento de Tipos — SQL Server → T-SQL Fabric (Lakehouse/Warehouse)

| SQL Server | Fabric T-SQL | Observações |
|-----------|-------------|-------------|
| `INT` | `INT` | Direto |
| `BIGINT` | `BIGINT` | Direto |
| `SMALLINT` | `SMALLINT` | Direto |
| `TINYINT` | `TINYINT` | Direto |
| `BIT` | `BIT` | Direto |
| `DECIMAL(p,s)` | `DECIMAL(p,s)` | Direto |
| `FLOAT` / `REAL` | `FLOAT` / `REAL` | Direto |
| `MONEY` | `DECIMAL(19,4)` | MONEY não suportado no Fabric |
| `VARCHAR(n)` | `VARCHAR(n)` | Direto |
| `NVARCHAR(n)` | `NVARCHAR(n)` | Direto |
| `TEXT` / `NTEXT` | `VARCHAR(MAX)` / `NVARCHAR(MAX)` | Tipos legados — atualizar |
| `DATETIME` | `DATETIME2` | Preferir DATETIME2 no Fabric |
| `DATETIME2` | `DATETIME2` | Direto |
| `DATE` | `DATE` | Direto |
| `TIME` | `TIME` | Direto |
| `DATETIMEOFFSET` | `DATETIMEOFFSET` | Direto |
| `UNIQUEIDENTIFIER` | `UNIQUEIDENTIFIER` | Direto |
| `XML` | `NVARCHAR(MAX)` | XML não suportado como tipo no Fabric |
| `IDENTITY` | `INT IDENTITY(1,1)` | Suportado no Fabric Warehouse |
| `GEOGRAPHY` / `GEOMETRY` | não suportado | Converter para NVARCHAR(MAX) |

---

## Mapeamento de Tipos — PostgreSQL → Spark SQL (Databricks)

| PostgreSQL | Spark SQL | Observações |
|-----------|-----------|-------------|
| `INTEGER` / `INT4` | `INT` | |
| `BIGINT` / `INT8` | `BIGINT` | |
| `SMALLINT` / `INT2` | `SMALLINT` | |
| `SERIAL` / `BIGSERIAL` | `INT` / `BIGINT` | SERIAL é autoincrement — gerar no pipeline |
| `BOOLEAN` | `BOOLEAN` | |
| `NUMERIC(p,s)` / `DECIMAL(p,s)` | `DECIMAL(p,s)` | |
| `REAL` / `FLOAT4` | `FLOAT` | |
| `DOUBLE PRECISION` / `FLOAT8` | `DOUBLE` | |
| `MONEY` | `DECIMAL(19,2)` | |
| `CHAR(n)` / `CHARACTER(n)` | `STRING` | |
| `VARCHAR(n)` / `CHARACTER VARYING(n)` | `STRING` | |
| `TEXT` | `STRING` | |
| `BYTEA` | `BINARY` | |
| `TIMESTAMP` | `TIMESTAMP` | |
| `TIMESTAMPTZ` / `TIMESTAMP WITH TIME ZONE` | `TIMESTAMP` | Timezone normalizado para UTC |
| `DATE` | `DATE` | |
| `TIME` | `STRING` | |
| `TIMETZ` | `STRING` | |
| `INTERVAL` | `STRING` | Sem suporte nativo |
| `UUID` | `STRING` | |
| `JSON` / `JSONB` | `STRING` | Usar `from_json()` no pipeline se necessário |
| `ARRAY` | `ARRAY<tipo>` | Mapear o tipo base |
| `HSTORE` | `MAP<STRING,STRING>` | |
| `INET` / `CIDR` | `STRING` | |
| `MACADDR` | `STRING` | |
| `XML` | `STRING` | |
| `POINT` / `GEOMETRY` (PostGIS) | `STRING` (WKT) | Sem suporte nativo |
| `OID` | `BIGINT` | |
| `ENUM` | `STRING` | Documentar valores possíveis |

---

## Mapeamento de Tipos — PostgreSQL → T-SQL Fabric

| PostgreSQL | Fabric T-SQL | Observações |
|-----------|-------------|-------------|
| `INTEGER` | `INT` | |
| `BIGINT` | `BIGINT` | |
| `SMALLINT` | `SMALLINT` | |
| `SERIAL` | `INT IDENTITY(1,1)` | Apenas no Fabric Warehouse |
| `BOOLEAN` | `BIT` | TRUE=1, FALSE=0 |
| `NUMERIC(p,s)` | `DECIMAL(p,s)` | |
| `REAL` | `REAL` | |
| `DOUBLE PRECISION` | `FLOAT` | |
| `TEXT` | `NVARCHAR(MAX)` | |
| `VARCHAR(n)` | `NVARCHAR(n)` | Preferir NVARCHAR para Unicode |
| `BYTEA` | `VARBINARY(MAX)` | |
| `TIMESTAMP` | `DATETIME2` | |
| `TIMESTAMPTZ` | `DATETIMEOFFSET` | |
| `DATE` | `DATE` | |
| `UUID` | `UNIQUEIDENTIFIER` | |
| `JSON` / `JSONB` | `NVARCHAR(MAX)` | |
| `ARRAY` | não suportado diretamente | Normalizar em tabela separada |
| `ENUM` | `NVARCHAR(50)` | |

---

## Arquitetura Medallion para Tabelas Migradas

### Bronze (ingestão bruta)
- Schema: `bronze`
- Convenção: `bronze.<nome_original>` — sem transformação
- Tipos: preservar ao máximo o original
- Particionamento: `_ingestion_date DATE` (coluna técnica adicionada)
- Delta format: `USING DELTA` (Databricks) / tabela Delta no Lakehouse (Fabric)

### Silver (dados limpos e tipados)
- Schema: `silver`
- Convenção: `silver.<dominio>_<entidade>` — ex: `silver.erp_clientes`
- Transformações: casting para tipos canônicos, deduplicação, validação de PKs
- Chaves: PKs explícitas, FKs como referências documentadas (sem constraints no Delta)

### Gold (agregações e visões de negócio)
- Schema: `gold`
- Convenção: `gold.<dominio>_<agregacao>` — ex: `gold.erp_vendas_mensais`
- Star Schema obrigatório para tabelas fato: `dim_*` + `fato_*`
- Sem JOINs em tempo de query — pré-materializar

---

## Anti-Padrões de Migração

| Código | Anti-Padrão | Correção |
|--------|-------------|---------|
| M01 | Usar `FLOAT`/`DOUBLE` para valores monetários | `DECIMAL(19,4)` |
| M02 | Copiar `IDENTITY` como coluna de dados | Gerar surrogate key no pipeline |
| M03 | Migrar `TEXT`/`NTEXT` sem avaliação de tamanho | Amostrar primeiro — decidir STRING vs BINARY |
| M04 | Ignorar `DATETIMEOFFSET` — perder timezone | Normalizar para UTC e documentar |
| M05 | Criar FKs em Delta Lake | Delta não suporta FK constraints — documentar linhagem |
| M06 | Migrar diretamente para Gold | Sempre passar por Bronze → Silver → Gold |
| M07 | Usar `SELECT *` no job de ingestão | Sempre listar colunas explicitamente |
| M08 | Ignorar `ENUM` do PostgreSQL | Documentar valores possíveis e mapear para STRING com CHECK |
| M09 | Misturar dialeto SQL Server e PostgreSQL no DDL alvo | Um DDL por destino, sem mistura |
| M10 | Transpor stored procedures sem análise de compatibilidade | Classificar por complexidade antes de propor reescrita |

---

## Classificação de Complexidade de Objetos

| Complexidade | Critérios | Ação Recomendada |
|-------------|-----------|-----------------|
| **Simples** | DDL puro, tipos básicos, sem procedures | Transpilação automática pelo agente |
| **Médio** | Views com lógica, procedures simples, tipos especiais | Transpilação + revisão manual |
| **Complexo** | Cursores, procedures com lógica de negócio, triggers | Reescrita manual recomendada — agente gera esqueleto |
| **Bloqueado** | Features sem equivalente (ex: CLR, linked servers) | Documentar como gap — escalar para pipeline-architect |

---

## Checklist de Reconciliação

Após migração, validar obrigatoriamente:

- [ ] Contagem de linhas por tabela (origem vs destino)
- [ ] Soma de colunas numéricas chave (checksums)
- [ ] Amostra de 100 linhas aleatórias comparadas
- [ ] Nulidade: % de nulos por coluna não varia > 1%
- [ ] PKs: sem duplicatas no destino
- [ ] Datas: range min/max preservado
- [ ] Valores monetários: soma total ±0.01%
