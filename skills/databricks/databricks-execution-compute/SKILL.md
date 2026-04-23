---
name: databricks-execution-compute
updated_at: 2026-04-23
source: web_search
---

# Databricks Execution & Compute

Run code on Databricks. Three execution modes—choose based on workload.

## Execution Mode Decision Matrix

| Aspect | [Databricks Connect](references/1-databricks-connect.md) ⭐ | [Serverless Job](references/2-serverless-job.md) | [Interactive Cluster](references/3-interactive-cluster.md) |
|--------|-------------------|----------------|---------------------|
| **Use for** | Spark code (ETL, data gen) | Heavy processing (ML), batch jobs | State across tool calls, Scala/R |
| **Startup** | Instant | ~15-25s (performance-optimized) / 4-6 min (standard mode) | ~5min if stopped |
| **State** | Within Python process | None | Via context_id |
| **Languages** | Python (PySpark) | Python, SQL | Python, Scala, SQL, R |
| **Dependencies** | `withDependencies()` | CLI with environments spec / custom base environments | Install on cluster |

> ⚠️ **Breaking change em DBR 18.1 / databricks-connect 18.1:** O requisito mínimo de `pyarrow` foi elevado de `>=11.0.0` para `>=18.0.0` (SPARK-54849). Atualize o ambiente antes de migrar para DBR 18.1.

> ⚠️ **Breaking change em DBR 17.3 LTS:** A função `input_file_name` não é mais suportada. Use `_metadata.file_name` no lugar.

### Decision Flow

```
Spark-based code? → Databricks Connect (fastest, serverless GA)
  └─ Python 3.12 missing? → Install it + databricks-connect
  └─ Install fails? → Ask user (don't auto-switch modes)

Heavy/long-running (ML) ou batch scheduled? → Serverless Job (independent)
  └─ Latência de cold start crítica? → performance-optimized mode (padrão)
  └─ Custo é prioridade, cold start tolerável? → standard mode (4-6 min, até 70% mais barato)
Need state across calls? → Interactive Cluster (list and ask which one to use)
Scala/R? → Interactive Cluster (list and ask which one to use)
```

### Notas importantes sobre Serverless

- **Requer Unity Catalog habilitado** no workspace. Workspaces legados sem UC não têm acesso a serverless.
- **É o padrão ao criar jobs** via UI (Lakeflow Jobs) para os task types suportados: notebook, Python script, dbt, Python wheel e JAR (JAR em Public Preview).
- Sessões serverless via Databricks Connect **não expiram mais após 10 min de inatividade** (mudança em dezembro 2025).
- Serverless é um produto **versionless**: o runtime é atualizado automaticamente pelo Databricks. Para o runtime atual, consulte as [Serverless compute release notes](https://docs.databricks.com/aws/en/release-notes/serverless/).
- Autoscaling e Photon são **habilitados automaticamente** no serverless — não há configuração manual de instâncias.

## How to Run Code

**Read the reference file for your chosen mode before proceeding.**

### Databricks Connect (no MCP tool, run locally) → [reference](references/1-databricks-connect.md)

> Databricks Connect para Python com serverless compute é **GA** desde outubro 2025 (DBR 17.3 LTS).
> Versão mínima recomendada: `databricks-connect>=17.3`. Para DBR 18.1+, certifique-se de ter `pyarrow>=18.0.0`.

```bash
# Instalar
pip install "databricks-connect>=17.3" "pyarrow>=18.0.0"

# Rodar localmente
python my_spark_script.py
```

### Serverless Job → [reference](references/2-serverless-job.md)

> A partir de janeiro 2026, é possível usar **custom base environments** em tasks Python, Python Wheels e notebooks em serverless jobs.
> Fixe versões de pacotes no `requirements.txt` para evitar resolução inesperada de versões no ambiente serverless.

```python
execute_code(file_path="/path/to/script.py")
```

### Interactive Cluster → [reference](references/3-interactive-cluster.md)

```python
# Check for running clusters first (or use the one instructed)
list_compute(resource="clusters")
# Ask the customer which one to use

# Run code, reuse context_id for follow-up MCP call
result = execute_code(code="...", compute_type="cluster", cluster_id="...")
execute_code(code="...", context_id=result["context_id"], cluster_id=result["cluster_id"])
```

## Runtime Versions de Referência

| Versão | Tipo | Spark | Status |
|--------|------|-------|--------|
| **18.1** | Standard | Spark 4.x | Current serverless runtime |
| **18.0** | Standard | Spark 4.x | GA (jan 2026) |
| **17.3 LTS** | LTS | Spark 4.0.0 | GA (out 2025) — recomendado para clusters |
| **16.4 LTS** | LTS | Spark 3.5.x | GA (mai 2025) |
| **14.3 LTS** | LTS | Spark 3.5.0 | Mínimo suportado para serverless |

> Databricks recomenda sempre usar a versão LTS mais recente para clusters de longa duração (17.3 LTS atualmente). O DBR do cluster deve ser **maior ou igual** à versão do cliente `databricks-connect`.

## MCP Tools

| Tool | For | Purpose |
|------|-----|---------|
| `execute_code` | Serverless, Interactive | Run code remotely |
| `list_compute` | Interactive | List clusters, check status, auto-select running cluster |
| `manage_cluster` | Interactive | Create, start, terminate, delete. **COSTLY:** `start` takes 3-8 min—ask user |
| `manage_sql_warehouse` | SQL | Create, modify, delete SQL warehouses |

## Related Skills

- **[databricks-synthetic-data-gen](../databricks-synthetic-data-gen/SKILL.md)** — Data generation using Spark + Faker
- **[databricks-jobs](../databricks-jobs/SKILL.md)** — Production job orchestration (Lakeflow Jobs)
- **[databricks-dbsql](../databricks-dbsql/SKILL.md)** — SQL warehouse and AI functions
