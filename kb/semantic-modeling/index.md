---
mcp_validated: "2026-04-15"
---

# KB: Modelagem Semântica — Índice

**Domínio:** Modelos semânticos, métricas DAX, Direct Lake e consumo analítico.
**Agentes:** semantic-modeler

---

## Conteúdo Disponível

### Conceitos (`concepts/`)

| Arquivo                                  | Conteúdo                                                              |
|------------------------------------------|-----------------------------------------------------------------------|
| `concepts/semantic-model-concepts.md`    | Estrutura de modelos semânticos, relacionamentos, boas práticas       |
| `concepts/dax-concepts.md`               | DAX: medidas vs colunas calculadas, contextos, funções essenciais    |
| `concepts/direct-lake-canonical.md`      | **CANONICAL** Direct Lake: otimização Delta, V-Order, regras Fabric+Databricks |
| `concepts/metric-views-concepts.md`      | Metric Views Databricks: conceitos, Genie, camada semântica          |

### Padrões (`patterns/`)

| Arquivo                                  | Conteúdo                                                              |
|------------------------------------------|-----------------------------------------------------------------------|
| `patterns/semantic-model-patterns.md`    | Power BI modelo completo, relacionamentos, ocultação de colunas      |
| `patterns/dax-patterns.md`               | Medidas DAX completas: YTD, LY, rankings, tabelas de data            |
| `patterns/metric-views-patterns.md`      | SQL Metric Views, CLUSTER BY semântico, integração Genie            |
| `patterns/reporting-patterns.md`         | Dashboards de engenharia, pipeline health, qualidade KPIs            |

---

## Regras de Negócio Críticas

### Direct Lake (Fabric + Power BI)
- Tabelas Gold devem ter `V-Order` habilitado para máxima performance no Direct Lake.
- Colunas de data devem ser do tipo `DATE` (não `TIMESTAMP`) para integração com tabela de calendário.
- Evite colunas com alta cardinalidade desnecessária (ex: IDs longos sem uso analítico).
- Nunca use `PARTITION BY` em tabelas destinadas ao Direct Lake — use `CLUSTER BY`.
- O modelo semântico deve referenciar diretamente as tabelas Gold do Lakehouse.

### Modelos Semânticos (Power BI)
- Defina todas as métricas como Medidas DAX (nunca como colunas calculadas para KPIs).
- Use tabela de calendário dedicada (`dim_data`) com relacionamento para todas as fact_*.
- Configure relacionamentos como Many-to-One (fact → dim), nunca Many-to-Many.
- Oculte colunas de chave estrangeira das fact_* para simplificar a experiência do usuário.
- Documente todas as medidas com descrição e formato de exibição.

### DAX — Boas Práticas
- Use `CALCULATE` com `FILTER` para contextos de filtro explícitos.
- Prefira `SUMX` / `AVERAGEX` para medidas iterativas sobre tabelas grandes.
- Use `DIVIDE(numerador, denominador, 0)` em vez de `/` para evitar erros de divisão por zero.
- Defina a tabela de data como `Mark as Date Table` no modelo semântico.

### Databricks Metric Views
- Use Metric Views para criar uma camada semântica reutilizável sobre tabelas Gold.
- Metric Views suportam `CLUSTER BY` e são consumíveis via Genie (Conversational BI).
- Documente cada métrica com `COMMENT` e unidade de medida.
