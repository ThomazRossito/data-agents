# AI & ML — Padrões de Implementação

> Padrões de implementação. Para conceitos, veja concepts/.

**Domínio:** MLflow código, Model Serving, Vector Search, AI Functions SQL

---

## MLflow Autolog

```python
import mlflow
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_breast_cancer

mlflow.autolog()

with mlflow.start_run():
    X, y = load_breast_cancer(return_X_y=True)
    model = RandomForestClassifier()
    model.fit(X, y)
    # Autolog captura: params, metrics, model, training time
```

---

## MLflow PythonModel (Custom)

```python
import mlflow
from mlflow.pyfunc import PythonModel, log_model

class MyCustomModel(PythonModel):
    def __init__(self):
        self.preprocessor = load_preprocessor()

    def predict(self, context, model_input):
        cleaned = self.preprocessor.transform(model_input)
        predictions = self.model.predict(cleaned)
        return predictions

with mlflow.start_run() as run:
    model = MyCustomModel()
    log_model(
        model,
        artifact_path="model",
        python_model=model,
        registered_model_name="my_model",
        resources=[
            {
                "type": "python_package",
                "package": "numpy==1.24.0"
            }
        ]
    )
```

**Gotcha:** `resources` parameter é obrigatório. Sem ele, Model Serving falha por imports.

---

## Model Serving: Criar Endpoint

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput

w = WorkspaceClient()

endpoint_config = EndpointCoreConfigInput(
    name="my-model-endpoint",
    served_models=[
        {
            "model_name": "my_model",
            "model_version": "1",
            "workload_size": "Small"
        }
    ]
)

endpoint = w.serving_endpoints.create(config=endpoint_config)
```

## Model Serving: Query Endpoint

```python
import requests

endpoint_url = "https://<workspace-url>/api/2.0/endpoints/my-model-endpoint/invocations"

payload = {
    "dataframe_split": {
        "columns": ["feature1", "feature2"],
        "data": [[1.0, 2.0], [3.0, 4.0]]
    }
}

response = requests.post(
    endpoint_url,
    headers={"Authorization": f"Bearer {token}"},
    json=payload
)
predictions = response.json()["predictions"]
```

---

## ResponsesAgent para Foundation Models

```python
from databricks.genai.agent_api import ResponsesAgent

agent = ResponsesAgent(
    model="databricks-claude-sonnet-4-5",  # Nome exato, case-sensitive
    temperature=0.7,
    max_tokens=1024
)

response = agent.respond(
    prompt="Analise este dataset...",
    context_data=df
)
```

---

## Vector Search: Delta Sync Index

```python
from databricks.vector_search.client import VectorSearchClient

client = VectorSearchClient()

index = client.create_delta_sync_index(
    endpoint_name="my-endpoint",
    index_name="doc_index",
    primary_key="doc_id",
    delta_sync_index_config={
        "data_objects": [
            {
                "table_name": "main.docs.documents",
                "text_search_config": {
                    "field_name": "content",
                    "chunk_template": "{{content}}"
                },
                "embedding_source_columns": ["content"],
                "embedding_model": "databricks-bge-large-en"
            }
        ]
    }
)

# Query
results = index.similarity_search(
    query_text="Machine learning",
    columns=["id", "content", "metadata"],
    num_results=5
)
```

---

## AI Functions SQL

```sql
-- ai_query: consultas customizadas
SELECT ai_query(
    'main.genai.ai_fn',
    'Sumarize este texto: ' || content,
    model => 'databricks-claude-sonnet-4-5'
) AS summary
FROM main.docs.articles;

-- ai_forecast: previsões
SELECT ai_forecast(
    'main.genai.forecast_fn',
    STRUCT(date, sales, trend),
    model => 'databricks-claude-sonnet-4-5'
) AS predicted_sales
FROM main.analytics.sales_history
WHERE date >= current_date() - 30;
```

**Requer Python wrapper registrado antes:**
```sql
CREATE FUNCTION summarize(text STRING)
RETURNS STRING
LANGUAGE PYTHON
AS $$
from databricks_genai import ...
return summarize_fn(text)
$$
```
