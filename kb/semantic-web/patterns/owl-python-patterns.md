# Padrões Python — rdflib e owlready2

> **Pré-requisito:** `pip install -e ".[ontology]"` para instalar `rdflib` e `owlready2`.

---

## rdflib — Padrões Fundamentais

### Carregar Ontologia de Arquivo Local

```python
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import OWL, RDF, RDFS, XSD

g = Graph()

# Carrega a partir de arquivo — rdflib detecta o formato pelo conteúdo
g.parse("rh_schema.ttl")           # Turtle
g.parse("rh_schema.owl")           # RDF/XML (OWL)
g.parse("rh_schema.nt")            # N-Triples
g.parse("rh_schema.jsonld")        # JSON-LD

print(f"Triples carregados: {len(g)}")
```

### Carregar com Formato Explícito

```python
# Quando a extensão não define o formato (ex: arquivo sem extensão ou nome genérico)
g.parse("minha_ontologia", format="turtle")
g.parse("minha_ontologia", format="xml")       # RDF/XML
g.parse("minha_ontologia", format="nt")
g.parse("minha_ontologia", format="json-ld")
g.parse("minha_ontologia", format="n3")
```

### Serializar para Diferentes Formatos

```python
# Turtle — leitura humana, versionamento Git
ttl_bytes = g.serialize(format="turtle", encoding="utf-8")
with open("output.ttl", "wb") as f:
    f.write(ttl_bytes)

# RDF/XML — máxima interoperabilidade
g.serialize(destination="output.owl", format="xml")

# N-Triples — ingestão em lote / Spark
g.serialize(destination="output.nt", format="nt")

# JSON-LD — integração com APIs REST
g.serialize(destination="output.jsonld", format="json-ld", indent=2)

# OWL/XML — ferramentas como Protégé
g.serialize(destination="output.owx", format="xml")
```

### Converter Entre Formatos

```python
def convert_ontology(input_path: str, output_path: str, output_format: str) -> int:
    """
    Converte arquivo OWL/RDF entre formatos.
    Valida que nenhum triple foi perdido na conversão.
    Retorna número de triples ou lança ValueError se houver perda.
    """
    g = Graph()
    g.parse(input_path)
    triple_count_before = len(g)

    g.serialize(destination=output_path, format=output_format)

    # Validação de equivalência — roundtrip integrity
    g2 = Graph()
    g2.parse(output_path, format=output_format)
    triple_count_after = len(g2)

    if triple_count_before != triple_count_after:
        raise ValueError(
            f"Perda de triples na conversão {input_path} → {output_path}: "
            f"{triple_count_before} antes, {triple_count_after} depois. "
            f"Verifique se o formato de saída suporta todos os features da ontologia."
        )

    return triple_count_after

# Exemplos:
convert_ontology("schema.owl", "schema.ttl", "turtle")
convert_ontology("schema.ttl", "schema.nt", "nt")
convert_ontology("schema.rdf", "schema.jsonld", "json-ld")
```

---

## Criar Ontologia do Zero

```python
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import OWL, RDF, RDFS, XSD

# Definir namespaces do domínio
EX = Namespace("https://ontologia.empresa.com.br/rh/")

g = Graph()
g.bind("owl", OWL)
g.bind("rdfs", RDFS)
g.bind("xsd", XSD)
g.bind("ex", EX)

# Declarar a ontologia
ontology_uri = URIRef("https://ontologia.empresa.com.br/rh/")
g.add((ontology_uri, RDF.type, OWL.Ontology))
g.add((ontology_uri, RDFS.label, Literal("Ontologia de RH", lang="pt")))
g.add((ontology_uri, RDFS.label, Literal("HR Ontology", lang="en")))
g.add((ontology_uri, OWL.versionInfo, Literal("1.0.0")))

# Adicionar classe
g.add((EX.Funcionario, RDF.type, OWL.Class))
g.add((EX.Funcionario, RDFS.label, Literal("Funcionário", lang="pt")))
g.add((EX.Funcionario, RDFS.comment, Literal("Pessoa vinculada à empresa.", lang="pt")))

# Subclasse
g.add((EX.Gerente, RDF.type, OWL.Class))
g.add((EX.Gerente, RDFS.subClassOf, EX.Funcionario))
g.add((EX.Gerente, RDFS.label, Literal("Gerente", lang="pt")))

# Object Property
g.add((EX.gerenciaEquipe, RDF.type, OWL.ObjectProperty))
g.add((EX.gerenciaEquipe, RDFS.domain, EX.Gerente))
g.add((EX.gerenciaEquipe, RDFS.range, EX.Equipe))
g.add((EX.gerenciaEquipe, RDFS.label, Literal("gerencia equipe", lang="pt")))

# Datatype Property
g.add((EX.nomeCompleto, RDF.type, OWL.DatatypeProperty))
g.add((EX.nomeCompleto, RDFS.domain, EX.Funcionario))
g.add((EX.nomeCompleto, RDFS.range, XSD.string))
g.add((EX.nomeCompleto, RDFS.label, Literal("nome completo", lang="pt")))

# Adicionar indivíduo
g.add((EX.joao_silva, RDF.type, OWL.NamedIndividual))
g.add((EX.joao_silva, RDF.type, EX.Funcionario))
g.add((EX.joao_silva, EX.nomeCompleto, Literal("João da Silva")))

print(f"Ontologia criada com {len(g)} triples")
g.serialize(destination="rh_schema.ttl", format="turtle")
```

