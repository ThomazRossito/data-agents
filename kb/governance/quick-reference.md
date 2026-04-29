# Governance Quick Reference

> Tabelas de lookup rápido. Para exemplos completos ver arquivos linkados.

## PII Detection Patterns (Regex — Python)

| Tipo de PII | Regex | Exemplo |
|------------|-------|---------|
| CPF | `\d{3}\.?\d{3}\.?\d{3}-?\d{2}` | 123.456.789-00 |
| E-mail | `[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}` | user@email.com |
| Telefone BR | `(\+55\s?)?(\(?\d{2}\)?\s?)(\d{4,5}-?\d{4})` | (11) 99999-9999 |
| Cartão de crédito | `\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b` | 4111 1111 1111 1111 |
| CEP | `\d{5}-?\d{3}` | 01310-100 |

## Unity Catalog — Grants

| Operação | Sintaxe SQL | Nível |
|----------|------------|-------|
| Leitura em tabela | `GRANT SELECT ON TABLE cat.sch.tbl TO group_x` | Table |
| Criação em schema | `GRANT CREATE ON SCHEMA cat.sch TO group_x` | Schema |
| Usar catalog | `GRANT USE CATALOG ON CATALOG cat TO group_x` | Catalog |
| Mascarar coluna PII | `ALTER TABLE t ALTER COLUMN cpf SET MASK func` | Column |
| Row filter | `ALTER TABLE t SET ROW FILTER func ON (tenant_id)` | Row |
| Revogar | `REVOKE SELECT ON TABLE ... FROM group_x` | Any |

## LGPD / GDPR Direitos

| Direito | Implementação Delta | Prazo típico |
|---------|--------------------|----|
| Acesso | `SELECT` com row filter por titular_id | On-demand |
| Portabilidade | Export CSV da view filtrada | 15 dias |
| Retificação | `UPDATE ... WHERE titular_id = ?` | 15 dias |
| Esquecimento | `DELETE FROM ... WHERE titular_id = ?` + VACUUM | 72h (urgência) |
| Oposição | Soft-delete + column_mask para leituras futuras | Imediato |

## Severity Matrix (Achados de Auditoria)

| Achado | Severidade | Ação imediata |
|--------|-----------|---------------|
| PII em logs sem máscara | CRITICAL | Stop pipeline + notificar DPO |
| Colunas PII sem `tag pii=true` | CRITICAL | Tag + rever grants |
| Ausência de row filter em tabela Gold com PII | HIGH | Criar row filter urgente |
| Grant excessivo em catálogo inteiro | HIGH | Revogar, aplicar least-privilege |
| Ausência de COMMENT em coluna PII | MEDIUM | Documentar no sprint seguinte |
| Nome de objeto fora da convenção | LOW | Criar ticket de rename |

## Common Pitfalls

| Evite | Prefira |
|-------|---------|
| Tag PII manual após criação | Definir no DDL no ato de criação |
| Grant em usuário individual | Grant em grupo/role do Unity Catalog |
| VACUUM imediato pós-DELETE PII | VACUUM após SLA de retenção (≥ 7 dias) |
| Logs com `row.asDict()` completo | Logar apenas IDs e timestamps |

## Related

| Tópico | Arquivo |
|--------|---------|
| Naming audit | naming-audit.md |
| PII masking (código) | pii-handling.md |
| Grants e RLS (código) | access-control.md |
