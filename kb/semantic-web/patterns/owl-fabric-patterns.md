# Padrões OWL no Microsoft Fabric — Import / Export

---

## Padrão 1: Upload de Arquivo OWL para OneLake via MCP

```python
# Usar mcp__fabric_official__onelake_upload_file para enviar arquivo ao OneLake
# Caminho destino: Files/ontologies/domain/<nome>.<ext>

# Via MCP (em contexto de agente):
# mcp__fabric_official__onelake_upload_file(
#     workspace_id = "<FABRIC_WORKSPACE_ID>",
#     lakehouse_name = "ontology_lh",
#     destination_path = "ontologies/domain/rh_schema_v1.ttl",
#     file_content = <bytes do arquivo TTL>
# )
```

### Gerar o arquivo localmente e fazer upload:

```python
from rdflib import Graph
import tempfile
import os

def upload_ontology_to_onelake(
    graph: Graph,
    lakehouse_name: str,
    ontology_name: str,
    fmt: str = "turtle",
    ext: str = "ttl",
) -> str:
    """Serializa grafo e prepara para upload ao OneLake. Retorna caminho destino."""
    destination_path = f"ontologies/domain/{ontology_name}.{ext}"

    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        graph.serialize(destination=tmp.name, format=fmt)
        tmp_path = tmp.name

    # Ler bytes para upload via MCP (mcp__fabric_official__onelake_upload_file)
    with open(tmp_path, "rb") as f:
        file_bytes = f.read()
    os.unlink(tmp_path)

    print(f"Pronto para upload: {destination_path} ({len(file_bytes)} bytes)")
    return destination_path
```

---

## Padrão 2: Download de Arquivo OWL do OneLake via MCP

```python
# Via MCP (em contexto de agente):
# conteudo = mcp__fabric_official__onelake_download_file(
#     workspace_id = "<FABRIC_WORKSPACE_ID>",
#     lakehouse_name = "ontology_lh",
#     file_path = "ontologies/domain/rh_schema_v1.ttl"
# )
```

### Parsear arquivo baixado em grafo rdflib:

```python
from rdflib import Graph
import io

def parse_ontology_from_bytes(file_bytes: bytes, fmt: str = "turtle") -> Graph:
    """Carrega grafo rdflib a partir de bytes baixados do OneLake."""
    g = Graph()
    g.parse(data=file_bytes.decode("utf-8"), format=fmt)
    return g
```

---

## Padrão 3: Processar OWL em Spark Notebook (Fabric)

> **Schema canônico da tabela `ontology_triples`** — use sempre esta estrutura para garantir
> compatibilidade com Padrão 4, Padrão 6 e Padrão 8.

```python
# Notebook Spark no Fabric — executar após instalar rdflib no cluster:
# %pip install rdflib==7.1.1

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
from rdflib import Graph
from datetime import datetime, timezone

spark = SparkSession.builder.getOrCreate()

# 1. Ler arquivo OWL do OneLake Files via mssparkutils (Fabric nativo)
file_path = "abfss://<workspace_id>@onelake.dfs.fabric.microsoft.com/<lakehouse_id>/Files/ontologies/domain/rh_schema_v1.ttl"
content = spark.sparkContext.textFile(file_path).collect()
owl_text = "\n".join(content)

# 2. Parsear com rdflib no driver
g = Graph()
g.parse(data=owl_text, format="turtle")
print(f"Triples carregados: {len(g)}")

# 3. Converter para DataFrame PySpark — schema canônico com graph e loaded_at
schema = StructType([
    StructField("subject",     StringType(), False),
    StructField("predicate",   StringType(), False),
    StructField("object",      StringType(), False),
    StructField("graph",       StringType(), True),   # Named graph; None = grafo default
    StructField("datatype",    StringType(), True),
    StructField("lang_tag",    StringType(), True),
    StructField("source_file", StringType(), True),
    StructField("loaded_at",   StringType(), True),   # ISO 8601 UTC
])

from rdflib.term import Literal as RDFLiteral, BNode

rows = []
loaded_at = datetime.now(timezone.utc).isoformat()
for s, p, o in g:
    obj_str = str(o)
    datatype = None
    lang_tag = None
    if isinstance(o, RDFLiteral):
        datatype = str(o.datatype) if o.datatype else None
        lang_tag = o.language
    elif isinstance(o, BNode):
        obj_str = f"_:{str(o)}"
    subject_str = f"_:{str(s)}" if isinstance(s, BNode) else str(s)
    rows.append((subject_str, str(p), obj_str, None, datatype, lang_tag, "rh_schema_v1.ttl", loaded_at))

df = spark.createDataFrame(rows, schema=schema)

# 4. Salvar em Delta (merge ou overwrite por source_file)
(
    df.write
    .format("delta")
    .mode("append")
    .option("mergeSchema", "true")
    .saveAsTable("ontology_lh.ontology_triples")
)

print(f"Triples salvos: {df.count()}")
```

