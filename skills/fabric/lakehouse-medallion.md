---
name: Medallion Architecture on Lakehouse
description: Padrões de engenharia para criar a arquitetura Medalhão no Microsoft Fabric.
---

# Microsoft Fabric Lakehouse: Medallion Architecture

A arquitetura Medalhão (Bronze, Silver, Gold) é a abordagem recomendada no Microsoft Fabric para garantir a confiabilidade e escalabilidade dos pipelines lógicos.

## Camada Bronze (Raw)
*   **Armazenamento**: Área de staging para dados na sua estrutura original (JSON, CSV, Parquet).
*   **Ferramentas no Fabric**: Pipelines de Integração de Dados usando a Copy Activity para mover dados locais/nuvens (S3/ADLS) para a pasta `Files` ou `Tables` (não refinadas) do Lakehouse.
*   **Recomendação**: Adicionar colunas de metadata, como data de carga e sistema fonte. Não force tipos (`CAST`) neste nível.

## Camada Silver (Cleansed/Conformed)
*   **Armazenamento**: Tabelas Delta puras (no OneLake Lakehouse -> `Tables`).
*   **Processamento**: Fabric Notebooks (PySpark) ou Fabric Dataflows Gen2.
*   **Atividades**: Limpeza, padronização de tipos de dados (Datas, Strings), desduplicação (`dropDuplicates`), e junções preliminares.
*   **Upsert**: Implemente MERGE nas tabelas Silver para manter o histórico das transações, usando a API Delta nativa.

## Camada Gold (Business/Curated)
*   **Armazenamento**: Star schema em Tabelas Delta (Fato e Dimensão).
*   **Processamento**: T-SQL via Fabric Data Warehouse (se exigido por time de SQL puro) ou Spark SQL via Lakehouse.
*   **Atividades**: Otimizada explicitamente para relatórios. Agregações e KPIs.
*   **Consumo (Direct Lake)**: Como os dados Gold estão no formato Delta Parquet no OneLake, o modelo semântico predefinido do Fabric fará análises extremamente rápidas através do *Direct Lake*.

## Snippet Útil (PySpark MERGE - Silver Layer)
```python
from delta.tables import DeltaTable

# Path do Storage OneLake
silver_path = "abfss://WorkspaceID@onelake.dfs.fabric.microsoft.com/LakehouseID.Lakehouse/Tables/SilverClientes"

if delta.DeltaTable.isDeltaTable(spark, silver_path):
    dt = DeltaTable.forPath(spark, silver_path)
    dt.alias("target").merge(
        source=df_new.alias("source"),
        condition="target.ClientID = source.ClientID"
    ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
else:
    df_new.write.format("delta").save(silver_path)
```
