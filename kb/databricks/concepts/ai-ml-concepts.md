# AI & ML — Conceitos

> Conceitos e definições. Para padrões de implementação, veja patterns/.

**Domínio:** MLflow, Model Serving, Vector Search, AI Functions

---

## Componentes do Ecossistema ML

| Componente | Propósito | Quando Usar |
|------------|-----------|-------------|
| **MLflow Autolog** | Rastreia experimentos automaticamente | sklearn, xgboost, tensorflow |
| **MLflow PythonModel** | Encapsula lógica customizada | Custom models com preprocessing |
| **Model Serving** | Endpoint de inferência em tempo real | Produção, latência < 1s |
| **Vector Search** | Busca semântica sobre embeddings | RAG, recomendação, similaridade |
| **AI Functions** | LLMs em SQL direto | Sumarização, classificação em tabelas |

---

## MLflow: Autolog vs PythonModel

| Aspecto | Autolog | PythonModel |
|---------|---------|-------------|
| **Setup** | Uma linha (`mlflow.autolog()`) | Classe customizada |
| **Flexibilidade** | Limitado a libraries populares | Qualquer lógica |
| **Reprodutibilidade** | Automática | Manual (resources declarados) |
| **Uso** | sklearn, xgboost, tensorflow | Custom pipelines |

---

## Vector Search: Modos de Índice

| Modo | Sincronização | Embedding | Quando Usar |
|------|---------------|-----------|-------------|
| **Delta Sync Index** | Automática com tabela Delta | Calculado automaticamente | Datasets dinâmicos |
| **Direct Index** | Manual | Pré-calculado | Datasets estáticos |

**Gotcha:** Direct index requere embedding pré-calculado. Defasagem de minutos para datasets dinâmicos.

---

## Foundation Models: Nomes Exatos (Case-Sensitive)

```
databricks-claude-sonnet-4-5       ✅ Correto
databricks-meta-llama-3-70b-instruct  ✅ Correto
claude                              ❌ 404
Databricks-Claude                  ❌ Case-sensitive
```

---

## AI Functions: Requerem Python Wrapper

AI Functions **não** são queries diretas — requerem função Python wrapper registrada antes.

**Fluxo:** Criar função Python → Registrar em UC → Chamar em SQL

---

## Matriz de Decisão: ML Approach

| Cenário | Tipo | Implementação | Latência | Custo |
|---------|------|---------------|----------|-------|
| **Classificação tabular** | Classical ML | sklearn + AutoML | < 100ms | DBU |
| **Custom lógica + dados** | PythonModel | MLflow pyfunc | < 100ms | DBU |
| **GenAI agent** | Foundation Model | ResponsesAgent | 1-5s | Tokens LLM |
| **Embeddings + search** | Vector Search | Delta-sync index | < 500ms | Endpoint |
| **SQL + ML** | AI Functions | ai_query, ai_forecast | 1-5s | Tokens LLM |

---

## Checklist Implementação

- [ ] MLflow autolog ativado para sklearn/xgboost
- [ ] Custom models com PythonModel + resources declarados
- [ ] Model Serving endpoint criado e testado
- [ ] Foundation Model endpoint name exato (case-sensitive)
- [ ] ResponsesAgent para agentic workflows
- [ ] Vector Search delta-sync para datasets dinâmicos
- [ ] AI Functions com Python wrapper testado
- [ ] Timeout de 15 min considerado em CI/CD
- [ ] Embedding model selecionado (bge-large-en default)
- [ ] Logging de experimentos vinculado a runs (MLflow)
