# KB: Governança — PII Handling (LGPD/GDPR)

## Identificação de PII

Colunas que devem ser marcadas como PII:

| Campo | Sensibilidade | Base Legal Típica |
|-------|--------------|-------------------|
| cpf / cnpj | Alta | Contrato / Obrigação legal |
| email | Média | Consentimento |
| telefone | Média | Consentimento |
| nome_completo | Baixa | Contrato |
| data_nascimento | Baixa | Contrato |
| ip_address | Média | Consentimento |
| localização_gps | Alta | Consentimento explícito |
| dados_saúde | Máxima | Consentimento explícito + DPO |

## Tagging no Unity Catalog

```sql
-- Tag na tabela
ALTER TABLE catalog.silver.slv_customers
  SET TAGS ('contains_pii' = 'true', 'data_domain' = 'customer');

-- Tag na coluna
ALTER TABLE catalog.silver.slv_customers
  ALTER COLUMN cpf
  SET TAGS ('pii' = 'true', 'sensitivity' = 'high', 'lgpd_basis' = 'contract');
```

## Column Masking (acesso por grupo)

```sql
CREATE OR REPLACE FUNCTION catalog.governance.mask_cpf(cpf STRING, groups ARRAY<STRING>)
RETURNS STRING
RETURN CASE
  WHEN array_contains(groups, 'data_engineers') THEN cpf
  ELSE regexp_replace(cpf, '\\d{3}\\.\\d{3}\\.\\d{3}', '***.***.***')
END;

ALTER TABLE catalog.silver.slv_customers
  ALTER COLUMN cpf
  SET MASK catalog.governance.mask_cpf
  USING COLUMNS (current_groups());
```

## Direito ao Esquecimento (LGPD Art. 18)

```python
from delta.tables import DeltaTable

def gdpr_delete(table_name: str, customer_id: int) -> None:
    """Remove dados pessoais de um titular específico."""
    dt = DeltaTable.forName(spark, table_name)
    dt.delete(f"customer_id = {customer_id}")
    # Vacuum imediato para remover fisicamente (ATENÇÃO: perde time travel)
    spark.sql(f"VACUUM {table_name} RETAIN 0 HOURS")
```

## Regras

- Todo dado pessoal deve ter base legal documentada no TBLPROPERTIES
- Titular pode solicitar exclusão de todos os dados pessoais — implementar com DELETE + VACUUM
- Logs de acesso a tabelas PII habilitados por padrão
- Dados de saúde exigem aprovação do DPO antes de ingestão
