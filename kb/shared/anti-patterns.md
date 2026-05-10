# Anti-Padrões — Biblioteca Centralizada

Referência transversal de anti-padrões de engenharia de dados com severidade classificada.
Todos os agentes devem consultar este arquivo antes de recomendar soluções.

---

## Tabela de Severidade

| Severidade | Ação | Critério |
|------------|------|----------|
| **CRITICAL** | Bloquear imediatamente, não prosseguir | Risco de perda de dados, exposição de PII, destruição irreversível |
| **HIGH** | Alertar usuário, exigir confirmação explícita | Degradação severa de performance, falha silenciosa, custo explosivo |
| **MEDIUM** | Registrar aviso, sugerir correção | Má prática, dívida técnica, inconsistência de naming |

---

## CRITICAL

| ID | Anti-padrão | Domínio | Descrição |
|----|-------------|---------|-----------|
| C01 | `SELECT *` sem WHERE/LIMIT em tabela de produção | SQL, Spark | Full scan que pode processar bilhões de linhas. Sempre especificar colunas e filtros. |
| C02 | `DROP TABLE` / `DROP DATABASE` sem backup verificado | SQL, Databricks, Fabric | Operação irreversível fora do período de versionamento Delta. Exige confirmação explícita + snapshot. |
| C03 | PII sem mascaramento em queries ou outputs | Governança | Exposição de CPF, email, telefone, endereço sem hash/mask viola LGPD e GDPR. |
| C04 | Secrets / tokens hardcoded em código ou notebooks | Todos | API keys, passwords e tokens nunca em código fonte. Usar variáveis de ambiente ou Key Vault. |
| C05 | `TRUNCATE` em tabela silver/gold sem checkpoint | Pipeline | Truncar tabela downstream sem garantir reprocessabilidade do upstream. |
| C06 | Escrever direto em tabela de produção sem staging | Pipeline | Bypass do padrão medallion expõe produção a dados inválidos. |
| C07 | PySpark `collect()` em dataset grande | Spark | Traz todo o dataset para o driver — OOM garantido acima de ~100MB. |

---

## HIGH

| ID | Anti-padrão | Domínio | Descrição |
|----|-------------|---------|-----------|
| H01 | JOIN sem predicado (cross join implícito) | SQL, Spark | Produto cartesiano não intencional multiplica linhas exponencialmente. |
| H02 | Full table scan em tabela particionada sem filtro de partição | SQL, Spark | Ignora partition pruning — lê tudo quando deveria ler uma fração. |
| H03 | Schema sem Delta Lake / versionamento | Spark, Databricks | Arquivos Parquet raw sem versionamento tornam rollback impossível. |
| H04 | Pipeline sem testes de qualidade de dados | Pipeline, dbt | Deploy em produção sem Great Expectations / dbt tests. |
| H05 | `UDF Python` onde SQL nativo resolve | Spark | Python UDFs desativam otimizações Catalyst/Tungsten — preferir SQL built-ins. |
| H06 | Chave de partição com alta cardinalidade (>10k valores) | Spark, Delta | Ex: particionar por `user_id` → milhões de arquivos pequenos = small files problem. |
| H07 | Direct Lake com medida DAX de alta volatilidade sem cache | Fabric, Semantic | Queries DAX em Direct Lake sem cache para agregações pesadas causam timeout. |
| H08 | Pipeline sem idempotência | Pipeline | Reexecução cria duplicatas. Todo pipeline deve ser seguro de re-rodar. |
| H09 | Medida DAX com dependência circular | Semantic | `CALCULATE` referenciando a si mesmo via variável intermediária. |
| H10 | dbt model em prod sem `unique_key` em snapshot | dbt | Snapshot sem chave única → duplicatas silenciosas ao longo do tempo. |
| H11 | `MERGE` Databricks sem `WHEN NOT MATCHED BY SOURCE` controlado | SQL | MERGE incompleto pode deixar registros órfãos ou perder deletes. |
| H12 | Leitura de Unity Catalog sem especificar catálogo.esquema | Databricks | Dependência implícita do schema padrão da sessão — comportamento não determinístico. |

---

## MEDIUM

| ID | Anti-padrão | Domínio | Descrição |
|----|-------------|---------|-----------|
| M01 | Naming inconsistente (camelCase vs snake_case) | Todos | Misturar convenções dificulta discoverability e filtros por prefixo. |
| M02 | Comentários desatualizados ou enganosos | Todos | Comentário que contradiz o código atual é pior que sem comentário. |
| M03 | Sem versionamento de schema no frontmatter da KB | KB | KB sem `version` ou `updated_at` torna difícil detectar obsolescência. |
| M04 | Magic numbers sem constante nomeada | Python, SQL | `LIMIT 1000`, `* 0.8` sem explicação — extrair para constante documentada. |
| M05 | `OPTIMIZE` / `VACUUM` sem monitoramento de duração | Databricks, Fabric | Operações de manutenção podem bloquear leituras — agendar fora de horário de pico. |
| M06 | Delta table sem `TBLPROPERTIES` de retention | Databricks | Sem `delta.logRetentionDuration` explícito, comportamento depende do cluster default. |
| M07 | KQL query sem `limit` explícito | Fabric RTI | Queries Kusto sem limit podem retornar volumes inesperados em Eventhouses grandes. |
| M08 | dbt model sem description no schema.yml | dbt | Sem documentação, `dbt docs generate` produz catálogo incompleto. |
| M09 | Agente delegando para pipeline-architect tarefas de qualidade | Orquestração | Viola S6 da Constituição — qualidade é responsabilidade exclusiva do data-quality-steward. |
| M10 | KB consultada após geração de código | KB | Viola S3 da Constituição — KB-First significa consultar ANTES de planejar, não depois. |

---

## Referências Cruzadas

| Anti-padrão | KB Canônica | Regra da Constituição |
|-------------|-------------|----------------------|
| C03 (PII) | `kb/governance/concepts/pii-concepts.md` | S5 |
| C06 (bypass medallion) | `kb/pipeline-design/concepts/medallion-concepts.md` | S6 |
| H04 (sem testes) | `kb/data-quality/concepts/expectations-concepts.md` | S3 |
| H07 (Direct Lake) | `kb/semantic-modeling/concepts/direct-lake-canonical.md` | S3 |
| M09 (delegação errada) | `kb/constitution.md` | S6 |
| M10 (KB-First violado) | `kb/constitution.md` | S3 |
