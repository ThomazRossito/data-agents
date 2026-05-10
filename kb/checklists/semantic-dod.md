# Definition of Done — Modelos Semânticos e Camada Analítica

Critérios objetivos de aceite para modelos semânticos no Microsoft Fabric (Direct Lake, Import, Composite)
e Metric Views no Databricks. Aplicar ao final de qualquer entrega de modelagem semântica.

---

## Nível 1 — Obrigatório (todos os modelos semânticos)

### Estrutura do Modelo

- [ ] **Tabelas Gold como base** — modelo semântico consome exclusivamente tabelas da camada Gold (nunca Silver ou Bronze diretamente)
- [ ] **Star schema ou snowflake** — pelo menos uma fact table com dimension tables relacionadas
- [ ] **Relacionamentos definidos** — todos os relacionamentos entre tabelas configurados com direção de filtro correta (single / both)
- [ ] **Cardinalidade correta** — Many-to-One, One-to-One ou Many-to-Many documentados e justificados
- [ ] **Tabela de datas** — dimensão de calendário presente e marcada como `Date Table` com coluna de data contínua

### Medidas DAX

- [ ] **Medidas nomeadas** — nome em português/inglês consistente, sem espaços (ex: `Total Receita`, `Margem Bruta %`)
- [ ] **Formatação aplicada** — formato de número/moeda/percentual definido em todas as medidas
- [ ] **Pasta de medidas** — medidas agrupadas em pastas por categoria (`Financeiro`, `Operacional`, `Clientes`)
- [ ] **Sem colunas calculadas desnecessárias** — preferir medidas DAX a colunas calculadas sempre que possível
- [ ] **Medidas base documentadas** — medidas como `Total Vendas`, `Qtd Pedidos` com descrição preenchida

### Qualidade DAX

- [ ] **Testadas no Power BI Desktop ou Fabric** — todas as medidas retornam valores coerentes com dados reais
- [ ] **Sem dependências circulares** — modelo sem erros de dependência circular entre medidas
- [ ] **DIVIDE() em lugar de `/`** — divisões protegidas contra divisão por zero com `DIVIDE(numerator, denominator, 0)`
- [ ] **Sem FILTER com ALLSELECTED() desnecessário** — revisar uso de context modifiers

---

## Nível 2 — Recomendado (modelos em produção / compartilhados)

### Direct Lake (Fabric)

- [ ] **Direct Lake validado** — tabelas estão no OneLake e o modo Direct Lake está ativo (não degradou para Import ou DirectQuery)
- [ ] **Framing configurado** — `EVALUATE INFO.STORAGETABLECOLUMNS()` retorna tabelas com `State = "Ready"`
- [ ] **Aggregations configuradas** — tabelas de agregação pré-construídas para medidas de alto volume (> 100M rows)
- [ ] **Fallback policy definida** — política de fallback para DirectQuery documentada (quando e por quê)

### Row-Level Security (RLS)

- [ ] **RLS planejada** — decisão documentada: model-level RLS ou object-level security no Fabric
- [ ] **Roles testadas** — cada role de RLS testada com usuário real ou via `USERELATIONSHIP + USERPRINCIPALNAME()`
- [ ] **Herdada da Gold** — se RLS está na camada Gold (Unity Catalog), comportamento de herança no modelo verificado

### Genie Space (Databricks)

- [ ] **Genie Space criado** — espaço configurado sobre as tabelas Gold relevantes
- [ ] **Curated questions** — pelo menos 5 perguntas de exemplo cadastradas cobrindo KPIs principais
- [ ] **Trusted assets** — queries SQL de referência cadastradas para KPIs mais consultados
- [ ] **Instruções de contexto** — field descriptions e contexto de negócio preenchidos nas configurações do Space

### Documentação e Metadados

- [ ] **Descrição do modelo** — descrição de negócio preenchida no modelo semântico (Fabric) ou no Genie Space
- [ ] **Descrições de medidas** — description preenchida nas principais medidas (top 20)
- [ ] **Descrições de colunas** — descrição de colunas de dimensão que podem causar ambiguidade
- [ ] **Tabelas e colunas ocultas** — colunas técnicas (IDs, chaves surrogate) marcadas como Hidden

---

## Nível 3 — Para modelos analíticos críticos (> 100 usuários, KPIs executivos)

- [ ] **Performance testada** — queries DAX mais complexas testadas com `DAX Studio` ou `Performance Analyzer`
- [ ] **Model size avaliado** — tamanho do modelo em memória (Import) ou framed tables (Direct Lake) dentro do limite da capacidade
- [ ] **Certified dataset** — dataset certificado no Fabric (Endorsed > Certified) pelo Data Owner
- [ ] **Change management** — processo de aprovação para mudanças em medidas críticas documentado
- [ ] **Review pelo semantic-modeler** — entrega revisada pelo agente especialista antes de go-live
- [ ] **Comunicação aos consumidores** — time de BI / analistas informados sobre novas métricas / mudanças

---

## Metric Views (Databricks)

Para Metric Views no Databricks (camada semântica nativa):

- [ ] **`CREATE METRIC VIEW` executado sem erros** — DDL da Metric View válido
- [ ] **Dimensões e medidas declaradas** — pelo menos uma `MEASURE` e uma `DIMENSION` definidas
- [ ] **Grain definido** — nível de granularidade (`grain`) explicitamente declarado
- [ ] **Permissões** — `GRANT SELECT` para grupos consumidores da Metric View
- [ ] **Integração Genie** — Metric View exposta no Genie Space relevante
- [ ] **Descrições preenchidas** — `COMMENT ON METRIC VIEW` e `COMMENT ON COLUMN` preenchidos

---

## Exemplo de Apresentação ao Usuário

```
✅ Modelo semântico entregue. Checklist DoD — Nível 1 (obrigatório):

[✓] Star schema — 1 fact (fct_vendas) + 4 dims (dim_produto, dim_cliente, dim_data, dim_loja)
[✓] Relacionamentos — todos Many-to-One, filtro Single direction
[✓] Tabela de datas — dim_data marcada como Date Table, 2020–2030
[✓] 12 medidas DAX — formatadas, em pastas, sem dependências circulares
[✓] DIVIDE() — todas as divisões protegidas
[✓] Direct Lake validado — tabelas framed, sem fallback para DirectQuery

⚠️ Pendente para Nível 2 (antes de certificar o dataset):
[ ] RLS — roles para Regional Manager ainda não testadas
[ ] Descrições — 8 medidas sem description preenchida
[ ] Genie Space — curated questions não cadastradas
```

---

## Referências

- `kb/semantic-modeling/` — Direct Lake, DAX, Metric Views, Genie
- `kb/fabric/` — Fabric Lakehouse, Direct Lake, OneLake
- `kb/databricks/` — Unity Catalog, Genie Spaces, Metric Views
- `kb/shared/anti-patterns.md` — H07 (Direct Lake sem cache), H09 (DAX circular), M09
- Agentes: `semantic-modeler`, `sql-expert`, `governance-auditor`
