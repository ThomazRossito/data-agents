# Skill: Star Schema — Regras de Design Gold Layer

> **Leia este arquivo ANTES de gerar qualquer tabela Gold (dim_* ou fact_*) em
> pipelines Medallion. Estas regras evitam os erros mais comuns de modelagem
> dimensional que causam dependências incorretas no DAG do LakeFlow.**

---

## O que é Star Schema e por que importa no LakeFlow

Um Star Schema organiza dados analíticos em:
- **Tabelas de dimensão** (`dim_*`): entidades de negócio (produtos, clientes, tempo).
- **Tabela fato** (`fact_*`): eventos mensuráveis (vendas, transações, cliques).

No LakeFlow Pipelines (DAG), o Star Schema correto produz um grafo assim:

```
silver_clientes ──▶ dim_clientes ──┐
silver_produtos ──▶ dim_produtos ──┤
                    dim_data  ─────┤──▶ fact_vendas
silver_vendas ────────────────────┘
```

**NUNCA** produza um grafo onde `fact_vendas` não se conecte a todas as dimensões,
ou onde uma dimensão aponte para uma tabela transacional (silver_vendas, bronze_*).

---

## REGRA 1 — Autonomia das Dimensões

**Tabelas `dim_*` NUNCA devem derivar de tabelas de fatos ou transacionais.**

| ❌ ERRADO | ✅ CORRETO |
|-----------|-----------|
| `SELECT DISTINCT data_venda FROM silver_vendas` | `SEQUENCE(DATE '2020-01-01', DATE '2030-12-31', INTERVAL 1 DAY)` |
| `SELECT DISTINCT id_produto FROM silver_pedidos` | `SELECT * FROM silver_produtos` (tabela própria da entidade) |
| `SELECT DISTINCT id_cliente FROM fact_vendas` | `SELECT * FROM silver_clientes` (tabela própria da entidade) |

**Regra de ouro**: cada dimensão deve ter sua **própria fonte de dados** ou ser
gerada sinteticamente (calendário, sequência de IDs). Uma dimensão derivada de
`DISTINCT` sobre uma tabela de fatos viola a integridade referencial — novos
produtos/clientes que ainda não tiveram venda ficam invisíveis na dimensão.

---

## REGRA 2 — Geração de Dimensão de Data/Calendário

A dimensão de data (`dim_data`, `dim_calendario`, `dim_tempo`) é **sempre gerada
sinteticamente** a partir de um intervalo fixo — nunca derivada de datas que
aparecem nos fatos.

### Padrão obrigatório (SQL / MATERIALIZED VIEW):

```sql
CREATE OR REFRESH MATERIALIZED VIEW gold_dim_data AS
SELECT
  CAST(date_col AS DATE)                            AS data_id,
  date_col                                          AS data_completa,
  YEAR(date_col)                                    AS ano,
  QUARTER(date_col)                                 AS trimestre,
  MONTH(date_col)                                   AS mes,
  DATE_FORMAT(date_col, 'MMMM')                     AS nome_mes,
  WEEKOFYEAR(date_col)                              AS semana_ano,
  DAYOFWEEK(date_col)                               AS dia_semana_num,
  DATE_FORMAT(date_col, 'EEEE')                     AS dia_semana_nome,
  DAY(date_col)                                     AS dia_mes,
  CASE WHEN DAYOFWEEK(date_col) IN (1, 7)
       THEN true ELSE false END                     AS fim_de_semana,
  DATE_FORMAT(date_col, 'yyyy-MM')                  AS ano_mes
FROM (
  SELECT EXPLODE(
    SEQUENCE(DATE '2020-01-01', DATE '2030-12-31', INTERVAL 1 DAY)
  ) AS date_col
)
CLUSTER BY ano, mes;
```

### Por que não usar `SELECT DISTINCT data_venda FROM silver_vendas`:
- Datas sem vendas (feriados, fins de semana) ficam ausentes → joins futuros retornam NULL.
- O intervalo cresce dinamicamente → reprocessamento completo a cada nova data.
- O DAG cria dependência dim_data → silver_vendas, que é **errada semanticamente**.

---

## REGRA 3 — Tabela Fato DEVE fazer INNER JOIN com TODAS as Dimensões

A `fact_*` é o ponto de encontro de todas as entidades. Ela **deve referenciar**
as tabelas `dim_*` via INNER JOIN, não apenas ler a tabela silver diretamente.

### Padrão obrigatório (SQL / MATERIALIZED VIEW):

```sql
CREATE OR REFRESH MATERIALIZED VIEW gold_fact_vendas AS
SELECT
  -- Chaves estrangeiras (FKs para as dimensões)
  v.id_venda,
  c.cliente_id,
  p.produto_id,
  d.data_id,
  -- Medidas
  v.quantidade,
  v.preco_unitario,
  v.quantidade * v.preco_unitario    AS receita_bruta,
  v.desconto,
  v.quantidade * v.preco_unitario
    - COALESCE(v.desconto, 0)        AS receita_liquida
FROM silver_vendas          v
INNER JOIN gold_dim_clientes c ON v.id_cliente = c.cliente_id
INNER JOIN gold_dim_produtos p ON v.id_produto = p.produto_id
INNER JOIN gold_dim_data     d ON CAST(v.data_venda AS DATE) = d.data_id
CLUSTER BY d.ano, d.mes;
```

