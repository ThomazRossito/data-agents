# SCD Types (Slowly Changing Dimensions)

## SCD Tipo 1 — Sobrescrever
Mais simples: atualiza o valor direto, sem histórico.
```sql
MERGE INTO dim_customer AS target
USING (SELECT customer_nk, name, email FROM source) AS src
ON target.customer_nk = src.customer_nk
WHEN MATCHED THEN UPDATE SET
    target.name = src.name,
    target.email = src.email
WHEN NOT MATCHED THEN INSERT (customer_nk, name, email) VALUES (src.customer_nk, src.name, src.email);
```

## SCD Tipo 2 — Nova Linha com Histórico

### Padrão com mergerkey (recomendado para Delta)
O `mergerkey` é um truque para permitir que o MERGE insira múltiplas linhas para o mesmo registro:

```sql
-- Preparar staging com mergerkey
CREATE OR REPLACE TEMP VIEW staged_updates AS
SELECT
  src.customer_nk,
  src.name,
  src.email,
  src.updated_at,
  CASE
    WHEN tgt.customer_nk IS NOT NULL AND tgt.is_current = TRUE
         AND (tgt.name != src.name OR tgt.email != src.email)
    THEN tgt.customer_nk  -- registro existente que muda → fechar
    ELSE NULL
  END AS mergerkey
FROM source src
LEFT JOIN dim_customer tgt ON src.customer_nk = tgt.customer_nk AND tgt.is_current = TRUE

UNION ALL

-- Nova linha para mudanças
SELECT
  src.customer_nk,
  src.name,
  src.email,
  src.updated_at,
  src.customer_nk AS mergerkey  -- forçar INSERT de nova linha
FROM source src
JOIN dim_customer tgt ON src.customer_nk = tgt.customer_nk AND tgt.is_current = TRUE
WHERE tgt.name != src.name OR tgt.email != src.email;

-- Executar MERGE
MERGE INTO dim_customer AS target
USING staged_updates AS src
ON target.customer_nk = src.mergerkey AND target.is_current = TRUE
WHEN MATCHED THEN UPDATE SET
    target.is_current = FALSE,
    target.expiry_date = CURRENT_DATE()
WHEN NOT MATCHED THEN INSERT (
    customer_nk, name, email,
    effective_date, expiry_date, is_current
) VALUES (
    src.customer_nk, src.name, src.email,
    CURRENT_DATE(), NULL, TRUE
);
```

### Por que mergerkey funciona?
- O MERGE padrão do Delta só permite 1 ação por linha de destino
- O mergerkey permite inserir a linha de "fechamento" separada da linha de "abertura"
- No `WHEN MATCHED`, fecha a linha atual (`is_current = FALSE`)
- No `WHEN NOT MATCHED`, insere nova linha ativa (`is_current = TRUE`)

## SCD Tipo 2 — Campos Obrigatórios na Dimensão
```sql
is_current      BOOLEAN DEFAULT TRUE,
effective_date  DATE NOT NULL,
expiry_date     DATE                  -- NULL enquanto is_current = TRUE
```

## SCD Tipo 3 — Versão Anterior
```sql
ALTER TABLE dim_customer ADD COLUMN previous_email STRING;

UPDATE dim_customer
SET previous_email = email, email = 'novo@email.com'
WHERE customer_nk = 'C001';
```
Limitação: guarda apenas 1 versão anterior. Raramente a escolha certa.

## dbt Snapshots (SCD Tipo 2 automatizado)
```yaml
# snapshots/snap_customer.sql
{% snapshot snap_customer %}
  {{
    config(
      target_schema='snapshots',
      unique_key='customer_nk',
      strategy='check',
      check_cols=['name', 'email'],
      invalidate_hard_deletes=true
    )
  }}
  SELECT * FROM {{ source('crm', 'customers') }}
{% endsnapshot %}
```
