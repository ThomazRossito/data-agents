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

---

## Padrão 10: Delta Schema → Ontologia OWL (Reverse Mapping)

> Use quando o usuário quer gerar uma ontologia a partir de tabelas Delta Lake existentes
> no Fabric (Lakehouse). O agente inspeciona o schema das tabelas e infere a T-Box OWL 2.

### Mapeamento de Tipos Spark → XSD

| Tipo Spark / Delta | Tipo XSD OWL |
|--------------------|-------------|
| StringType         | xsd:string  |
| IntegerType        | xsd:integer |
| LongType           | xsd:long    |
| DoubleType         | xsd:double  |
| FloatType          | xsd:float   |
| BooleanType        | xsd:boolean |
| DateType           | xsd:date    |
| TimestampType      | xsd:dateTime|
| DecimalType(p,s)   | xsd:decimal |
| ArrayType          | *(ignorar — sem equivalente direto em OWL 2 DL)* |
| MapType            | *(ignorar — sem equivalente direto em OWL 2 DL)* |
| StructType aninhado| *(criar classe auxiliar + ObjectProperty)* |

### Convenção de Inferência de Classes e Propriedades

```
Tabela         → owl:Class  (nome em PascalCase singular, ex: dim_products → Product)
Coluna simples → owl:DatatypeProperty  (nome camelCase, ex: product_name → hasProductName)
Coluna *Key / *ID / *Id (FK aparente) → owl:ObjectProperty candidata (inferência heurística)
Coluna PK (primary key)               → owl:DatatypeProperty + anotação rdfs:comment "primary key"
```

**Regra de nomeação:**
- Remover prefixos `dim`, `fact`, `fct`, `lkp`, `ref` do nome da classe
- Converter `snake_case` → `PascalCase` para classes e `camelCase` para propriedades
- Prefixar datatype properties com `has` (ex: `hasProductName`, `hasSaleDate`)
- Object properties: verbo semântico preferido (ex: `soldProduct`, `locatedAt`); se não inferível, usar `relatesTo<NomeClasse>`

### Estratégia de Inferência de Object Properties (FK)

```
1. Colunas cujo nome termina em Key, ID, Id, _id, _key → candidatas FK
2. Verificar se o prefixo do nome corresponde a outra tabela do Lakehouse
   ex: ProductKey em factsales → dimproducts → ObjectProperty Sale → Product
3. Se correspondência encontrada: criar ObjectProperty + rdfs:domain + rdfs:range explícitos
4. Se ambígua ou não encontrada: criar como DatatypeProperty (xsd:long) + WARN no relatório
5. NUNCA usar owl:Thing como range — se range for incerto, omitir range e registrar WARN
```

### Protocolo de Execução (8 Passos)