---

## SPARQL Queries In-Memory (rdflib)

```python
from rdflib import Graph

g = Graph()
g.parse("rh_schema.ttl")

# Listar todas as classes da ontologia
classes_query = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?class ?label WHERE {
    ?class a owl:Class .
    OPTIONAL { ?class rdfs:label ?label FILTER(lang(?label) = "pt") }
}
ORDER BY ?class
"""
for row in g.query(classes_query):
    print(f"Classe: {row.class_} — {row.label}")

# Listar hierarquia de classes
hierarchy_query = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>

SELECT ?subclass ?superclass WHERE {
    ?subclass rdfs:subClassOf ?superclass .
    ?subclass a owl:Class .
    ?superclass a owl:Class .
}
"""

# Listar propriedades e seus domínios/ranges
properties_query = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?prop ?type ?domain ?range ?label WHERE {
    ?prop a ?type .
    FILTER(?type IN (owl:ObjectProperty, owl:DatatypeProperty))
    OPTIONAL { ?prop rdfs:domain ?domain }
    OPTIONAL { ?prop rdfs:range ?range }
    OPTIONAL { ?prop rdfs:label ?label FILTER(lang(?label) = "pt") }
}
"""
```

---

## Extrair Triples como DataFrame (para Delta Lake)

```python
from rdflib import Graph
from rdflib.term import URIRef, Literal, BNode
import pandas as pd

def graph_to_dataframe(g: Graph, source_file: str = "", graph_uri: str = None) -> pd.DataFrame:
    """
    Converte grafo rdflib em DataFrame pandas para ingestão Delta.
    Schema canônico: subject, predicate, object, graph, datatype, lang_tag, source_file, loaded_at.
    """
    from datetime import datetime, timezone
    loaded_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for s, p, o in g:
        obj_str = str(o)
        datatype = None
        lang_tag = None

        if isinstance(o, Literal):
            datatype = str(o.datatype) if o.datatype else None
            lang_tag = o.language
        elif isinstance(o, BNode):
            obj_str = f"_:{str(o)}"

        rows.append({
            "subject":     str(s) if not isinstance(s, BNode) else f"_:{str(s)}",
            "predicate":   str(p),
            "object":      obj_str,
            "graph":       graph_uri,   # Named graph URI; None = grafo default
            "datatype":    datatype,
            "lang_tag":    lang_tag,
            "source_file": source_file,
            "loaded_at":   loaded_at,
        })

    return pd.DataFrame(rows)

# Uso
g = Graph()
g.parse("rh_schema.ttl")
df = graph_to_dataframe(g, source_file="rh_schema.ttl")
print(df.shape)
```

---

## owlready2 — Padrões para Manipulação OWL

> Use `owlready2` quando precisar de **reasoning OWL** (inferência de subclasses, consistência).
> Em ambientes Spark, prefira `rdflib` puro — `owlready2` com Java pode não estar disponível.

```python
from owlready2 import get_ontology, owl, Thing, sync_reasoner_pellet

# Carregar ontologia
onto = get_ontology("file:///path/to/rh_schema.owl").load()

# Inspecionar classes
for cls in onto.classes():
    print(f"Classe: {cls.name}")
    print(f"  Superclasses: {cls.is_a}")
    print(f"  Rótulo: {cls.label}")

# Criar nova classe programaticamente
with onto:
    class Estagiario(onto.Funcionario):
        pass
    Estagiario.label = ["Estagiário"]

# Salvar de volta
onto.save(file="rh_schema_updated.owl", format="rdfxml")

# Reasoning (requer Java ≥ 11 e HermiT/Pellet)
# sync_reasoner_pellet()
# for cls in onto.classes():
#     print(f"{cls.name} → inferred ancestors: {cls.ancestors()}")
```

