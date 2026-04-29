# Data Quality Quick Reference

> Tabelas de lookup rápido. Para exemplos completos ver arquivos linkados.

## DQX vs Great Expectations

| Critério | Databricks DQX | Great Expectations |
|----------|---------------|-------------------|
| Integração Databricks | Nativa, zero setup | Requer GE Cloud ou setup local |
| Definição de expectativas | Python API / YAML | Python + GE Suite |
| Relatório visual | Databricks UI | Data Docs (HTML) |
| Streaming support | Sim (DLT constraints) | Limitado |
| Quando usar | Pipelines DLT/LakeFlow | Projetos multi-cloud ou legado |

## SLAs por Camada

| Camada | Completude | Consistência | Freshness |
|--------|-----------|-------------|----------|
| Bronze | ≥ 99% | Sem duplicatas na PK técnica | < 1h do source |
| Silver | ≥ 99.5% | Sem duplicatas na PK natural | < 2h |
| Gold | ≥ 99.9% | Joins validados, regras de negócio aplicadas | < 4h |

## Profiling Checklist

| Verificação | Threshold de alerta | Ferramenta |
|------------|--------------------|-----------| 
| % nulos por coluna | > 5% em coluna NOT NULL | DQX / GE |
| Cardinalidade de enum | Valor fora do domínio aceito | accepted_values |
| Outliers numéricos | > 3σ da média histórica | PySpark stats |
| Schema drift | Nova coluna não esperada | Delta schema evolution log |
| Duplicatas por PK | > 0 em Silver/Gold | ROW_NUMBER dedup check |

## Decision Matrix

| Cenário | Ação |
|---------|------|
| Nulo em coluna crítica (Bronze) | Quarentena → dead letter |
| Nulo em coluna crítica (Silver) | Falha + alerta + não promover |
| Schema drift inesperado | Alerta + revisão manual antes de merge |
| Duplicata na PK (Silver) | Dedup por timestamp + log |
| Métrica de qualidade < SLA | Alerta no canal de dados + não servir Gold |

## Common Pitfalls

| Evite | Prefira |
|-------|---------|
| Validar schema apenas em Bronze | Validar em todas as camadas |
| Alerta sem ação automática | Configurar `on_failure_callback` |
| Expectativas manuais sem versionamento | `schema.yml` no dbt ou YAML versionado |
| Ignorar NULL em join keys | Checar NULL antes de join |

## Related

| Tópico | Arquivo |
|--------|---------|
| DQX expectations (código) | expectations.md |
| Profiling com PySpark | profiling.md |