```python
# PASSO 1 — Listar tabelas do Lakehouse alvo
# tables = mcp__fabric_community__list_tables(
#     workspace_id   = "<FABRIC_WORKSPACE_ID>",
#     lakehouse_name = "<nome_lakehouse>"
# )

# PASSO 2 — Inspecionar schema de cada tabela
# for table in tables:
#     schema = mcp__fabric_community__get_table_schema(
#         workspace_id   = "<FABRIC_WORKSPACE_ID>",
#         lakehouse_name = "<nome_lakehouse>",
#         table_name     = table
#     )

# PASSO 3 — Inferir T-Box
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import OWL, RDF, RDFS, XSD

DOMAIN = Namespace("https://ontologia.empresa.com.br/<dominio>/")
g = Graph()
g.bind("owl", OWL); g.bind("rdfs", RDFS); g.bind("xsd", XSD)
g.bind("<prefixo>", DOMAIN)

ont_uri = URIRef("https://ontologia.empresa.com.br/<dominio>/")
g.add((ont_uri, RDF.type, OWL.Ontology))
g.add((ont_uri, RDFS.label, Literal("<Nome> Ontologia", lang="pt")))
g.add((ont_uri, OWL.versionInfo, Literal("1.0.0")))

# Para cada tabela → classe; para cada coluna → DatatypeProperty ou ObjectProperty

# PASSO 4 — Validar (zero ERRORs antes de prosseguir)
# report = validate_owl_structure_from_graph(g)
# if not report["valid"]:
#     raise ValueError(f"ERRORs: {[i for i in report['issues'] if i.startswith('ERROR')]}")

# PASSO 5 — Serializar localmente
# g.serialize(destination="output/<dominio>_ontology.ttl", format="turtle")

# PASSO 6 — Upload do TTL para OneLake Files
# mcp__fabric_official__onelake_upload_file(
#     workspace_id     = "<FABRIC_WORKSPACE_ID>",
#     lakehouse_name   = "<nome_lakehouse>",
#     destination_path = "ontologies/domain/<dominio>_ontology.ttl",
#     local_file_path  = "output/<dominio>_ontology.ttl"
# )

# PASSO 7 — Gerar arquivo .ipynb localmente com o código de ingestão Delta
#
# LIMITAÇÃO CONHECIDA: mcp__fabric_official__core_create-item para notebooks requer
# o payload definition encodado em base64 no formato IPYNB, que o MCP oficial não
# encoda automaticamente. Tentativas de criar notebooks via MCP resultam em erro de payload.
#
# ALTERNATIVA CORRETA: gerar o arquivo .ipynb localmente e instruir o usuário a
# importá-lo no Fabric (Home → Import Notebook → selecionar o arquivo).
#
# O agente deve:
# 1. Gerar o arquivo output/<dominio>_ontology_ingest.ipynb com o código Spark completo
# 2. Informar ao usuário: "Importe o notebook no Fabric: Home → Import Notebook →
#    selecione output/<dominio>_ontology_ingest.ipynb → Execute Run All"
#
# Estrutura mínima do .ipynb:
# {
#   "nbformat": 4, "nbformat_minor": 2,
#   "metadata": {"language_info": {"name": "python"}, "kernelspec": {"name": "synapse_pyspark"}},
#   "cells": [
#     {"cell_type": "code", "source": ["# %pip install rdflib==7.1.1\n", ...], "outputs": [], "metadata": {}}
#   ]
# }

# PASSO 8 — Criar views SQL no SQL Analytics Endpoint via fabric_sql
# Executar cada CREATE OR REPLACE VIEW diretamente. Não gerar código apenas — executar.
#
# mcp__fabric_sql__fabric_sql_execute(
#     query = """
#     CREATE OR REPLACE VIEW vw_<dominio>_classes AS
#     SELECT subject AS class_uri, ...
#     FROM <lakehouse>.ontology_triples
#     WHERE predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
#       AND object    = 'http://www.w3.org/2002/07/owl#Class'
#       AND subject LIKE 'https://ontologia.empresa.com.br/<dominio>/%'
#     """
# )
#
# mcp__fabric_sql__fabric_sql_execute(
#     query = """
#     CREATE OR REPLACE VIEW vw_<dominio>_properties AS
#     SELECT t1.subject AS property_uri, t1.object AS property_type, ...
#     FROM <lakehouse>.ontology_triples t1 ...
#     WHERE t1.predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
#       AND t1.object IN ('http://www.w3.org/2002/07/owl#ObjectProperty',
#                         'http://www.w3.org/2002/07/owl#DatatypeProperty')
#     """
# )
#
# NOTA: As views só funcionam após o Notebook (Passo 7) ser executado pelo usuário,
# pois dependem da tabela ontology_triples estar populada.
```

### O que fica pronto automaticamente vs. manual

| Item | Automático (agente) | Manual (usuário) |
|------|---------------------|------------------|
| Arquivo `.ttl` no OneLake Files | Passo 6 | — |
| Arquivo `.ipynb` gerado localmente | Passo 7 | — |
| Notebook importado no workspace Fabric | — | Home → Import Notebook → selecionar o `.ipynb` |
| Tabela Delta `ontology_triples` populada | — | Clicar "Run All" no notebook importado |
| Views SQL criadas | Passo 8 | — (executa após o notebook) |

> **Limitação de API:** `core_create-item` para notebooks requer payload base64 IPYNB que
> o MCP oficial não encoda automaticamente. O agente gera o `.ipynb` localmente — o usuário
> importa no Fabric em 3 cliques (Home → Import Notebook → arquivo).
>
> As views SQL (Passo 8) dependem de `ontology_triples` existir. O agente DEVE informar
> ao usuário que precisa importar e executar o notebook antes das views ficarem funcionais.

### Relatório Mínimo Esperado

O agente deve produzir ao final um `output/<dominio>_ontology.md` com:
- Tabela origem → Classe OWL gerada
- Colunas → Properties (tipo, range XSD/classe)
- Object Properties inferidas (FK encontradas)
- WARNs de colunas ignoradas (ArrayType, ambíguas) ou FKs não resolvidas
- Contagem: classes, datatype properties, object properties, triples totais
- Status de cada passo do protocolo (1–8)
- Instrução explícita ao usuário: executar o notebook `<dominio>_ontology_ingest` no Fabric

> `domain/` é reservado para ontologias de domínio criadas pelo projeto.
