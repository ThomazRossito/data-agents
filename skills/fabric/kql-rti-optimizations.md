---
name: KQL e Real-Time Intelligence Optimizations
description: Dicas e guias de uso de Kusto Query Language (KQL) Eventhouses no Fabric.
---

# Fabric Real-Time Intelligence (KQL / Eventhouses)

O Microsoft Fabric provê capacidades de Real-Time Intelligence focadas primariamente no motor Kusto (Data Explorer / Eventhouse). Esta arquitetura não usa bancos transacionais. Usa bancos orientados e injetados de logs na linguagem KQL (Kusto Query Language).

## Padrões de Ingestão
*   **Eventstreams**: A maneira sem código nativa de conectar no Event Hubs nativo ou Kafka externo direto no banco KQL.
*   **Batching vs. Streaming**: KQL provê os dois tipos nativamente. Para telemetria massiva, a latência pode ser setada na política (Update Policy) da tabela para batchear a micro-sec ou ingerir estritamente por fila.

## Boas Práticas (KQL Writing)
*   **Filtre cedo, filtre rápido (Filter Early)**: Traga a limitação temporal na PRIMEIRA LINHA de qualquer query para forçar o predicate pushdown de partição.
*   **Ordem temporal**: O Eventhouse otimiza partições em janelas temporais, sempre busque por partições datadas (`| where ingestion_time() > ago(1d)`).

## Sintaxe Útil e Conversão de SQL para KQL (Exemplos)

### Equivalência Básica
*   **SQL:** `SELECT * FROM Logs WHERE Level = 'Error'`
*   **KQL:** `Logs | where Level == 'Error'`

### Agregações e Agrupamentos (Summarize)
*   **SQL:** `SELECT AppName, COUNT(*) FROM Logs GROUP BY AppName`
*   **KQL:** `Logs | summarize Count=count() by AppName`

### Janelas e Séries Temporais (Bin)
*   O Eventhouse brilha com análise de série temporal em KQL. Agrupamento em janelas de tempo:
    ```kusto
    Logs
    | where TimeGenerated >= ago(7d)
    | summarize count() by bin(TimeGenerated, 1h), AppName
    | render timechart
    ```

## Integração com OneLake
No Fabric, embora o KQL Eventhouse gerencie cache veloz dos logs localmente (Hot Cache), todos os dados sofrem persistência nativa sob a engine do OneLake na forma Parquet (Cold Storage). Isso viabiliza:
1.  Notebooks Spark que batem num endpoint KQL e convertem para DataFrames.
2.  Consultas combinadas do Lakehouse consumindo *Cold Data* provindo dos Eventhouses.
