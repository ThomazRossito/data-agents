# KB: Workflows Colaborativos Multi-Agente

> Padrões de encadeamento automático entre agentes especialistas. Em vez de
> delegações isoladas, o Supervisor orquestra workflows onde a saída de um
> agente alimenta automaticamente o próximo.

---

## 1. Conceito: Workflow vs Delegação Simples

| Aspecto | Delegação Simples | Workflow Colaborativo |
|---------|-------------------|-----------------------|
| **Estrutura** | Supervisor → Agente → Resultado | Supervisor → A → B → ... → Resultado |
| **Handoff** | Manual | Automático (Supervisor encadeia outputs) |
| **Quando usar** | Tarefas single-domain | Tarefas cross-domain ou multi-etapa |
| **Spec** | Opcional | Obrigatório |

---

## 2. Workflows Pré-Definidos

### WF-01: Pipeline End-to-End (Bronze → Gold)

```
spark_expert → data_quality → supervisor (consolida)
```

**Trigger:** "pipeline completo", "end-to-end", "bronze até gold"
**Etapas:**
1. `spark_expert` — cria DDL + código PySpark (B→S→G)
2. `data_quality` — define expectations + profiling sobre as tabelas
3. Supervisor consolida resultado

**Handoff spark→quality:** DDL das tabelas criadas + código do pipeline

---

### WF-02: Star Schema Design + Implementação

```
sql_expert → spark_expert → data_quality
```

**Trigger:** "star schema", "camada gold", "dimensional", "fato e dimensão"
**Etapas:**
1. `sql_expert` — DDL de dims + fatos (Gold)
2. `spark_expert` — pipeline SDP para popular
3. `data_quality` — expectations + validação FK

**Handoff sql→spark:** DDL completo das tabelas Gold

---

### WF-03: Migração Cross-Platform

```
pipeline_architect → sql_expert → spark_expert
```

**Trigger:** "migrar", "mover para fabric", "mover para databricks", "cross-platform"
**Etapas:**
1. `pipeline_architect` — conectividade + estratégia
2. `sql_expert` — conversão de dialeto SQL
3. `spark_expert` — pipeline de movimentação

**Handoff:** cada agente recebe o output do anterior como contexto

---

### WF-04: Auditoria de Governança

```
naming_guard → supervisor (consolida relatório)
```

**Trigger:** "auditoria", "governança completa", "relatório de compliance", "naming audit"
**Etapas:**
1. `naming_guard` — inventário de violações de nomenclatura
2. Supervisor consolida relatório final com sugestões de rename

---

## 3. Formato de Handoff

Ao delegar para o próximo agente no workflow, incluir:

```
## Contexto do Workflow

- **Workflow:** [WF-XX] [Nome]
- **Etapa atual:** [N] de [Total]
- **Resultado da etapa anterior ([agente]):**
  [Resumo conciso — máximo 500 palavras]
- **Sua tarefa nesta etapa:**
  [Descrição específica]
- **Restrições constitucionais aplicáveis:**
  [Regras relevantes de kb/constitution.md]
```

---

## 4. Detecção Automática

O Supervisor detecta o workflow pelo conteúdo da tarefa:

| Palavras-chave | Workflow |
|---------------|----------|
| pipeline completo, end-to-end, bronze até gold | WF-01 |
| star schema, camada gold, dimensional | WF-02 |
| migrar, mover para fabric, cross-platform | WF-03 |
| auditoria, governança completa, compliance | WF-04 |

Quando detectado, o Supervisor apresenta o plano antes de executar.

---

## 5. Regras de Orquestração

| # | Regra |
|---|-------|
| W1 | Todo workflow deve ter spec antes de iniciar. |
| W2 | Supervisor apresenta plano ao usuário antes de iniciar delegações. |
| W3 | Cada agente recebe o contexto da etapa anterior. |
| W4 | Se um agente falhar, o workflow pausa — Supervisor propõe correção. |
| W5 | Resultados de cada etapa salvos em `output/` para rastreabilidade. |
