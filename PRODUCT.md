# PRODUCT — Data Agents

> Tese de produto em uma página. O que é, pra quem é, e onde **não** se aplica.

---

## Tese

**Data Agents é um copiloto de engenharia de dados que opera dentro do seu Databricks e do seu Microsoft Fabric — não uma camada de chat que explica o que você já teria que fazer manualmente.**

O diferencial é simples: o assistente **executa** (via MCPs nativos), respeita regras corporativas declarativas (Constituição, KBs, Skills), e orquestra 12 especialistas em vez de jogar tudo em um único agente genérico.

---

## ICP — Para quem é

### Se encaixa se você é…

- **Squad de engenharia de dados** que usa Databricks **ou** Fabric (idealmente ambos) e precisa acelerar tarefas recorrentes: DDLs, pipelines Medallion, validações de qualidade, auditoria de acesso.
- **Consultor/arquiteto de dados** que alterna entre clientes e ambientes e quer um "cockpit" padronizado em vez de reaprender notebooks e workspaces a cada projeto.
- **Time de migração** saindo de SQL Server/PostgreSQL on-prem → Lakehouse. O agente `migration-expert` e o MCP `migration_source` fazem o *assessment* de schema e geram o plano Medallion.
- **Analytics Engineer** com dbt Core que quer um par para revisar models, propor testes e escrever snapshots.

### **Não** se encaixa se você…

- Busca um chatbot generalista (use Claude, ChatGPT ou Copilot diretamente).
- Não tem Databricks nem Fabric. O sistema pode rodar sem credenciais, mas o valor real está nos MCPs de plataforma.
- Espera "clica e deploya" com zero configuração. Existe setup (credenciais, MCPs, KBs) — 10-30 min na primeira vez.
- Precisa de um produto SaaS gerenciado. Isto é um **repositório de referência** para rodar localmente ou em infra própria.

---

## JTBD — O que encurta

| Tarefa | Caminho manual | Com Data Agents |
|--------|----------------|-----------------|
| **Análise de impacto de migração SQL Server → Databricks** (100 tabelas, 30 procedures) | 1-2 dias lendo DDLs, mapeando dependências, estimando esforço | ~30 min: `/migrate` extrai DDLs via MCP, classifica complexidade, sugere desenho Medallion |
| **Criar pipeline Medallion (Bronze → Silver → Gold)** | 2-4h procurando templates, ajustando configs, testando incrementalmente | ~30-60 min: `/pipeline` delega ao `pipeline-architect` com KBs + skills + MCP Databricks/Fabric |
| **Auditoria de acessos e linhagem num workspace Fabric** | 1 dia compilando manualmente de múltiplas UIs | ~1h: `/governance` cruza `fabric_community` lineage + `memory_mcp` knowledge graph |
| **Revisar um dbt model com 200 linhas** | 30-45 min de review humano | ~5 min: `/dbt` aponta falta de testes, sugere snapshots, checa naming |
| **"Qual a diferença entre Delta Lake e Iceberg pro meu caso?"** | 1-2h de leitura de docs e blogs | ~2 min: `/party` traz 3 especialistas em paralelo com opiniões independentes |

A meta não é magia — é **remover o atrito entre intenção e execução** quando a intenção já é clara.

---

## Diferencial vs alternativas

| Alternativa | O que ela faz bem | Onde Data Agents ganha |
|-------------|-------------------|------------------------|
| **Databricks Genie (nativo)** | Conversational BI sobre Unity Catalog | Data Agents **usa o Genie como tool** (MCP `databricks_genie`) e complementa com pipeline, quality, governance, migração — Genie sozinho não escreve PySpark nem faz auditoria |
| **Microsoft Copilot for Fabric** | Q&A integrado no ecossistema MS | Copilot vive na UI do Fabric. Data Agents **cruza Databricks + Fabric** na mesma sessão, algo impossível nos copilots nativos |
| **dbt AI / dbt Copilot** | Sugere SQL e docs dentro do dbt Cloud | `dbt-expert` aqui é **multi-fonte** — consulta context7 para padrões atualizados, PostgreSQL para schemas externos, Fabric para lineage |
| **LangChain / LangGraph multi-agent** | Framework genérico com muita flexibilidade | Data Agents é **opinativo** sobre dados — tem Constituição S1-S7, KBs declarativas, MCPs pré-configurados. Não é um framework, é um produto pronto |
| **ChatGPT / Claude direto** | Excelente pra raciocínio e código | Não toca seu Databricks nem seu Fabric. Data Agents **executa** via MCP; a resposta não é "aqui está o SQL pra você rodar" e sim "rodei, aqui está o resultado" |

**Princípio central:** não somos o melhor chat. Somos o **melhor orquestrador de execução** sobre Databricks e Fabric.

---

## Anti-escopo — O que Data Agents **não** faz

1. **Não é um ChatOps genérico.** Se a pergunta não envolve dados, plataforma ou engenharia, o agente `geral` responde em Haiku e fim — não há MCP, não há orquestração. Para conversa ampla, use Claude direto.
2. **Não é um produto SaaS.** Não há multi-tenant, billing, SLA gerenciado. É um repositório para rodar local ou em infra própria do cliente.
3. **Não faz *fine-tuning* nem treina modelos customizados.** Usa Claude Opus 4.7 e Sonnet 4.6 via API; otimização é via prompt engineering, KBs, caching — não via pesos.
4. **Não escreve em produção sem aprovação humana.** Hooks bloqueiam `DROP`, `DELETE`, `rm -rf`, `git reset --hard` e 18 outros padrões destrutivos. O Supervisor apresenta plano **antes** de delegação múltipla (S4 da Constituição).
5. **Não substitui o *data engineer*.** O sistema acelera os 70% mais repetitivos do trabalho — os 30% de julgamento (desenho de schema crítico, decisão entre arquiteturas, SLA de pipeline) **continuam humanos**.
6. **Não prescreve stack.** Databricks *ou* Fabric *ou* ambos *ou* nenhum — o sistema ativa só o que tem credencial. Não há "modo recomendado" que force uma escolha.

---

## Estado atual (2026-04-18)

- **12 agentes**, **13 MCPs** (6 custom, 7 de terceiros), **1026 testes** ✅.
- Versão `v1.0.0` marcada em `CHANGELOG.md`.
- Próximos marcos: skills nativas Anthropic 2026 (T5.3), evals automáticos (T6.2), `make bootstrap` (T6.3), dashboard de observabilidade (T6.5).

---

*Documento de posicionamento. Atualizar quando o ICP, JTBD ou anti-escopo mudarem — não a cada feature release.*
