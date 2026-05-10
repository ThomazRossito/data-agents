# Templates — Spec-First

> **O que é:** Templates de especificação estruturada que o Supervisor gera e preenche
> **antes** de iniciar delegação de tarefas complexas. Inspirado no padrão Spec-First
> do AgentSpec — "define before you build."

## Quando Usar

O Supervisor deve gerar um spec preenchido (baseado no template relevante) quando:

1. A tarefa envolve **3+ agentes** ou **2+ plataformas**
2. A tarefa cria **infraestrutura nova** (pipelines, tabelas, modelos semânticos)
3. O usuário solicita explicitamente um plano detalhado (`/plan`)
4. O Clarity Checkpoint (Passo 0.5) indica complexidade alta

## Templates Disponíveis

| Template | Quando Usar | Agentes Envolvidos |
|----------|-------------|-------------------|
| `pipeline-spec.md` | Criação/migração de pipelines ETL/ELT | pipeline-architect, spark-expert, data-quality-steward |
| `star-schema-spec.md` | Design de camada Gold com Star Schema | spark-expert, sql-expert, semantic-modeler |
| `cross-platform-spec.md` | Operações Fabric ↔ Databricks | pipeline-architect + agentes de ambas plataformas |

## Fluxo Spec-First

```
Passo 0 (KB-First) → Passo 0.5 (Clarity) → Passo 0.9 (Spec-First)
                                                 ↓
                                        Gerar spec preenchido
                                                 ↓
                                        Apresentar ao usuário (Passo 2)
                                                 ↓
                                        Delegação com referência ao spec
```

O spec é salvo em `output/specs/` e referenciado no prompt de delegação de cada agente.
