# Data Modeling Quick Reference

## Star vs Snowflake
| Critério | Star Schema | Snowflake Schema |
|----------|------------|-----------------|
| Estrutura | Fato → Dimensões planas | Fato → Dimensões normalizadas |
| Query performance | Melhor (menos joins) | Pior (mais joins) |
| Storage | Maior (redundância) | Menor |
| Manutenção | Mais simples | Mais complexa |
| Uso típico | OLAP, BI self-service | DWH altamente normalizado |
| **Recomendado** | ✓ Default | Apenas se storage crítico |

## SCD — Tipos de Mudança Lenta
| Tipo | Estratégia | Histórico | Uso |
|------|-----------|-----------|-----|
| SCD 0 | Não atualizar | Não | Dados imutáveis |
| SCD 1 | UPDATE simples | Não | Correção de erros |
| SCD 2 | Nova linha + active/dates | Sim | Histórico completo |
| SCD 3 | Coluna "anterior" | Parcial | Apenas 1 versão anterior |

## Chaves
| Tipo | Definição | Pros | Contras |
|------|-----------|------|---------|
| **Surrogate Key (SK)** | Seq int gerado (IDENTITY) | Estável, independente de fonte | Sem significado de negócio |
| **Natural Key (NK)** | Vem da fonte (CPF, order_id) | Significado real | Pode mudar; depende da fonte |
| **Recomendado** | SK como PK + NK como lookup | Join por SK; filter por NK | — |

## Formas Normais (resumo)
| Forma | Regra |
|-------|-------|
| 1FN | Atributos atômicos, sem grupos repetidos |
| 2FN | 1FN + todos atributos dependem da PK inteira |
| 3FN | 2FN + sem dependências transitivas |
| BCNF | 3FN reforçada — toda dependência funcional tem superkey |

## DDL Padrão — Tabela Dimensão
```sql
CREATE TABLE dim_customer (
    customer_sk     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_nk     STRING NOT NULL,       -- natural key da fonte
    name            STRING,
    email           STRING,
    -- SCD 2 fields
    effective_date  DATE NOT NULL,
    expiry_date     DATE,
    is_current      BOOLEAN NOT NULL DEFAULT TRUE
)
USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
```