**Por que INNER JOIN e não LEFT JOIN?**
- INNER JOIN garante que cada fato aponte para dimensões válidas (integridade referencial).
- Um fato sem dimensão correspondente indica dado sujo → deve ser tratado na Silver.
- LEFT JOIN na fact é aceitável apenas quando a ausência do registro dimensional
  é intencional e documentada (ex: transações de sistemas legados sem cadastro).

---

## REGRA 4 — Impacto no DAG do LakeFlow

O DAG é derivado automaticamente das dependências SQL. Para garantir a topologia
correta `dim_* → fact_*`:

```
✅ DAG CORRETO:
silver_clientes ──▶ dim_clientes ─────────────────────────────┐
silver_produtos ──▶ dim_produtos ─────────────────────────────┤──▶ fact_vendas
[SEQUENCE]      ──▶ dim_data     ─────────────────────────────┘         ▲
silver_vendas   ───────────────────────────────────────────────────────┘

❌ DAG ERRADO (dim derivada de fato):
silver_vendas ──▶ dim_data (SELECT DISTINCT) ──▶ fact_vendas
                                               ──▶ silver_vendas (novamente)
```

No DAG errado, `silver_vendas` aparece duas vezes no grafo, cria um ciclo lógico
e o LakeFlow pode reprocessar a silver desnecessariamente.

---

## REGRA 5 — Liquid Clustering na Gold Layer

Use `CLUSTER BY` nas tabelas Gold para otimizar consultas analíticas. **Não use
`PARTITION BY` + `ZORDER BY` em MATERIALIZED VIEWs — use apenas `CLUSTER BY`.**

```sql
-- ✅ Correto para MATERIALIZED VIEW
CLUSTER BY (ano, mes, id_cliente)

-- ❌ Errado — PARTITION BY não é suportado em MATERIALIZED VIEW do LakeFlow
PARTITIONED BY (ano, mes)
```

Escolha colunas de clustering com base nos filtros mais comuns:
- Dimensão temporal: `ano`, `mes`
- Dimensão de negócio principal: `id_produto`, `id_cliente`, `regiao`

---

## Checklist Star Schema — Gold Layer

Antes de finalizar qualquer geração de Gold Layer, confirme:

- [ ] Cada `dim_*` tem fonte própria (tabela silver específica da entidade OU geração sintética)
- [ ] `dim_data` / `dim_calendario` usa `SEQUENCE(...)` com intervalo fixo — **NUNCA** `SELECT DISTINCT data FROM ...`
- [ ] `fact_*` faz `INNER JOIN` com **todas** as `dim_*` relacionadas
- [ ] O DAG resultante NÃO cria `silver_vendas` (ou qualquer tabela transacional) como antecessor de uma `dim_*`
- [ ] Todas as tabelas Gold usam `MATERIALIZED VIEW` (não `STREAMING TABLE`)
- [ ] `CLUSTER BY` definido para colunas de acesso frequente
- [ ] Chaves de join entre fact e dims estão tipadas de forma compatível (DATE vs DATE, INT vs INT)

---

## Exemplo Completo — Star Schema de E-commerce (Referência)

```sql
-- ── dim_clientes: fonte própria (silver_clientes) ───────────────
CREATE OR REFRESH MATERIALIZED VIEW gold_dim_clientes AS
SELECT
  id_cliente    AS cliente_id,
  nome,
  email,
  cidade,
  estado,
  pais,
  segmento
FROM silver_clientes
CLUSTER BY estado, segmento;

-- ── dim_produtos: fonte própria (silver_produtos) ───────────────
CREATE OR REFRESH MATERIALIZED VIEW gold_dim_produtos AS
SELECT
  id_produto    AS produto_id,
  nome_produto,
  categoria,
  subcategoria,
  marca,
  preco_lista
FROM silver_produtos
CLUSTER BY categoria, subcategoria;

-- ── dim_data: GERAÇÃO SINTÉTICA — NUNCA de silver_vendas ────────
CREATE OR REFRESH MATERIALIZED VIEW gold_dim_data AS
SELECT
  CAST(date_col AS DATE)              AS data_id,
  date_col                            AS data_completa,
  YEAR(date_col)                      AS ano,
  QUARTER(date_col)                   AS trimestre,
  MONTH(date_col)                     AS mes,
  DATE_FORMAT(date_col, 'MMMM')      AS nome_mes,
  DAY(date_col)                       AS dia,
  DATE_FORMAT(date_col, 'EEEE')      AS dia_semana,
  CASE WHEN DAYOFWEEK(date_col) IN (1,7) THEN true ELSE false END AS fim_de_semana
FROM (SELECT EXPLODE(SEQUENCE(DATE '2020-01-01', DATE '2030-12-31', INTERVAL 1 DAY)) AS date_col)
CLUSTER BY ano, mes;

-- ── fact_vendas: JOIN com TODAS as dimensões ────────────────────
CREATE OR REFRESH MATERIALIZED VIEW gold_fact_vendas AS
SELECT
  v.id_venda,
  c.cliente_id,
  p.produto_id,
  d.data_id,
  v.canal_venda,
  v.quantidade,
  v.preco_unitario,
  v.desconto,
  v.quantidade * v.preco_unitario                         AS receita_bruta,
  v.quantidade * v.preco_unitario - COALESCE(v.desconto, 0) AS receita_liquida
FROM silver_vendas          v
INNER JOIN gold_dim_clientes c ON v.id_cliente  = c.cliente_id
INNER JOIN gold_dim_produtos p ON v.id_produto  = p.produto_id
INNER JOIN gold_dim_data     d ON CAST(v.data_venda AS DATE) = d.data_id
CLUSTER BY d.ano, d.mes;
```
