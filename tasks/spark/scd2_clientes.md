---
agent: spark_expert
output: output/pipelines/scd2_clientes.md
---

Implemente SCD Type 2 em PySpark com Delta Lake para a tabela `silver.dim_clientes`.

Requisitos:
- Fonte: `bronze.raw_clientes` (snapshot diário completo)
- Colunas de rastreamento: `valid_from`, `valid_to`, `is_current`, `row_hash`
- Campos que disparam mudança: nome, email, endereco, segmento
- Usar `MERGE INTO` nativo do Delta Lake
- Compatível com Unity Catalog (main.silver.dim_clientes)
- Incluir função helper `compute_row_hash(*cols)` com SHA-256
