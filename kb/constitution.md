# Constituição — data-agents-copilot

Documento de autoridade máxima do sistema. Toda decisão de qualquer agente
deve respeitar estas regras. O Supervisor valida os resultados contra a
Constituição na fase de síntese.

---

## 1. Regras de Plataforma

| # | Regra |
|---|-------|
| P1 | Sempre usar **Unity Catalog** (nunca Hive metastore legado). |
| P2 | Preferir **Delta Lake** para todas as tabelas (não Parquet puro). |
| P3 | Usar `dbutils.secrets` ou Azure Key Vault — **nunca hardcodar tokens**. |
| P4 | Toda tabela deve ter schema explícito — **nunca inferir de CSV**. |
| P5 | Usar **managed tables** no Unity Catalog, salvo exceção justificada. |

## 2. Nomenclatura

| # | Regra |
|---|-------|
| N1 | snake_case para tudo: schemas, tabelas, colunas, jobs. |
| N2 | Prefixos por camada: `raw_`, `brz_`, `slv_`, `gld_`, `mrt_`. |
| N3 | PKs com sufixo `_id`. FKs com sufixo `_id`. Booleanos com `_flag`. |
| N4 | Datas com sufixo `_date`. Timestamps com sufixo `_ts`. |
| N5 | Máximo 64 caracteres por nome de objeto. |
| N6 | Sem acentos, sem caracteres especiais além de `_`. |

## 3. Qualidade de Dados

| # | Regra |
|---|-------|
| Q1 | Todo pipeline com dados externos deve ter validação de schema na ingestão. |
| Q2 | Colunas NOT NULL declaradas explicitamente no DDL. |
| Q3 | PKs ou surrogate keys obrigatórias em tabelas Silver e Gold. |
| Q4 | Nenhum `SELECT *` em pipelines de produção. |
| Q5 | Expectativas críticas de qualidade devem gerar alertas, não apenas logs. |

## 4. Segurança & Governança

| # | Regra |
|---|-------|
| S1 | Colunas PII marcadas com tag `pii=true` no Unity Catalog. |
| S2 | Nenhum dado pessoal em logs — mascarar antes de logar. |
| S3 | Row-level security em tabelas Gold com dados sensíveis. |
| S4 | Auditoria de acesso habilitada para catálogos com PII. |
| S5 | LGPD: direito ao esquecimento implementável via `DELETE` em Delta. |

## 5. Pipeline & Orquestração

| # | Regra |
|---|-------|
| O1 | Pipelines de ingestão devem ser **idempotentes** (reprocessar sem duplicar). |
| O2 | Usar `MERGE INTO` (não `INSERT OVERWRITE`) para SCD. |
| O3 | Checkpoints obrigatórios em Structured Streaming. |
| O4 | Particionamento por data em tabelas > 100M linhas. |
| O5 | Testes de integridade antes de promover para camada superior. |

## 6. Código

| # | Regra |
|---|-------|
| C1 | Type hints obrigatórios em código Python de produção. |
| C2 | Nenhuma lógica de negócio em notebooks — usar módulos Python. |
| C3 | Testes unitários com cobertura mínima 80% para transformações. |
| C4 | Sem `collect()` em DataFrames grandes — usar `show()`, `toPandas()` só em dev. |
| C5 | Documentar decisões de design em `output/prd/` ou `output/specs/`. |

## 7. Protocolo KB-First

Todo agente deve seguir antes de executar qualquer tarefa:

1. **Scan** — leia `kb/{domínio}/index.md`, escaneie só os títulos
2. **Carga sob demanda** — leia apenas o arquivo específico relevante à tarefa
3. **Skill como fallback** — se KB insuficiente, consulte a Skill operacional
4. **MCP como último recurso** — apenas se KB + Skill forem insuficientes
