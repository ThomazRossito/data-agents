# Spark Internals Quick Reference

## Plan Stages
| Stage | O que acontece |
|-------|---------------|
| 1. Parsing | SQL/DataFrame → Unresolved Logical Plan |
| 2. Analysis | Resolve nomes (Catalog: permissões, schemas) |
| 3. Logical Optimization | Filter pushdown, constant folding, predicate pushdown |
| 4. Physical Planning | Geração de Physical Plans (HashJoin vs SortMergeJoin) |
| 5. Cost-Based Selection | Best Physical Plan via statistics / CBO |
| 6. Code Generation | Tungsten: bytecode JVM gerado por query |

## Narrow vs Wide Transformations
| Tipo | Definição | Shuffle | Exemplos |
|------|-----------|---------|---------|
| **Narrow** | 1 input partition → 1 output partition | ✗ | map, filter, union, coalesce |
| **Wide** | N input partitions → M output partitions | ✓ | groupBy, join (SMJ), repartition, distinct |

## Repartition vs Coalesce
| Operação | Shuffle | Balanceamento | Quando Usar |
|----------|---------|---------------|------------|
| `repartition(n)` | ✓ Wide | Igual | Aumentar partições, balancear skew |
| `coalesce(n)` | ✗ Narrow | Pode skew | Reduzir partições (ex: após filter pesado) |

## Tipos de Join
| Join Type | Quando Usa | Shuffle |
|-----------|------------|---------|
| Broadcast Hash Join | Tabela pequena (<= autoBroadcastJoin threshold) | ✗ |
| Sort Merge Join | Ambas grandes | ✓ |
| Shuffle Hash Join | Uma média, outra grande | ✓ (partial) |
| Cartesian | Cross join explícito | ✓ Muito caro |

## AQE (Adaptive Query Execution) — Configs Chave
```
spark.sql.adaptive.enabled = true (default DBR 10+)
spark.sql.adaptive.coalescePartitions.enabled = true
spark.sql.adaptive.skewJoin.enabled = true
spark.sql.adaptive.localShuffleReader.enabled = true
```

## Shuffle Partitions
```
spark.sql.shuffle.partitions = 200 (default — frequentemente errado)
Regra: ~128 MB por partição após shuffle
AQE ajusta automaticamente se habilitado
```

## Memory Fractions
```
spark.executor.memory = total heap
spark.memory.fraction = 0.6 (60% de execution + storage)
spark.memory.storageFraction = 0.5 (metade de 0.6 = 30% para cache)
User memory = 40% do total
```
