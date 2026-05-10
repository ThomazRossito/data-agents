# Definition of Done — Pipelines ETL/ELT

Critérios objetivos de aceite para pipelines de dados (Databricks DLT, Jobs, Fabric Data Factory).
Um pipeline só está **Done** quando todos os itens abaixo estão marcados.

> **Quando usar:** ao final de qualquer tarefa de construção ou modificação de pipeline.
> O agente deve apresentar este checklist ao usuário antes de declarar a entrega concluída.

---

## Nível 1 — Obrigatório (todos os pipelines)

### Código e Qualidade

- [ ] **Idempotência verificada** — reexecutar o pipeline não cria duplicatas nem corrompe dados
- [ ] **Tratamento de erros** — falhas em tabelas individuais não derrubam o pipeline inteiro (ex: `expect_or_drop` em DLT, try/except em Python)
- [ ] **Sem secrets hardcoded** — credenciais em Databricks Secrets ou Key Vault, nunca no código
- [ ] **Sem `SELECT *`** — colunas explicitamente nomeadas em transformações Silver/Gold
- [ ] **Schema declarado** — schema das tabelas de saída definido explicitamente, não inferido
- [ ] **Nomes de tabelas totalmente qualificados** — `catalogo.esquema.tabela` em todo o código Databricks

### Dados e Validação

- [ ] **Testes de contagem** — contagem de registros de saída validada contra expectativa (`>= N` ou `delta < X%` vs fonte)
- [ ] **Valores nulos** — colunas obrigatórias verificadas (`expect_or_drop` ou `assert`)
- [ ] **Duplicatas** — chave primária validada como única nas tabelas Silver/Gold
- [ ] **Tipos de dados** — colunas de data/timestamp com fuso horário explícito

### Documentação

- [ ] **Comentário de cabeçalho** — propósito, fonte, destino e dono do pipeline documentados no notebook/script
- [ ] **Tabelas comentadas** — `COMMENT ON TABLE` ou `table_properties` com descrição no Unity Catalog / Fabric

### Observabilidade

- [ ] **Logging estruturado** — início, fim e contagem de registros logados por stage
- [ ] **Alerta de falha configurado** — email ou webhook em caso de falha do Job/DLT

---

## Nível 2 — Recomendado (pipelines de produção)

### Performance

- [ ] **Particionamento definido** — coluna de partição adequada (data, região) para tabelas > 10GB
- [ ] **`OPTIMIZE` e `ZORDER` planejados** — estratégia de compactação documentada para tabelas críticas
- [ ] **Compute sizing documentado** — tamanho do cluster justificado (DBU/hora estimado)
- [ ] **SLA de execução definido** — tempo máximo de execução documentado (ex: "deve concluir em < 2h")

### Governança

- [ ] **Linhagem registrada** — tabelas de entrada e saída documentadas (manual ou via Unity Catalog lineage)
- [ ] **PII identificada** — colunas com dados pessoais mascaradas ou documentadas com justificativa
- [ ] **Política de retenção** — `delta.logRetentionDuration` e `delta.deletedFileRetentionDuration` definidos
- [ ] **Política de acesso** — `GRANT SELECT` mínimo para os grupos que consomem as tabelas

### Confiabilidade

- [ ] **Checkpoint configurado** — Auto Loader ou structured streaming com checkpoint path em storage persistente
- [ ] **Retry policy** — job configurado com retry em caso de falha transitória (ex: 2 retries, 5min de delay)
- [ ] **Runbook de incident** — procedimento de rollback documentado (ex: `RESTORE TABLE ... TO VERSION AS OF N`)

---

## Nível 3 — Para pipelines críticos (SLA < 4h, dados de negócio críticos)

- [ ] **Teste de carga** — pipeline testado com volume real ou representativo de produção
- [ ] **Smoke test automatizado** — job de validação pós-execução verifica sanidade dos dados
- [ ] **Monitoramento de drift** — alerta se distribuição de valores muda > threshold (ex: % de nulos subiu > 5%)
- [ ] **Review por data-quality-steward** — entrega revisada por agente especialista em qualidade
- [ ] **Review de governança** — se pipeline processa PII, revisado pelo governance-auditor

---

## Exemplo de Apresentação ao Usuário

```
✅ Pipeline construído. Checklist DoD — Nível 1 (obrigatório):

[✓] Idempotência — testada com reexecução, 0 duplicatas
[✓] Tratamento de erros — expect_or_drop em todas as tabelas DLT
[✓] Sem secrets hardcoded — usando dbutils.secrets
[✓] Schema declarado — schema explícito em todas as tabelas de saída
[✓] Testes de contagem — output: 1.247.832 linhas (esperado: ~1.2M)
[✓] Logging — início/fim e contagem por stage logados
[✓] Alerta — email configurado para data-team@empresa.com

⚠️ Pendente (Nível 2, para before go-live):
[ ] OPTIMIZE/ZORDER — recomendar após 30 dias de dados acumulados
[ ] PII review — tabela `silver_customers` contém `email` → encaminhar para governance-auditor
```

---

## Referências

- `kb/pipeline-design/` — padrões Medallion, ETL/ELT, orquestração
- `kb/data-quality/` — Great Expectations, profiling, SLA
- `kb/shared/sql-rules.md` — regras SQL obrigatórias
- `kb/shared/anti-patterns.md` — anti-padrões H04, H08, C05, C06
- Agentes: `pipeline-architect`, `spark-expert`, `data-quality-steward`