---

## Padrão 4: Reconstruir Grafo a Partir do Delta

```python
# Spark Notebook: Delta Table → rdflib Graph → arquivo serializado

from pyspark.sql import SparkSession
from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import XSD
import re

spark = SparkSession.builder.getOrCreate()

# Filtrar triples de um domínio específico
namespace_filter = "https://ontologia.empresa.com.br/rh/"

triples_df = spark.sql(f"""
    SELECT subject, predicate, object, datatype, lang_tag
    FROM ontology_lh.ontology_triples
    WHERE subject LIKE '{namespace_filter}%'
       OR predicate LIKE '{namespace_filter}%'
""").collect()

# Reconstruir grafo
g = Graph()

def make_node(value: str):
    if value.startswith("_:"):
        return BNode(value[2:])
    return URIRef(value)

for row in triples_df:
    s = make_node(row.subject)
    p = URIRef(row.predicate)

    if row.datatype or row.lang_tag:
        if row.lang_tag:
            o = Literal(row.object, lang=row.lang_tag)
        else:
            o = Literal(row.object, datatype=URIRef(row.datatype) if row.datatype else None)
    else:
        # Verificar se object é URI ou blank node
        if row.object.startswith("http") or row.object.startswith("_:"):
            o = make_node(row.object)
        else:
            o = Literal(row.object)

    g.add((s, p, o))

print(f"Grafo reconstruído: {len(g)} triples")

# Serializar e salvar no OneLake
output_ttl = g.serialize(format="turtle")
# Salvar via mssparkutils.fs.put ou via MCP
```

---

## Padrão 5: Inventário Completo de Ontologias no Workspace

> **OBRIGATÓRIO:** sempre executar os dois passos abaixo — itens nativos do Fabric
> NÃO aparecem em `onelake_list_files`; arquivos OWL/TTL NÃO aparecem em `list_items`.

```python
# PASSO A — Itens nativos do Fabric (tipo "Ontology", "GraphModel", etc.)
# Via MCP:
# items = mcp__fabric_official__list_items(workspace_id="<FABRIC_WORKSPACE_ID>")
# Resposta: lista de dicts com chaves: id, displayName, type, description
# Exemplo de item nativo:
#   { "id": "c731f2d7-...", "displayName": "RetailSalesOntology", "type": "Ontology" }
#
# Filtrar por tipo Ontology:
# ontology_items = [i for i in items if i.get("type") == "Ontology"]
#
# Para cada item nativo, inspecionar estrutura:
# schema = mcp__fabric_official__get_item_schema(
#     workspace_id = "<FABRIC_WORKSPACE_ID>",
#     item_id = item["id"]
# )

# PASSO B — Arquivos OWL/TTL/NT armazenados no OneLake Files
# Via MCP:
# arquivos = mcp__fabric_official__onelake_list_files(
#     workspace_id = "<FABRIC_WORKSPACE_ID>",
#     lakehouse_name = "ontology_lh",
#     directory_path = "ontologies/"
# )
# Resposta: lista de dicts com chaves: name, size, last_modified
# for f in arquivos:
#     print(f["name"], f["size"], f["last_modified"])
```

---

## Padrão 6: Views SQL sobre Tabela de Triples

