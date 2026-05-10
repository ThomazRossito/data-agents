# Knowledge Bases (KB) — Data Agents

As Knowledge Bases (KBs) contêm o **conhecimento corporativo e arquitetural** do time de dados.
Elas respondem ao *porquê* — regras de negócio, padrões de arquitetura, contratos de dados e
decisões técnicas do time.

> **Diferença entre KB e Skills:**
> - **KB** = Regras de negócio, padrões arquiteturais, decisões do time. Lida pelo **Supervisor** durante o planejamento.
> - **Skills** = Manuais operacionais de ferramentas específicas (ex: como criar um Delta Live Table). Lida pelos **Agentes Especialistas** durante a execução.

---

## Constituição (`constitution.md`)

O arquivo `kb/constitution.md` é o **documento de autoridade máxima** do sistema multi-agente.
Ele centraliza todas as regras invioláveis extraídas dos domínios de KB, prompts de agentes
e decisões arquiteturais do time. Toda decisão de qualquer agente deve respeitar a Constituição.

O Supervisor carrega a Constituição no início de sessões complexas e a utiliza como referência
na fase de Síntese (Passo 4) para validar os resultados dos agentes especialistas.

---

## Workflows Colaborativos (`collaboration-workflows.md`)

O arquivo `kb/collaboration-workflows.md` define **workflows pré-definidos** para tarefas
que envolvem múltiplos agentes trabalhando em sequência com handoff automático de outputs.
Inclui 4 workflows (WF-01 a WF-04) para pipeline end-to-end, Star Schema, migração
cross-platform e auditoria de governança.

Utilizado em conjunto com os **templates spec-first** em `templates/` para garantir que
tarefas complexas sejam especificadas antes de serem executadas.

---

## Estrutura de Domínios

| Domínio               | Diretório                  | Agentes que Usam                                      |
|-----------------------|----------------------------|-------------------------------------------------------|
| Padrões SQL           | `kb/sql-patterns/`         | sql-expert                                            |
| Padrões Spark         | `kb/spark-patterns/`       | spark-expert, pipeline-architect                      |
| Design de Pipelines   | `kb/pipeline-design/`      | pipeline-architect, spark-expert                      |
| Qualidade de Dados    | `kb/data-quality/`         | data-quality-steward                                  |
| Governança            | `kb/governance/`           | governance-auditor                                    |
| Modelagem Semântica   | `kb/semantic-modeling/`    | semantic-modeler                                      |
| Microsoft Fabric      | `kb/fabric/`               | pipeline-architect, sql-expert, semantic-modeler      |
| Databricks            | `kb/databricks/`           | pipeline-architect, sql-expert, spark-expert          |

---

## Protocolo de Uso (KB-First)

Todo agente deve seguir o protocolo KB-First antes de executar qualquer tarefa:

1. **Scan do índice** — Leia `kb/{domínio}/index.md`, escaneie apenas os títulos (~20 linhas).
2. **Carga sob demanda** — Leia apenas o arquivo específico que corresponde à tarefa.
3. **Skill como fallback** — Se a KB não for suficiente, consulte a Skill operacional correspondente.
4. **MCP como último recurso** — Consulte o MCP apenas se KB + Skill forem insuficientes.
