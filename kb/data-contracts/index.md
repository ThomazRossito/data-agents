# KB: Data Contracts — Índice

Base de conhecimento para autoria, governança e evolução de Data Contracts no padrão ODCS.

Agente responsável: `data-contracts-engineer`

---

## Domínios Cobertos

### 1. ODCS — Open Data Contract Standard
- Estrutura de um contrato: `dataContractSpecification`, `info`, `servers`, `models`, `quality`, `servicelevels`
- Campos obrigatórios vs opcionais
- Versionamento semântico de contratos (MAJOR.MINOR.PATCH)
- Publicação e descoberta de contratos no catálogo

### 2. SLAs de Qualidade Contratual
- **Freshness**: `cron`, `maxAge`, `taskType: batch|streaming`
- **Completeness**: percentual de campos NOT NULL por tabela/coluna
- **Validity**: regras de formato (regex, enum, range)
- **Uniqueness**: deduplication rules por natural key
- **Consistency**: referential integrity cross-domain

### 3. Schema Governance & Evolution
- Backward compatibility: novos campos opcionais são safe; remover/renomear campos obrigatórios é breaking
- Forward compatibility: consumidores devem tolerar campos desconhecidos
- Full compatibility: ambas direções
- Uso de `x-deprecated`, `x-replaces` para deprecações graduais

### 4. Breaking Change Management
- Identificar breaking vs non-breaking changes via diff de schema
- Processo de notificação de consumidores (producer-consumer agreement)
- Grace period e estratégia de cutover
- Integração com Unity Catalog (Data Lineage para mapear consumidores afetados)

### 5. Implementação em Plataformas
- **Databricks Unity Catalog**: constraints, tags, column comments como extensão de contratos
- **Microsoft Fabric**: OneLake metadata, Purview sensitivity labels, workspace governance
- **Ferramentas**: `datacontract-cli` para lint/test/export, `dbt-contracts` como extensão

---

## Padrões e Anti-Padrões

### Padrões Recomendados
- Contratos versionados em Git, auditados por CI
- Separação entre contrato de interface (schema + SLA) e implementação (pipeline)
- Data Owner definido por contrato (não por plataforma)
- Testes automatizados de contrato em cada pipeline run

### Anti-Padrões
- Contratos mantidos apenas em documentos (sem versionamento)
- SLA definido sem mecanismo de medição e alerta
- Breaking changes sem notificação antecipada de consumidores
- Contrato duplicado por plataforma (Databricks vs Fabric) sem sincronização

---

## Recursos Externos
- [Open Data Contract Standard](https://bitol-io.github.io/open-data-contract-standard/)
- [datacontract-cli](https://github.com/datacontract/datacontract-cli)
- Databricks Unity Catalog — Data Quality Rules
- Fabric OneLake Catalog — Purview Integration
