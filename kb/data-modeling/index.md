# KB: Data Modeling

## Domínio
Modelagem dimensional (Star Schema, Snowflake), SCD Tipos 1/2/3, formas normais, ACID no Delta Lake, chaves surrogate vs naturais.

## Quando Consultar
- Projetar esquema dimensional (fato/dimensão)
- Implementar SCD Tipo 2 com Delta MERGE
- Decidir entre surrogate key vs natural key
- Normalização vs desnormalização
- ACID transactions no Delta

## Arquivos de Referência Rápida
| Recurso | Arquivo |
|---------|---------|
| Cheatsheet | [quick-reference.md](quick-reference.md) |
| Star Schema | [patterns/star-schema.md](patterns/star-schema.md) |
| SCD Types | [patterns/scd-types.md](patterns/scd-types.md) |
| ACID Transactions | [patterns/acid-transactions.md](patterns/acid-transactions.md) |

## Agentes Relacionados
- `sql_expert` — DDL e queries
- `dbt_expert` — modelos dbt, snapshots SCD
- `spark_expert` — SCD com PySpark MERGE

## Última Atualização
2026-04-25
