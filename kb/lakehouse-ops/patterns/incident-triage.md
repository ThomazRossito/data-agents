# Pattern: Incident Triage

## Árvore de decisão de incidente

```
Pipeline falhou?
├── Erro de código (Python/Spark)?
│   ├── AnalysisException → schema mismatch ou coluna inexistente
│   ├── OutOfMemoryError → repartition ou escalar cluster
│   └── SparkException → ver Task Exception no Spark UI
├── Timeout?
│   ├── Job cluster não iniciou → verificar available_workers / quota
│   └── Task muito longa → ver se há skew de dados
├── Permissão?
│   ├── Databricks → GRANT no Unity Catalog
│   └── Fabric → workspace permissions / capacity role
└── Dados downstream incorretos?
    ├── Verificar audit log do pipeline
    └── DESCRIBE HISTORY <table> → ver última operação
```

## P1 — Dados atrasados (> 50% do SLA)

```
1. Verificar jobs em execução: Databricks Jobs UI ou Fabric Monitor
2. Se travado: cancelar e reiniciar com repair_run (não perder progresso)
3. Se falha recorrente: escalar cluster antes de reiniciar
4. Comunicar stakeholders: impacto downstream (Power BI / relatórios)
```

## P2 — Qualidade degradada

```
1. Rodar expectations manualmente na última partição
2. Verificar se source mudou schema (novo campo, tipo alterado)
3. Se schema drift: adicionar coluna com mergeSchema = true
4. Quarentenar dados ruins antes de propagar para Silver/Gold
```

## P3 — Performance degradada

```
1. spark.sql("DESCRIBE DETAIL <table>") → verificar numFiles
2. Se numFiles > 1000 → executar OPTIMIZE imediatamente
3. Verificar spark.sql.shuffle.partitions (padrão 200, pode ser alto/baixo)
4. Verificar broadcast join: tabelas < 10 MB devem usar broadcast
```

## Rollback de tabela Delta

```python
# Ver histórico de versões
spark.sql("DESCRIBE HISTORY prod.sales_silver.order_curated").show(10, truncate=False)

# Rollback para versão anterior
spark.sql("""
    RESTORE TABLE prod.sales_silver.order_curated
    TO VERSION AS OF 42
""")
```

⚠️ Só funciona se arquivos estiverem dentro do retention period (VACUUM não removeu).

## Checklist pós-incidente

- [ ] Root cause identificado e documentado
- [ ] Fix aplicado e testado em dev/test antes de prod
- [ ] Alerta adicionado para detectar próxima ocorrência cedo
- [ ] Retention/VACUUM ajustado se rollback foi necessário
- [ ] Stakeholders notificados sobre resolução
- [ ] Postmortem registrado (se P1)