```sql
-- View: Classes da ontologia
CREATE OR REPLACE VIEW ontology_lh.vw_ontology_classes AS
SELECT
    subject                                    AS class_uri,
    REGEXP_EXTRACT(subject, '[^/#+]+$')        AS class_local_name,
    source_file,
    loaded_at
FROM ontology_lh.ontology_triples
WHERE predicate  = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
  AND object     = 'http://www.w3.org/2002/07/owl#Class';

-- View: Hierarquia de classes (subClassOf)
CREATE OR REPLACE VIEW ontology_lh.vw_class_hierarchy AS
SELECT
    subject   AS subclass_uri,
    object    AS superclass_uri,
    REGEXP_EXTRACT(subject, '[^/#+]+$') AS subclass_name,
    REGEXP_EXTRACT(object,  '[^/#+]+$') AS superclass_name
FROM ontology_lh.ontology_triples
WHERE predicate = 'http://www.w3.org/2000/01/rdf-schema#subClassOf'
  AND object NOT LIKE '_:%';

-- View: Labels em português
CREATE OR REPLACE VIEW ontology_lh.vw_ontology_labels AS
SELECT
    subject   AS entity_uri,
    object    AS label_pt,
    REGEXP_EXTRACT(subject, '[^/#+]+$') AS local_name
FROM ontology_lh.ontology_triples
WHERE predicate = 'http://www.w3.org/2000/01/rdf-schema#label'
  AND lang_tag  = 'pt';
```

---

## Padrão 7: Export para Múltiplos Formatos em Paralelo

```python
from rdflib import Graph
from pathlib import Path

EXPORT_FORMATS = {
    "turtle":  ".ttl",
    "xml":     ".owl",
    "nt":      ".nt",
    "json-ld": ".jsonld",
}

def export_all_formats(source_ttl: str, output_dir: str) -> dict[str, int]:
    """
    Exporta uma ontologia Turtle para todos os formatos suportados.
    Retorna dict de formato → bytes escritos.
    """
    g = Graph()
    g.parse(source_ttl, format="turtle")

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    base_name = Path(source_ttl).stem
    results = {}

    for fmt, ext in EXPORT_FORMATS.items():
        dest = out_path / f"{base_name}{ext}"
        g.serialize(destination=str(dest), format=fmt)
        size = dest.stat().st_size
        results[fmt] = size
        print(f"Exportado {fmt}: {dest} ({size:,} bytes)")

    return results
```

---

## Padrão 8: Trabalhar com Ontology Item Nativo do Microsoft Fabric

> O Fabric tem um tipo de item nativo chamado **Ontology** (criado pela UI do Fabric).
> Ele é diferente de um arquivo OWL armazenado no OneLake Files — é um artefato gerenciado
> internamente pelo Fabric e **não aparece em `onelake_list_files`**.

### Artefatos auto-gerados pelo Fabric ao criar um item Ontology

Quando o Fabric cria um item do tipo Ontology, ele provisiona automaticamente:

| Artefato | Tipo | Descrição |
|----------|------|-----------|
| `<nome>` | Ontology | Item principal — gerenciado internamente |
| `<nome>_lh` | Lakehouse | Lakehouse que armazena os dados em Delta |
| `<nome>_lh` | SQLEndpoint | SQL Analytics Endpoint do Lakehouse acima |
| `<nome>_graph` | GraphModel | Representa o grafo RDF internamente no Fabric |
| `<nome>Model` | SemanticModel | Modelo semântico para consumo em Power BI (nem sempre criado) |

### Descoberta e Inspeção via MCP

```python
# 1. Descobrir todos os itens nativos do tipo Ontology no workspace
# items = mcp__fabric_official__list_items(workspace_id="<FABRIC_WORKSPACE_ID>")
# Resposta esperada (lista de dicts):
# [
#   { "id": "c731f2d7-...", "displayName": "RetailSalesOntology", "type": "Ontology" },
#   { "id": "d40b7907-...", "displayName": "RetailSalesOntology_lh", "type": "Lakehouse" },
#   { "id": "...",          "displayName": "RetailSalesOntology_graph", "type": "GraphModel" },
# ]

# 2. Inspecionar o schema do item nativo Ontology
# schema_info = mcp__fabric_official__get_item_schema(
#     workspace_id = "<FABRIC_WORKSPACE_ID>",
#     item_id      = "c731f2d7-..."   # ID do item tipo Ontology
# )

# 3. Inspecionar o Lakehouse gerado automaticamente
# Use mcp__fabric_community__list_tables para ver tabelas Delta disponíveis
# tabelas = mcp__fabric_community__list_tables(
#     workspace_id   = "<FABRIC_WORKSPACE_ID>",
#     lakehouse_name = "RetailSalesOntology_lh"
# )
```

### Exportar Ontologia Nativa → Arquivo OWL/Turtle

