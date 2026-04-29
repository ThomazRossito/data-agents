# Genie Agent Mode (GA Abril/2026)

## O que é Genie
Genie é o agente analítico autônomo do Databricks — transforma perguntas em linguagem natural em análises completas usando SQL + interpretação.

## Genie Agent Mode (GA Abr/2026)
**Agent Mode** expande o Genie original (pergunta → SQL → resultado) para um loop multi-step autônomo:

```
Usuário: "Por que as vendas caíram 15% em março?"
   ↓
Genie Agent Mode:
  1. Consulta dim_date, fact_sales → identifica queda
  2. Analisa por região → identifica problema no Sul
  3. Cruza com estoque → detecta ruptura específica
  4. Gera insight narrativo + recomendações
```

## Configurar Genie Space
```python
# Genie Space = contexto de tabelas + instruções semânticas
# Configurar via Databricks Portal → Genie → Create Space

# Estrutura de um Genie Space:
{
  "name": "Sales Analytics",
  "tables": [
    {"catalog": "prod", "schema": "sales", "table": "fact_orders"},
    {"catalog": "prod", "schema": "sales", "table": "dim_customer"},
    {"catalog": "prod", "schema": "sales", "table": "dim_product"},
  ],
  "instructions": """
    - 'sales' sempre refere a amount na fact_orders
    - Para análises de churn, olhar customers sem order nos últimos 90 dias
    - 'região' = dim_customer.region field
  """,
  "sample_questions": [
    "Qual foi o produto mais vendido em Q1?",
    "Quais clientes compraram pela primeira vez este mês?"
  ]
}
```

## Agentic Analytics — Multi-step Loop
No Agent Mode, Genie executa autonomamente até 10 SQL queries em sequência, ajustando a análise a cada resultado. O usuário pode:
- Aprovar cada passo (modo guiado)
- Deixar full auto (modo autônomo)
- Exportar o SQL gerado para um notebook

## Integração com UC
- Genie Space acessa apenas tabelas na lista de permissões do space
- Permissões do usuário são respeitadas (Unity Catalog GRANTS)
- Genie não tem acesso a tabelas que o usuário não pode `SELECT`
- Audit Log registra cada query gerada pelo Genie

## Limitações
- Max 10 steps no loop autônomo
- Tabelas devem estar no Unity Catalog (não DBFS legacy)
- Requer `SELECT` grant no UC para o usuário ou SP que executa
- Melhor desempenho com estatísticas de coluna atualizadas (`ANALYZE TABLE`)
