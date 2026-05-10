# Cross-Platform Spec — {{NOME_DA_OPERAÇÃO}}

> **Template Spec-First:** Especificação para operações que envolvem Databricks E Fabric.
> Deve ser preenchido pelo Supervisor e validado contra `kb/constitution.md` §5.

---

## 1. Visão Geral

| Campo | Valor |
|-------|-------|
| **Nome** | [PREENCHER] |
| **Objetivo** | [PREENCHER — o que esta operação cross-platform resolve] |
| **Direção** | [Databricks → Fabric / Fabric → Databricks / Bidirecional] |
| **Ambiente** | [Dev / Staging / Produção] |
| **Tipo** | [Migração / Sincronização contínua / Compartilhamento read-only] |

---

## 2. Inventário de Ativos

### 2.1 Origem

| # | Ativo | Plataforma | Localização | Formato | Volume |
|---|-------|-----------|-------------|---------|--------|
| 1 | [PREENCHER] | [Databricks/Fabric] | [catalog.schema.table / Lakehouse/Table] | Delta | [PREENCHER] |

### 2.2 Destino

| # | Ativo | Plataforma | Localização Destino | Formato | Uso Final |
|---|-------|-----------|-------------------|---------|----------|
| 1 | [PREENCHER] | [Databricks/Fabric] | [catalog.schema.table / Lakehouse/Table] | Delta | [Pipeline / Analytics / Direct Lake] |

---

## 3. Estratégia de Conectividade

| Opção | Quando Usar | Selecionada? |
|-------|-------------|-------------|
| **ABFSS Paths Compartilhados** | Mesma storage account (Azure) | [ ] |
| **OneLake Shortcuts** | Acesso read-only sem movimentação (zero-copy) | [ ] |
| **Mirroring** | Sincronização automática contínua Fabric → Databricks | [ ] |
| **OneLake API (export/upload)** | Sem storage compartilhado; batch | [ ] |
| **Unity Catalog Federation** | Consulta cross-catalog sem cópia | [ ] |

**Regra Cross-Platform:** Estratégia preferida é ABFSS paths compartilhados.
Alternativa: OneLake Shortcuts para zero-copy.

---

## 4. Mapeamento de Camadas

| Camada Origem | Plataforma Origem | Camada Destino | Plataforma Destino | Transformação? |
|--------------|-------------------|----------------|-------------------|---------------|
| Bronze | [PREENCHER] | Bronze | [PREENCHER] | Não (raw) |
| Silver | [PREENCHER] | Silver | [PREENCHER] | [Reconversão de tipos?] |
| Gold | [PREENCHER] | Gold | [PREENCHER] | [V-Order? CLUSTER BY?] |

---

## 5. Compatibilidade de Dialeto

| Componente | Databricks | Fabric | Ação Necessária |
|-----------|-----------|--------|----------------|
| DDL | Spark SQL | T-SQL (Synapse) | [Conversão automática via sql-expert] |
| Queries analíticas | Spark SQL | T-SQL ou KQL | [PREENCHER] |
| Expectations | SDP `@dp.expect*` | [Sem equivalente nativo] | [Implementar via data-quality-steward] |
| Semantic Layer | Metric Views | Direct Lake + DAX | [Mapeamento via semantic-modeler] |

**Regra de Dialeto:**
- Databricks → Spark SQL
- Fabric Lakehouse → T-SQL (Synapse)
- Fabric Eventhouse → KQL

---

## 6. Segurança Cross-Platform

| Aspecto | Databricks | Fabric | Ação |
|---------|-----------|--------|------|
| Autenticação | Service Principal + Unity Catalog | Service Principal + Entra ID | [PREENCHER] |
| Autorização | GRANT/REVOKE por grupo | Workspace Roles | [Mapear grupos equivalentes] |
| PII | Column Masking (UC) | Sensitivity Labels | [Garantir proteção em ambas] |
| Auditoria | System Tables | OneLake Catalog | [governance-auditor validar ambos] |

**Regra SEC2:** Acesso concedido via grupos, nunca diretamente a usuários.
**Regra SEC3:** PII com mascaramento obrigatório em ambientes não-produtivos.

---

## 7. Orquestração

| Campo | Valor |
|-------|-------|
| **Ferramenta** | [Data Factory / DABs / Ambos] |
| **Trigger** | [Schedule / Event-based / Manual] |
| **Frequência** | [PREENCHER] |
| **Monitoramento** | [Databricks: list_job_runs / Fabric: get_lineage] |
| **Alertas** | [PREENCHER] |

---

## 8. Plano de Delegação

| Ordem | Agente | Tarefa | Plataforma |
|-------|--------|--------|-----------|
| 1 | pipeline-architect | Configurar conectividade cross-platform | Ambas |
| 2 | sql-expert | DDL nas plataformas destino + conversão de dialeto | Destino |
| 3 | spark-expert | Pipeline de movimentação/transformação | Origem |
| 4 | data-quality-steward | Expectations + validação pós-carga | Ambas |
| 5 | governance-auditor | Auditoria de acessos e linhagem cross-platform | Ambas |
| 6 | semantic-modeler | Modelo semântico na plataforma de consumo | Destino |

---

## 9. Checklist de Validação

- [ ] Estratégia de conectividade definida e testada
- [ ] Mapeamento de dialetos validado (sql-expert)
- [ ] Linhagem documentada em ambas plataformas
- [ ] PII protegido em ambas as plataformas
- [ ] Expectations definidas em ambos os lados
- [ ] Validação pós-carga executada (`SELECT count(*)`)
- [ ] Monitoramento e alertas configurados
