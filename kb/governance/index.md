# KB: Governança de Dados — Índice

**Domínio:** Auditoria, linhagem, controle de acesso e conformidade de dados.
**Agentes:** governance-auditor

---

## Conteúdo Disponível

| Arquivo                        | Conteúdo                                                                  |
|--------------------------------|---------------------------------------------------------------------------|
| `access-control-patterns.md`   | Padrões de RBAC no Unity Catalog e Fabric Workspace Roles                 |
| `lineage-documentation.md`     | Como documentar e consultar linhagem de dados cross-platform              |
| `pii-classification.md`        | Classificação de dados PII, sensíveis e confidenciais                     |
| `audit-procedures.md`          | Procedimentos de auditoria usando System Tables e OneLake Catalog         |
| `compliance-checklist.md`      | Checklist de conformidade LGPD/GDPR para pipelines de dados               |

---

## Regras de Negócio Críticas

### Controle de Acesso
- Todo acesso a dados deve ser concedido via grupos (nunca diretamente a usuários).
- Dados PII requerem aprovação do Data Owner antes de qualquer acesso.
- Princípio do menor privilégio: conceda apenas as permissões necessárias para a função.
- Revogue acessos de colaboradores que saíram do time em até 24h.
- Audite acessos mensalmente usando `system.access.audit` (Databricks) ou OneLake Catalog (Fabric).

### Classificação de Dados
- **Público**: Dados sem restrição de acesso (ex: tabelas de referência).
- **Interno**: Dados de uso interno do time (ex: métricas operacionais).
- **Confidencial**: Dados de negócio sensíveis (ex: dados financeiros, estratégicos).
- **PII/Restrito**: Dados pessoais identificáveis (ex: CPF, email, endereço). Requer mascaramento.

### Linhagem de Dados
- Toda tabela Gold deve ter sua linhagem documentada até a fonte de origem.
- Use `mcp__fabric_community__get_lineage` para consultar linhagem no Fabric.
- Use System Tables `system.lineage.table_lineage` para linhagem no Databricks.
- Documente dependências cross-platform (Shortcuts, Mirroring) no catálogo.

### Conformidade LGPD/GDPR
- Dados PII devem ser mascarados em ambientes de desenvolvimento e homologação.
- Implemente right-to-erasure: processo documentado para exclusão de dados pessoais.
- Mantenha registro de processamento de dados pessoais atualizado.
- Retenção de dados: defina e implemente políticas de TTL (Time-To-Live) por tabela.
- Auditorias de conformidade devem ser realizadas trimestralmente.
