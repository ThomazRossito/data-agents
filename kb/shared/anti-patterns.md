# KB: Shared — Anti-patterns

## Anti-patterns SQL

| ❌ Anti-pattern | ✅ Correto |
|----------------|----------|
| `SELECT *` em produção | Listar colunas explicitamente |
| `INSERT OVERWRITE` em Silver+ | `MERGE INTO` |
| Hardcode de datas (`'2024-01-01'`) | Parâmetro ou variável |
| Subquery correlacionada em loop | JOIN ou window function |
| `UNION` sem `ALL` (desduplicação implícita) | `UNION ALL` + dedup explícito |

## Anti-patterns PySpark

| ❌ Anti-pattern | ✅ Correto |
|----------------|----------|
| `.collect()` em DataFrames grandes | `.show()`, `.limit(100).toPandas()` |
| UDF Python em hot path | Spark native functions (`F.regexp_extract`, etc.) |
| `.count()` desnecessário (força scan completo) | Remover ou adiar |
| `repartition(1)` antes de `.write` | `coalesce(n)` com n proporcional ao tamanho |
| Schema inference em CSV/JSON externo | Schema explícito `StructType` |
| `crossJoin` acidental (sem condição join) | Sempre especificar condição |

## Anti-patterns de Nomenclatura

| ❌ Anti-pattern | ✅ Correto |
|----------------|----------|
| `table1`, `df_temp`, `data_final` | Nome descritivo com prefixo de camada |
| `customerId` (camelCase) | `customer_id` (snake_case) |
| `tbl_customer` (prefixo redundante) | `raw_customer` (prefixo de camada) |
| `dt` para coluna de data | `created_date`, `order_date` |
| Mais de 64 caracteres | Abreviar mantendo semântica |

## Anti-patterns de Arquitetura

| ❌ Anti-pattern | ✅ Correto |
|----------------|----------|
| Lógica de negócio em notebook | Módulo Python testável |
| Staging como destino final | Staging é temporário, promover para Bronze |
| Gold sem agregação (passthrough) | Gold = KPIs ou modelo dimensional |
| Pipeline não-idempotente | MERGE ou DELETE-INSERT com chave determinística |
| Múltiplos jobs escrevendo na mesma tabela sem coordenação | Delta concurrent writes ou fila |
