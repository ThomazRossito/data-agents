# Repartition vs Coalesce

## Regra Principal
- `repartition(n)` = **Wide Transformation** (gera shuffle completo)
- `coalesce(n)` = **Narrow Transformation** (junta partições sem shuffle)

## Quando Usar Repartition
Use `repartition` quando:
- Aumentar número de partições (coalesce não consegue aumentar)
- Balancear dados após skew grave
- Preparar para join de alto volume
- Reparticionar por coluna específica para colocation

```python
# Aumentar partições (força shuffle balanceado)
df.repartition(200)

# Reparticionar por coluna (melhora joins/groupBy na mesma coluna)
df.repartition(100, "customer_id")

# Múltiplas colunas
df.repartition(50, "country", "date")
```

## Quando Usar Coalesce
Use `coalesce` quando:
- Reduzir número de partições **sem shuffle** (mais eficiente)
- Antes de write final (reduz número de arquivos pequenos)
- Após filter pesado que deixou partições sparse

```python
# Reduzir para 10 arquivos antes de salvar
df.filter(...).coalesce(10).write.parquet(path)

# CUIDADO: coalesce pode criar skew se dados já estiverem desbalanceados
```

## Comparativo
| | repartition(n) | coalesce(n) |
|--|----------------|-------------|
| Shuffle | ✓ Sim (Wide) | ✗ Não (Narrow) |
| Pode aumentar partições | ✓ Sim | ✗ Não |
| Balanceamento | ✓ Uniforme | Pode ter skew |
| Custo | Alto (shuffle) | Baixo |
| Stage boundary | ✓ Novo stage | ✗ Mesmo stage |

## Armadilha Comum
```python
# ERRADO: coalesce antes de operação distribuída
df.coalesce(1).groupBy("country").count()  # ← processa tudo em 1 executor!

# CORRETO: coalesce apenas antes de escrita
df.groupBy("country").count().coalesce(10).write.parquet(path)
```

## Relação com Número de Arquivos
```python
# Problema: 1000 partições → 1000 arquivos pequenos
df.write.parquet(path)  # 1000 arquivos de 1 MB

# Solução: coalesce para reduzir antes da escrita
df.coalesce(50).write.parquet(path)  # 50 arquivos de 20 MB
# Ou usar spark.sql.files.maxRecordsPerFile = 1000000
```
