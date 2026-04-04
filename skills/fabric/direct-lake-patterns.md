---
name: Direct Lake Patterns
description: Padrões de arquitetura e ingestão para modelos Direct Lake no Power BI e Fabric.
---

# Microsoft Fabric: Direct Lake Patterns

## O que é Direct Lake?
Direct Lake é um modo de armazenamento no Power BI e Fabric que lê arquivos Parquet formatados em Delta diretamente do OneLake sem a necessidade de importá-los para um cache de banco de dados nem traduzir consultas via DirectQuery. Combina a velocidade do "Import" com a atualização em tempo real do "DirectQuery".

## Requisitos
*   Os dados **devem** ser formatos em **Delta Parquet** (`.parquet` transacionais).
*   Os arquivos devem estar armazenados no **OneLake** (como Lakehouses ou Warehouses nativos).
*   Não pode conter formatação condicional nem Colunas Calculadas complexas usando DAX caso for violar as "Fallbacks".

## Fallback para DirectQuery
Se a engine tabular achar a consulta ou modelo não ótimo pro Direct Lake, ela degrada para *DirectQuery* para poder resolver. Casos comuns:
1.  Limites de memória excedidos para o SKU usado.
2.  Uso de certas funções na camada de semântica.
3.  Exibição de views complexas T-SQL no SQL endpoint do Lakehouse (cuidado: materializar em tabelas previne o fallback da view).

## Melhor Prática na Ingestão (Medallion)
*   As tabelas da Camada **Silver/Gold** devem ser particionadas otimizadamente (usar `OPTIMIZE` do Spark) e ter `V-Order` habilitado. O *V-Order* compila o parquet num formato amigável ao Power BI (VertiPaq).
*   Config: `spark.conf.set("spark.sql.parquet.vorder.enabled", "true")`

## Código Exemplo PySpark (V-Order habilitado):
```python
# Otimizando tabela Gold para Direct Lake do Power BI
df_gold.write.format("delta").mode("overwrite").save("Tables/VendasGold")

# Manutenção periódica da Tabela (V-Order e otimização de pequenos arquivos)
spark.sql("OPTIMIZE VendasGold")
spark.sql("VACUUM VendasGold RETAIN 168 HOURS")
```
