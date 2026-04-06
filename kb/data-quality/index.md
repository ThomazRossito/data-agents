# KB: Qualidade de Dados — Índice

**Domínio:** Monitoramento, validação e garantia de qualidade de dados.
**Agentes:** data-quality-steward

---

## Conteúdo Disponível

| Arquivo                        | Conteúdo                                                                  |
|--------------------------------|---------------------------------------------------------------------------|
| `expectations-patterns.md`     | Padrões de Data Quality Expectations no Spark e Databricks                |
| `profiling-rules.md`           | Regras de data profiling: completude, unicidade, validade, consistência   |
| `monitoring-alerts.md`         | Configuração de alertas no Fabric Activator e Databricks                  |
| `drift-detection.md`           | Detecção de schema drift e data drift em pipelines de streaming           |
| `sla-contracts.md`             | Contratos de SLA de dados: freshness, completude, latência                |

---

## Regras de Negócio Críticas

### Dimensões de Qualidade (Framework DAMA)
- **Completude**: % de valores não-nulos em colunas obrigatórias. Threshold mínimo: 95%.
- **Unicidade**: Ausência de duplicatas em chaves primárias e naturais. Threshold: 100%.
- **Validade**: Conformidade com domínios de valores (ex: status IN ('ativo', 'inativo')).
- **Consistência**: Coerência entre tabelas relacionadas (ex: FK sempre presente na dimensão).
- **Pontualidade (Freshness)**: Dados devem ser atualizados dentro do SLA definido por tabela.
- **Acurácia**: Conformidade com a fonte de verdade (comparação com sistema de origem).

### Expectations no Spark Declarative Pipelines
- Use `@dp.expect` para expectativas que geram alertas mas não bloqueiam o pipeline.
- Use `@dp.expect_or_drop` para remover registros inválidos sem falhar o pipeline.
- Use `@dp.expect_or_fail` para expectativas críticas que devem bloquear o pipeline.
- Sempre defina expectations nas camadas Silver e Gold (nunca apenas na Bronze).

### Alertas e Monitoramento
- Configure Activator no Fabric para alertas em tempo real baseados em KQL queries.
- Use System Tables do Databricks (`system.access.audit`) para monitorar acessos anômalos.
- Defina thresholds de qualidade por tabela no arquivo `sla-contracts.md`.
- Alertas de qualidade devem ser enviados para o canal de dados do time (Teams/Slack).

### Data Profiling
- Execute profiling completo ao ingerir uma nova fonte de dados.
- Perfil mínimo: contagem de linhas, % nulos por coluna, cardinalidade, min/max/avg.
- Armazene resultados de profiling em tabela de metadados (`catalog.quality.profiling_results`).
- Repita profiling após mudanças de schema ou aumento de volume > 20%.
