# Pattern: Hybrid Architecture (Databricks + Fabric)

## Quando usar arquitetura híbrida
- Time de engenharia usa Databricks (Spark pesado, ML, streaming)
- Time de análise/BI usa Fabric (Power BI, Direct Lake, relatórios)
- Dados precisam estar disponíveis nas duas plataformas sem duplicação

## Abordagens de integração

### 1. Delta Sharing (recomendado — sem cópia)
```
Databricks (produtor) ──Delta Sharing──► Fabric (consumidor)
```
- Cria Share no Unity Catalog com as tabelas autorizadas
- Fabric lê via OneLake Shortcut tipo `DeltaSharing`
- Dados ficam no ADLS do Databricks; Fabric lê remotamente

```sql
-- Databricks: criar share
CREATE SHARE finance_share;
ALTER SHARE finance_share ADD TABLE prod.sales_gold.order_summary;
CREATE RECIPIENT fabric_reader COMMENT 'Fabric workspace';
GRANT SELECT ON SHARE finance_share TO RECIPIENT fabric_reader;
```

### 2. OneLake Mirroring (Fabric lê do ADLS externo)
- Criar shortcut OneLake apontando para ADLS Gen2 onde Databricks grava
- Tabelas Delta do Databricks ficam visíveis no Fabric Lakehouse
- Requisito: tabelas devem estar no formato Delta Parquet (padrão Databricks)

```
ADLS Gen2 (Delta tables escritas pelo Databricks)
    └── OneLake Shortcut → Fabric Lakehouse Tables/
```

### 3. Mirroring de banco externo (Azure SQL, Snowflake, etc.)
- Fabric Mirroring replica dados de fontes externas para OneLake
- Latência: ~1 min (Change Event Streaming GA abr/2026)
- Databricks pode ler do mesmo ADLS via external location

## Decision Matrix

| Cenário | Abordagem |
|---|---|
| Compartilhar tabelas Gold (read-only) com Fabric | Delta Sharing |
| Fabric e Databricks escrevem no mesmo dado | OneLake + Shortcut compartilhado |
| Ingestão de OLTP para ambas as plataformas | Fabric Mirroring → OneLake → Shortcut Databricks |
| ML no Databricks, BI no Fabric | Delta Sharing de feature tables |

## Checklist de Governança Híbrida
- [ ] Dados PII têm masking nas duas plataformas
- [ ] Unity Catalog gerencia lineage do lado Databricks
- [ ] Fabric workspace tem permissões equivalentes ao UC schema
- [ ] Delta Sharing audita acesso via Unity Catalog audit logs
- [ ] Schema evolution compatível (additive only entre plataformas)

## Anti-padrões
- NÃO duplicar dados copiando tabelas inteiras entre plataformas → usar Delta Sharing
- NÃO usar JDBC entre Databricks e Fabric → latência e throttling
- NÃO misturar escritas concorrentes de Databricks e Fabric na mesma tabela