---

## Validação de Ontologia

```python
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

# Namespaces placeholder que indicam que o namespace canônico não foi aplicado — ERROR
_PLACEHOLDER_NAMESPACES = (
    "http://example.org/",
    "http://www.example.com/",
    "http://example.com/",
    "https://example.org/",
    "http://test.org/",
)

def validate_owl_structure(path: str) -> dict:
    """
    Valida estrutura mínima e qualidade de uma ontologia OWL.
    Retorna relatório com issues classificados como ERROR ou WARN.
    'valid' = False se qualquer ERROR estiver presente.
    """
    g = Graph()
    g.parse(path)

    issues = []

    # ERROR: Namespace placeholder (deve usar namespace canônico do projeto)
    all_uris = set()
    for s, p, o in g:
        for node in (s, p, o):
            if isinstance(node, URIRef):
                all_uris.add(str(node))
    for uri in all_uris:
        for placeholder in _PLACEHOLDER_NAMESPACES:
            if uri.startswith(placeholder):
                issues.append(
                    f"ERROR: Namespace placeholder detectado em '{uri}'. "
                    f"Use 'https://ontologia.empresa.com.br/<dominio>/' como namespace canônico."
                )
                break

    # ERROR: Declaração owl:Ontology ausente
    ontologies = list(g.subjects(RDF.type, OWL.Ontology))
    if not ontologies:
        issues.append("ERROR: Nenhuma declaração owl:Ontology encontrada")
    else:
        ont_uri = ontologies[0]
        # WARN: owl:versionInfo ausente
        if not list(g.objects(ont_uri, OWL.versionInfo)):
            issues.append(f"WARN: owl:Ontology sem owl:versionInfo em {ont_uri}")
        # WARN: rdfs:label ausente
        if not list(g.objects(ont_uri, RDFS.label)):
            issues.append(f"WARN: owl:Ontology sem rdfs:label em {ont_uri}")

    # WARN: Classes sem rdfs:label
    for cls in g.subjects(RDF.type, OWL.Class):
        labels = list(g.objects(cls, RDFS.label))
        if not labels:
            issues.append(f"WARN: Classe {cls} sem rdfs:label")

    # ERROR: ObjectProperty com owl:Thing como range (proibido)
    # WARN: ObjectProperty sem rdfs:domain ou rdfs:range
    for prop in g.subjects(RDF.type, OWL.ObjectProperty):
        domain = list(g.objects(prop, RDFS.domain))
        range_ = list(g.objects(prop, RDFS.range))
        if not domain:
            issues.append(f"WARN: ObjectProperty {prop} sem rdfs:domain")
        if not range_:
            issues.append(f"WARN: ObjectProperty {prop} sem rdfs:range")
        elif OWL.Thing in range_:
            issues.append(
                f"ERROR: ObjectProperty {prop} usa owl:Thing como range — "
                f"declare um range específico."
            )

    # WARN: DatatypeProperty sem rdfs:domain ou rdfs:range
    for prop in g.subjects(RDF.type, OWL.DatatypeProperty):
        if not list(g.objects(prop, RDFS.domain)):
            issues.append(f"WARN: DatatypeProperty {prop} sem rdfs:domain")
        if not list(g.objects(prop, RDFS.range)):
            issues.append(f"WARN: DatatypeProperty {prop} sem rdfs:range")

    errors = [i for i in issues if i.startswith("ERROR")]
    return {
        "triple_count": len(g),
        "class_count": sum(1 for _ in g.subjects(RDF.type, OWL.Class)),
        "object_property_count": sum(1 for _ in g.subjects(RDF.type, OWL.ObjectProperty)),
        "datatype_property_count": sum(1 for _ in g.subjects(RDF.type, OWL.DatatypeProperty)),
        "individual_count": sum(1 for _ in g.subjects(RDF.type, OWL.NamedIndividual)),
        "issues": issues,
        "error_count": len(errors),
        "warn_count": len(issues) - len(errors),
        "valid": len(errors) == 0,
    }

def validate_owl_structure_from_graph(g: Graph) -> dict:
    """Versão que aceita Graph já carregado (sem re-parse)."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".ttl", delete=False) as tmp:
        g.serialize(destination=tmp.name, format="turtle")
        tmp_path = tmp.name
    result = validate_owl_structure(tmp_path)
    os.unlink(tmp_path)
    return result
```
