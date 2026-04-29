# Narrow vs Wide Transformations

## Definição
- **Narrow**: cada partição de output depende de no máximo uma partição de input. Sem troca de dados entre executores.
- **Wide**: partições de output dependem de múltiplas partições de input. Requer shuffle (troca de dados pela rede).

## Narrow Transformations
| Operação | Tipo |
|----------|------|
| `map` / `flatMap` | Narrow |
| `filter` / `where` | Narrow |
| `select` / `withColumn` | Narrow |
| `union` / `unionAll` | Narrow |
| `coalesce` | Narrow |
| `sample` | Narrow |
| `mapPartitions` | Narrow |

Narrow não criam novo Stage no DAG.

## Wide Transformations (geram shuffle)
| Operação | Tipo |
|----------|------|
| `groupBy` + `agg` | Wide |
| `join` (Sort Merge Join) | Wide |
| `distinct` | Wide |
| `repartition` | Wide |
| `sortBy` / `orderBy` | Wide |
| `reduceByKey` / `groupByKey` | Wide |
| `pivot` | Wide |
| window functions com `partitionBy` diferente | Wide |

Wide criam novo Stage boundary — materialização em disco intermediária.

## Stage Boundaries e Implicações
```
Stage 1 (Narrow): read → filter → select → map
       ↓ Shuffle Write
Stage 2 (Narrow): map → groupBy
       ↓ Shuffle Read
Stage 3: agg → write
```
- Falha em qualquer task de stage → retry somente do stage (não do job todo)
- Shuffle materializa em disco → risco de disk spill com dados grandes

## JOIN pode ser Narrow?
Broadcast Hash Join é Narrow: a tabela pequena é replicada (broadcast) para todos os executores, eliminando shuffle.

```python
from pyspark.sql.functions import broadcast
df_large.join(broadcast(df_small), "key")
# → Narrow (sem shuffle da tabela grande)
```

## Diagnóstico no Spark UI
- **Stage com Input/Output muito diferente**: provável shuffle
- **Linhas "Shuffle Read"/"Shuffle Write"**: confirma Wide transformation
- **Task com duração muito diferente dentro do stage**: data skew em Wide op
