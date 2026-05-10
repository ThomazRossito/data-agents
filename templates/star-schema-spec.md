# Star Schema Spec — {{NOME_DO_MODELO}}

> **Template Spec-First:** Especificação completa para design de camada Gold com Star Schema.
> Deve ser preenchido pelo Supervisor e validado contra `kb/constitution.md` §4.2.

---

## 1. Visão Geral

| Campo | Valor |
|-------|-------|
| **Nome do Modelo** | [PREENCHER] |
| **Domínio de Negócio** | [PREENCHER — ex: Vendas, RH, Financeiro] |
| **Plataforma** | [Databricks / Fabric / Ambos] |
| **Consumo** | [Direct Lake / SQL Analytics / Metric Views / Dashboard] |
| **Grain (Granularidade)** | [PREENCHER — ex: uma linha por venda por dia] |

---

## 2. Tabelas Silver de Origem

| # | Tabela Silver | Entidade | Volume Estimado | Frequência de Atualização |
|---|--------------|----------|-----------------|--------------------------|
| 1 | `silver_[PREENCHER]` | [PREENCHER] | [PREENCHER] | [Batch / Streaming] |
| 2 | | | | |

---

## 3. Dimensões

### 3.1 dim_data (Obrigatória)

```sql
-- Geração sintética via SEQUENCE (Regra SS2)
CREATE OR REPLACE TABLE gold.dim_data AS
SELECT
  CAST(data AS INT FORMAT 'yyyyMMdd') AS sk_data,
  data AS data_completa,
  YEAR(data) AS ano,
  MONTH(data) AS mes,
  DAY(data) AS dia,
  DAYOFWEEK(data) AS dia_semana,
  QUARTER(data) AS trimestre
FROM (
  SELECT EXPLODE(SEQUENCE(
    DATE '2020-01-01',
    DATE '2030-12-31',
    INTERVAL 1 DAY
  )) AS data
);
```

### 3.2 Dimensões de Entidade

| # | Tabela Dim | Fonte Silver | Colunas-Chave | SCD Type |
|---|-----------|-------------|---------------|----------|
| 1 | `dim_[PREENCHER]` | `silver_[PREENCHER]` | [PK natural, atributos descritivos] | [SCD1 / SCD2] |
| 2 | | | | |

**Regra SS1:** Cada dim_* tem fonte própria (silver da entidade OU geração sintética).
NUNCA derivar de silver transacional.

---

## 4. Tabela Fato

| Campo | Valor |
|-------|-------|
| **Nome** | `fact_[PREENCHER]` |
| **Grain** | [PREENCHER — ex: uma venda por linha] |
| **Volume estimado** | [PREENCHER] |

### 4.1 Foreign Keys (INNER JOINs obrigatórios — Regra SS3)

| # | Dimensão | FK na Fact | Join Condition |
|---|----------|-----------|----------------|
| 1 | dim_data | sk_data | `fact.data = dim_data.data_completa` |
| 2 | dim_[PREENCHER] | sk_[PREENCHER] | [PREENCHER] |

### 4.2 Métricas

| # | Métrica | Tipo | Expressão |
|---|---------|------|-----------|
| 1 | [PREENCHER] | [SUM / COUNT / AVG] | [PREENCHER] |
| 2 | | | |

---

## 5. DAG Esperado

```
silver_entidade_A ──→ dim_entidade_A ──┐
silver_entidade_B ──→ dim_entidade_B ──┤
SEQUENCE()        ──→ dim_data       ──┤──→ fact_[nome]
silver_transacoes ─────────────────────┘
```

**Regra SS4:** Nenhuma tabela transacional é ancestral direta de uma dim_*.

---

## 6. Otimização Física

| Tabela | CLUSTER BY | V-Order (Fabric) | Formato |
|--------|-----------|-------------------|---------|
| dim_data | sk_data | Sim | Delta |
| dim_[PREENCHER] | sk_[PREENCHER] | Sim | Delta |
| fact_[PREENCHER] | sk_data, sk_[PREENCHER] | Sim | Delta |

**Regra SS5:** CLUSTER BY em Gold. NUNCA PARTITION BY + ZORDER BY.
**Regra FB2:** V-Order obrigatório para Direct Lake no Fabric.

---

## 7. Modelagem Semântica (se aplicável)

| Campo | Valor |
|-------|-------|
| **Tipo** | [Direct Lake / Import / Metric Views] |
| **Medidas DAX** | [Listar medidas principais] |
| **Relacionamentos** | Many-to-One (fact → dim) — NUNCA Many-to-Many |

**Regra SM1:** KPIs como Medidas DAX, não colunas calculadas.
**Regra SM5:** Use DIVIDE(num, den, 0) em vez de `/`.

---

## 8. Plano de Delegação

| Ordem | Agente | Tarefa | Saída |
|-------|--------|--------|-------|
| 1 | sql-expert | DDL das dims e facts | SQL scripts |
| 2 | spark-expert | Pipeline SDP para popular as tabelas | Código PySpark/SQL |
| 3 | data-quality-steward | Expectations nas dims e facts | Validações |
| 4 | semantic-modeler | Modelo semântico + DAX | Definição do modelo |

---

## 9. Checklist de Validação (Passo 4)

- [ ] SS1: Cada dim_* tem fonte própria independente
- [ ] SS2: dim_data usa SEQUENCE + EXPLODE
- [ ] SS3: fact_* faz INNER JOIN com TODAS as dimensões
- [ ] SS4: DAG correto (silver_entidade → dim → fact)
- [ ] SS5: CLUSTER BY em todas as tabelas Gold
- [ ] QA2: Unicidade 100% em surrogate keys
- [ ] SM3: Relacionamentos Many-to-One apenas
