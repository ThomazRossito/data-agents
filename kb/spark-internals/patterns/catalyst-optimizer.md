# Catalyst Optimizer — 6 Fases

O Catalyst Optimizer é o engine de otimização de queries do Spark. Transforma código de alto nível (SQL/DataFrame API) em código JVM otimizado em 6 fases:

## Fase 1: Parsing (Unresolved Logical Plan)
- Input: SQL string ou chamadas DataFrame API
- Output: árvore de expressões com referências não resolvidas (nomes de colunas/tabelas como strings)
- Erros aqui: sintaxe inválida

## Fase 2: Analysis (Resolved Logical Plan)
- Consulta o **Catalog**: valida existência de tabelas, permissões, resolvimento de tipos
- Resolve colunas para seus tipos reais
- Erros aqui: AnalysisException (coluna não existe, tipo incompatível)

## Fase 3: Logical Optimization (Optimized Logical Plan)
Aplica regras de reescrita:
- **Filter Pushdown**: `WHERE` movido para próximo da leitura
- **Column Pruning**: lê apenas colunas necessárias (aproveita Parquet column-oriented)
- **Constant Folding**: `1 + 1` → `2` em tempo de compilação
- **Subquery Decorrelation**: subqueries correlacionadas reescritas como joins

```python
# Ver plano lógico otimizado
df.explain(mode="formatted")
# ou
df.explain(True)  # mostra todos os estágios
```

## Fase 4: Physical Planning (Physical Plans)
- Gera múltiplos Physical Plans a partir do Optimized Logical Plan
- Escolhe algoritmo de JOIN: BroadcastHashJoin, SortMergeJoin, ShuffleHashJoin
- AQE pode overridar aqui em runtime

## Fase 5: Cost-Based Optimization (CBO)
- Usa statistics de tabelas (row count, column stats) para escolher melhor Physical Plan
- Requer ANALYZE TABLE para funcionar bem

```sql
ANALYZE TABLE minha_tabela COMPUTE STATISTICS FOR ALL COLUMNS;
```

## Fase 6: Code Generation (Tungsten)
- Gera bytecode JVM específico por query (Whole-Stage Code Generation)
- Elimina overhead de chamadas genéricas de método
- Usa operações SIMD via Unsafe memory
- Resultado: performance próxima de código escrito à mão em C

## Debug do Catalyst
```python
# Ver JSON detalhado do plano
print(df._jdf.queryExecution().toString())

# Verificar se scan foi pushdown
df.explain("extended")  # mostra Parsed, Analyzed, Optimized, Physical
```
