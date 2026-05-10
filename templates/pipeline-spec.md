# Pipeline Spec — {{NOME_DO_PIPELINE}}

> **Template Spec-First:** O Supervisor preenche este template antes de delegar.
> Campos marcados com `[PREENCHER]` devem ser completados com base na requisição
> do usuário e nas KBs consultadas.

---

## 1. Visão Geral

| Campo | Valor |
|-------|-------|
| **Nome** | [PREENCHER] |
| **Objetivo** | [PREENCHER — o que este pipeline resolve] |
| **Plataforma(s)** | [Databricks / Fabric / Cross-Platform] |
| **Ambiente** | [Dev / Staging / Produção] |
| **Owner** | [PREENCHER — time ou pessoa responsável] |
| **Data de Criação** | [DATA] |

---

## 2. Fontes de Dados (Bronze)

| # | Fonte | Formato | Método de Ingestão | Frequência |
|---|-------|---------|-------------------|------------|
| 1 | [PREENCHER] | [CSV/JSON/Parquet/API/Streaming] | [Auto Loader / Eventstream / API REST] | [Batch diário / Streaming contínuo] |
| 2 | [PREENCHER] | | | |

**Regra Constitucional:** Bronze usa Auto Loader (`cloud_files`). NUNCA transformar na Bronze.

---

## 3. Transformações (Silver)

| # | Tabela Silver | Fonte (Bronze) | Transformações | SCD Type |
|---|--------------|----------------|----------------|----------|
| 1 | `silver_[PREENCHER]` | `bronze_[PREENCHER]` | [Limpeza, tipagem, dedup] | [SCD1 / SCD2 via AUTO CDC] |
| 2 | | | | |

**Regra Constitucional:** Silver usa `STREAMING TABLE` + `stream()`. NUNCA `MATERIALIZED VIEW`.
SCD2 usa `AUTO CDC INTO`. NUNCA LAG/LEAD/ROW_NUMBER manual.

---

## 4. Camada Gold (Agregações / Star Schema)

### 4.1 Dimensões

| # | Tabela Dim | Fonte | Tipo |
|---|-----------|-------|------|
| 1 | `dim_data` | SEQUENCE sintético | Geração |
| 2 | `dim_[PREENCHER]` | `silver_[PREENCHER]` | Entidade |

**Regra SS1:** dim_* são entidades independentes. NUNCA derivam de tabelas transacionais.
**Regra SS2:** dim_data usa SEQUENCE + EXPLODE. NUNCA SELECT DISTINCT.

### 4.2 Fatos

| # | Tabela Fact | Dimensões (INNER JOIN) | Métricas |
|---|-----------|----------------------|----------|
| 1 | `fact_[PREENCHER]` | dim_data, dim_[...] | [PREENCHER] |

**Regra SS3:** fact_* faz INNER JOIN com TODAS as dimensões.
**Regra SS5:** Use CLUSTER BY. NUNCA PARTITION BY + ZORDER BY.

---

## 5. Qualidade (Expectations)

| Camada | Tabela | Expectation | Ação |
|--------|--------|-------------|------|
| Silver | `silver_[PREENCHER]` | [Regra de validação] | [expect / expect_or_drop / expect_or_fail] |
| Gold | `fact_[PREENCHER]` | [FK integridade] | expect_or_fail |

**Regra QA3:** Use `@dp.expect_or_fail` para expectations críticas.
**Regra QA5:** Execute data profiling ao ingerir nova fonte.

---

## 6. Consumo Analítico

| Plataforma | Modelo | Otimização |
|-----------|--------|-----------|
| [Fabric Direct Lake / Databricks SQL / Metric Views] | [PREENCHER] | [V-Order / CLUSTER BY] |

---

## 7. Orquestração

| Campo | Valor |
|-------|-------|
| **Tipo** | [DABs / Data Factory / Workflows] |
| **Schedule** | [Cron expression ou trigger] |
| **Retry Policy** | [Retries + backoff] |
| **Alertas** | [Email / Webhook / Teams] |

---

## 8. Plano de Delegação

| Ordem | Agente | Tarefa | Dependências |
|-------|--------|--------|-------------|
| 1 | spark-expert | [PREENCHER] | Nenhuma |
| 2 | data-quality-steward | [PREENCHER] | Etapa 1 |
| 3 | semantic-modeler | [PREENCHER] | Etapa 1 |

---

## 9. Checklist Pré-Delegação

- [ ] KB relevante consultada (Passo 0)
- [ ] Clarity Checkpoint ≥ 3/5 (Passo 0.5)
- [ ] Regras constitucionais aplicáveis identificadas
- [ ] Fontes de dados confirmadas com o usuário
- [ ] Plano apresentado e aprovado pelo usuário (Passo 2)