O item Ontology nativo **não pode ser exportado diretamente via MCP de arquivo**.
O caminho correto é via Spark Notebook lendo o Delta do Lakehouse gerado:

```python
# Spark Notebook — exportar Ontology nativa → Turtle

# %pip install rdflib==7.1.1

from pyspark.sql import SparkSession
from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import XSD
from datetime import datetime, timezone

spark = SparkSession.builder.getOrCreate()

# 1. Ler triples do Lakehouse gerado automaticamente pelo item Ontology
triples_df = spark.sql("""
    SELECT subject, predicate, object, datatype, lang_tag
    FROM RetailSalesOntology_lh.ontology_triples
""").collect()

# 2. Reconstruir grafo rdflib
g = Graph()

def make_node(value: str):
    if value and value.startswith("_:"):
        return BNode(value[2:])
    return URIRef(value)

for row in triples_df:
    s = make_node(row.subject)
    p = URIRef(row.predicate)
    if row.lang_tag:
        o = Literal(row.object, lang=row.lang_tag)
    elif row.datatype:
        o = Literal(row.object, datatype=URIRef(row.datatype))
    elif row.object and (row.object.startswith("http") or row.object.startswith("_:")):
        o = make_node(row.object)
    else:
        o = Literal(row.object)
    g.add((s, p, o))

print(f"Grafo reconstruído: {len(g)} triples")

# 3. Serializar para Turtle
output_path = "/lakehouse/default/Files/ontologies/export/retail_ontology_export.ttl"
g.serialize(destination=output_path, format="turtle")
print(f"Exportado: {output_path}")

# 4. Fazer upload via MCP (fora do Spark):
# mcp__fabric_official__onelake_upload_file(
#     workspace_id      = "<FABRIC_WORKSPACE_ID>",
#     lakehouse_name    = "OntologiaDataLH",
#     destination_path  = "ontologies/export/retail_ontology_export.ttl",
#     local_file_path   = output_path
# )
```

> **Escalar para `spark-expert`** se o notebook precisar ser executado no Fabric com
> configurações específicas de cluster ou se o volume de triples for > 1M linhas.

---

## Padrão 9: Import de Ontologia Pública via Tavily + Firecrawl

> Use quando o usuário precisar importar uma ontologia pública (Schema.org, Dublin Core,
> W3C Organization, OBO, etc.) para o Fabric OneLake.

```python
# PASSO 1 — Descobrir a ontologia pública com Tavily
# results = mcp__tavily__tavily-search(
#     query = "schema.org ontology turtle download filetype:ttl"
# )
# Inspecionar results para identificar URL do arquivo .ttl ou .owl
# Exemplo: "https://schema.org/version/latest/schemaorg-current-https.ttl"

# PASSO 2 — Fazer scrape/download do arquivo com Firecrawl
# content = mcp__firecrawl__scrape(
#     url     = "https://schema.org/version/latest/schemaorg-current-https.ttl",
#     formats = ["markdown", "rawHtml"]
# )
# raw_ttl = content.get("rawHtml") or content.get("content")

# PASSO 3 — Parsear e validar
from rdflib import Graph

g = Graph()
# g.parse(data=raw_ttl, format="turtle")  # ou "xml" se for RDF/XML

# PASSO 4 — Validar estrutura
# report = validate_owl_structure_from_graph(g)
# if not report["valid"]:
#     raise ValueError(f"Ontologia inválida: {report['issues']}")

# PASSO 5 — Verificar e normalizar namespace (se necessário)
# Ontologias públicas mantêm seu namespace original (ex: https://schema.org/)
# NÃO renomear para namespace canônico do projeto — apenas mapear via owl:imports ou owl:equivalentClass

# PASSO 6 — Serializar para Turtle (normalização)
# g.serialize(destination="output/schema_org.ttl", format="turtle")

# PASSO 7 — Upload para OneLake (Files/ontologies/raw/ para ontologias externas)
# mcp__fabric_official__onelake_upload_file(
#     workspace_id     = "<FABRIC_WORKSPACE_ID>",
#     lakehouse_name   = "ontology_lh",
#     destination_path = "ontologies/raw/schema_org.ttl",
#     local_file_path  = "output/schema_org.ttl"
# )
```

> **Nota:** Ontologias públicas armazenadas em `Files/ontologies/raw/` — NUNCA em `domain/`.
> `domain/` é reservado para ontologias de domínio criadas pelo projeto.
