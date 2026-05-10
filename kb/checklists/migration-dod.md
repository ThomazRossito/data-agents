# Definition of Done — Migração Cross-Platform

Critérios objetivos de aceite para migrações de banco relacional para Databricks ou Microsoft Fabric.
Cobre: SQL Server → Databricks/Fabric, PostgreSQL → Databricks/Fabric.

> **Quando usar:** ao final de qualquer fase de uma migração (assessment, DDL, dados, validação).
> Aplicar por fase — cada fase tem seu próprio DoD parcial.

---

## Fase 1 — Assessment DoD

Antes de iniciar qualquer migração, o assessment deve estar completo:

- [ ] **Inventário de objetos** — todos os objetos do banco mapeados: tabelas, views, procedures, functions, triggers, jobs
- [ ] **Dependências mapeadas** — grafo de dependências entre objetos documentado
- [ ] **Volume estimado** — contagem de rows e tamanho em GB por tabela documentados
- [ ] **Tipos de dados incompatíveis identificados** — lista de tipos sem equivalente direto (ex: `UNIQUEIDENTIFIER`, `XML`, `IMAGE`, `MONEY`)
- [ ] **Features sem suporte mapeadas** — cursors, linked servers, CLR assemblies, T-SQL dialeto-específico
- [ ] **Complexidade de procedures avaliada** — procedures classificadas: simples / moderada / complexa (manual)
- [ ] **SLA de migração definido** — janela de migração, tolerância a downtime, go-live date
- [ ] **Plano de rollback documentado** — como reverter para o banco source se a migração falhar

---

## Fase 2 — DDL e Schema DoD

Ao entregar a transpilação de DDL para o destino (Databricks SQL / Fabric T-SQL):

### Correção

- [ ] **Todas as tabelas transpiladas** — DDL gerado para 100% das tabelas no escopo
- [ ] **Tipos de dados mapeados** — cada tipo source tem equivalente documentado no destino
- [ ] **PKs e UKs preservadas** — constraints de unicidade recriadas (como `CONSTRAINT` ou `ZORDER` em Databricks)
- [ ] **FKs documentadas** — foreign keys anotadas (Databricks não enforça FK, mas devem ser documentadas)
- [ ] **Índices avaliados** — índices críticos mapeados para `ZORDER` (Databricks) ou índices columnstore (Fabric)
- [ ] **Defaults e computed columns** — expressões de default e colunas computadas revisadas e convertidas

### Qualidade

- [ ] **Naming conventions validadas** — nomes de tabelas/colunas em snake_case sem caracteres especiais
- [ ] **Schemas organizados em Medallion** — bronze (raw), silver (cleaned), gold (business) definidos
- [ ] **Delta table properties** — `delta.logRetentionDuration` e particionamento definidos para tabelas > 1GB
- [ ] **DDL revisado por migration-expert** — script de criação executado em ambiente de dev sem erros

---

## Fase 3 — Carga de Dados DoD

Ao concluir a carga inicial dos dados:

### Completude

- [ ] **100% das tabelas carregadas** — todas as tabelas no escopo com dados no destino
- [ ] **Contagem de rows validada** — `COUNT(*)` source == `COUNT(*)` destino para cada tabela
- [ ] **Desvio máximo de 0** — zero registros faltantes (tolerância: 0 para tabelas críticas, < 0.001% para logs)
- [ ] **Timestamps preservados** — `created_at`, `updated_at` com mesmo valor no destino (sem drift de timezone)

### Integridade

- [ ] **Checksum ou hash** — validação de checksum por amostragem em tabelas críticas (≥ 10% dos registros)
- [ ] **Nulos vs vazios** — `NULL` preservado como `NULL`, não convertido para string `"NULL"` ou vazio
- [ ] **Tipos numéricos** — sem perda de precisão em `DECIMAL`/`NUMERIC` após conversão
- [ ] **Encoding de texto** — caracteres especiais (acentos, emoji) preservados sem corrupção

---

## Fase 4 — Validação e Go-Live DoD

Antes de declarar a migração concluída:

### Testes Funcionais

- [ ] **Queries críticas validadas** — top 10 queries do sistema origem executadas no destino com mesmo resultado
- [ ] **Smoke tests passando** — suite de testes de sanidade executados com sucesso
- [ ] **Procedures transpiladas testadas** — cada procedure/function crítica testada com casos de uso reais
- [ ] **Aplicação conectando** — aplicação (se aplicável) conectando ao banco destino em staging

### Performance

- [ ] **Query performance baseline** — top queries do source têm performance igual ou melhor no destino
- [ ] **OPTIMIZE executado** — tabelas Delta otimizadas após carga inicial (`OPTIMIZE ... ZORDER BY`)
- [ ] **Statistics atualizadas** — `ANALYZE TABLE ... COMPUTE STATISTICS` executado

### Governança e Operações

- [ ] **Permissões recriadas** — ACLs equivalentes configuradas no Unity Catalog / Fabric
- [ ] **PII verificada** — colunas com dados pessoais identificadas e mascaradas conforme LGPD
- [ ] **Jobs equivalentes** — SQL Agent Jobs / scheduled procedures recriados como Databricks Jobs ou Data Factory
- [ ] **Monitoramento configurado** — alertas de saúde e SLA configurados no destino
- [ ] **Runbook de produção documentado** — procedimentos de operação (backup, manutenção, rollback) documentados
- [ ] **Janela de cutover planejada** — data, responsáveis e procedimento de cutover documentados

---

## Critérios de Bloqueio (Go/No-Go)

| Critério | Threshold | Decisão |
|----------|-----------|---------|
| Row count match | 100% (crítico) / > 99.999% (logs) | No-Go se abaixo |
| Query performance | ≤ 110% do tempo original | No-Go se acima |
| Smoke tests | 100% passando | No-Go se qualquer falha |
| PII compliance | 100% das colunas PII mascaradas | No-Go se qualquer exposição |
| Rollback testado | Procedimento executado em dry-run | No-Go se não testado |

---

## Referências

- `kb/migration/` — guias de migração SQL Server/PostgreSQL → Databricks/Fabric
- `kb/shared/sql-rules.md` — regras SQL obrigatórias no destino
- `kb/shared/anti-patterns.md` — anti-padrões C02, H01, H08
- `kb/governance/` — LGPD, PII, permissões
- Agentes: `migration-expert`, `sql-expert`, `governance-auditor`, `data-quality-steward`
