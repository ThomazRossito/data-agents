# KB: Spark Internals

## Domínio
Internals do Apache Spark: Catalyst Optimizer, plano de execução, narrow vs wide transformations, repartition vs coalesce, AQE, shuffle, memória.

## Quando Consultar
- Debug de query plan lento
- Otimizar shuffles e joins
- Entender por que repartition vs coalesce
- Tuning de AQE, executor memory, broadcast
- Diagnosticar OOM ou stage failures

## Arquivos de Referência Rápida
| Recurso | Arquivo |
|---------|---------|
| Cheatsheet | [quick-reference.md](quick-reference.md) |
| Catalyst Optimizer | [patterns/catalyst-optimizer.md](patterns/catalyst-optimizer.md) |
| Repartition vs Coalesce | [patterns/repartition-vs-coalesce.md](patterns/repartition-vs-coalesce.md) |
| Narrow vs Wide | [patterns/narrow-wide-transformations.md](patterns/narrow-wide-transformations.md) |
| Tuning params | [specs/spark-tuning.yaml](specs/spark-tuning.yaml) |

## Agentes Relacionados
- `spark_expert` — agente primário
- `pipeline_architect` — deploy e infra

## Última Atualização
2026-04-25
