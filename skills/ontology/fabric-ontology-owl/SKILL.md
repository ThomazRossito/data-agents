---
name: fabric-ontology-owl
description: Engenharia de Ontologias OWL no Microsoft Fabric — import, export, design e integração com OneLake e Delta Lake.
updated_at: 2026-05-05
source: internal
---

# SKILL: Ontologias OWL no Microsoft Fabric

> **Formato atual:** OWL 2 (via rdflib / owlready2)
> **Roadmap:** SKOS, SPARQL endpoint, RDF shapes/SHACL (fases futuras)
>
> Leia `kb/semantic-web/index.md` antes de iniciar qualquer tarefa de ontologia.

---

## Pré-requisitos de Ambiente

```bash
# Instalar dependências de ontologia
pip install -e ".[ontology]"   # rdflib>=7.0, owlready2>=0.47

# Verificar instalação
python -c "import rdflib; print(rdflib.__version__)"
python -c "import owlready2; print(owlready2.__version__)"
```

Fabric Lakehouse necessário: `ontology_lh` com estrutura:
```
Files/ontologies/raw/       ← ontologias externas importadas
Files/ontologies/domain/    ← ontologias do domínio (T-Box)
Files/ontologies/instances/ ← instâncias geradas (A-Box)
Tables/ontology_triples/    ← Delta table de triples
```

---

## Playbook: Import de Ontologia Externa → Fabric

### Passo 1 — Identificar e Validar o Arquivo de Entrada

```python
from rdflib import Graph

def load_and_validate(path: str) -> dict:
    g = Graph()
    g.parse(path)  # rdflib detecta o formato automaticamente

    from rdflib.namespace import OWL, RDF
    classes   = sum(1 for _ in g.subjects(RDF.type, OWL.Class))
    obj_props = sum(1 for _ in g.subjects(RDF.type, OWL.ObjectProperty))
    data_props = sum(1 for _ in g.subjects(RDF.type, OWL.DatatypeProperty))
    individuals = sum(1 for _ in g.subjects(RDF.type, OWL.NamedIndividual))

    print(f"Triples: {len(g)}")
    print(f"Classes: {classes} | ObjProp: {obj_props} | DataProp: {data_props} | Indivíduos: {individuals}")
    return {"graph": g, "triple_count": len(g)}
```

### Passo 2 — Normalizar para Turtle (padrão do projeto)

```python
def normalize_to_turtle(input_path: str, output_path: str) -> None:
    """Converte qualquer formato OWL/RDF para Turtle normalizado."""
    g = Graph()
    g.parse(input_path)
    g.serialize(destination=output_path, format="turtle")
    print(f"Normalizado: {output_path} ({len(g)} triples)")
```

### Passo 3 — Upload para OneLake via MCP

```
Ferramenta: mcp__fabric_official__onelake_upload_file
Parâmetros:
  workspace_id:     <FABRIC_WORKSPACE_ID>
  lakehouse_name:   ontology_lh
  destination_path: ontologies/raw/<nome_original>
                    ontologies/domain/<nome_normalizado>.ttl
```

### Passo 4 — Ingestão em Delta via Spark Notebook

Ver padrão completo em `kb/semantic-web/patterns/owl-fabric-patterns.md` → "Padrão 3".

Checklist do notebook:
- [ ] `%pip install rdflib==7.1.1` no início do notebook
- [ ] Usar `abfss://` path para ler do OneLake Files
- [ ] Converter para DataFrame com schema `(subject, predicate, object, datatype, lang_tag, source_file)`
- [ ] Salvar em `ontology_lh.ontology_triples` com `mode="append"` e `CLUSTER BY (predicate)`
- [ ] Executar verificação: `SELECT COUNT(*) FROM ontology_lh.ontology_triples WHERE source_file = '<nome>'`

---

## Playbook: Export de Ontologia Fabric → Arquivo

### Passo 1 — Definir Escopo do Export

```sql
-- Verificar qual namespace/domínio exportar
SELECT DISTINCT
    REGEXP_EXTRACT(subject, 'https?://[^#/]+(?:/[^#/]+)*') AS namespace,
    COUNT(*) AS triple_count
FROM ontology_lh.ontology_triples
GROUP BY 1
ORDER BY 2 DESC;
```

### Passo 2 — Reconstruir Grafo no Spark

Ver padrão em `kb/semantic-web/patterns/owl-fabric-patterns.md` → "Padrão 4".

### Passo 3 — Serializar no Formato Solicitado

| Destino                    | Formato Recomendado | Extensão |
|---------------------------|---------------------|----------|
| Repositório Git / review  | turtle              | `.ttl`   |
| Protégé / Reasoner        | xml (RDF/XML)       | `.owl`   |
| Pipeline / Spark ingestão | nt                  | `.nt`    |
| API REST / Web            | json-ld             | `.jsonld`|
| Todos os formatos de uma vez | export_all_formats() | N/A   |

### Passo 4 — Upload para OneLake (seção export)

```
Ferramenta: mcp__fabric_official__onelake_upload_file
Parâmetros:
  destination_path: ontologies/export/<nome>_<YYYYMMDD>.<ext>
```

---

## Playbook: Design de Ontologia de Domínio (do Zero)

### Passo 1 — Entender o Domínio

Antes de escrever qualquer OWL:
- Listar as entidades principais (candidatas a classes)
- Identificar relações entre entidades (candidatas a object properties)
- Identificar atributos (candidatos a datatype properties)
- Confirmar com `governance-auditor` se alguma propriedade é PII

### Passo 2 — Definir o Namespace

```
Template: https://ontologia.empresa.com.br/<dominio>/
Exemplos:
  https://ontologia.empresa.com.br/rh/
  https://ontologia.empresa.com.br/financeiro/
  https://ontologia.empresa.com.br/produto/
```

### Passo 3 — Criar T-Box em Turtle

Usar o padrão em `kb/semantic-web/patterns/owl-python-patterns.md` → "Criar Ontologia do Zero".

Checklist mínimo para cada classe:
- [ ] `rdf:type owl:Class`
- [ ] `rdfs:label` em pt e en
- [ ] `rdfs:comment` em pt (descrição de negócio)
- [ ] `rdfs:subClassOf` (se for subclasse)

Checklist mínimo para cada propriedade:
- [ ] `rdf:type owl:ObjectProperty` ou `owl:DatatypeProperty`
- [ ] `rdfs:domain` declarado
- [ ] `rdfs:range` declarado
- [ ] `rdfs:label` em pt

### Passo 4 — Validar Estrutura

```python
from kb.semantic_web.patterns import validate_owl_structure  # padrão em owl-python-patterns.md

report = validate_owl_structure("minha_ontologia.ttl")
print(f"Valid: {report['valid']}")
for issue in report['issues']:
    print(f"  {issue}")
```

### Passo 5 — Gerar Relatório da Ontologia

```python
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS

def ontology_report(path: str) -> str:
    g = Graph()
    g.parse(path)

    classes = [(str(c), [str(l) for l in g.objects(c, RDFS.label)])
               for c in g.subjects(RDF.type, OWL.Class)]
    obj_props = [(str(p), str(next(g.objects(p, RDFS.domain), "?")),
                           str(next(g.objects(p, RDFS.range), "?")))
                 for p in g.subjects(RDF.type, OWL.ObjectProperty)]

    lines = [f"# Relatório da Ontologia: {path}",
             f"\nTotal de triples: {len(g)}",
             f"\n## Classes ({len(classes)})"]
    for uri, labels in sorted(classes):
        name = uri.split("/")[-1].split("#")[-1]
        lines.append(f"- {name}: {', '.join(labels) or '(sem label)'}")

    lines.append(f"\n## Object Properties ({len(obj_props)})")
    for uri, dom, rng in sorted(obj_props):
        name = uri.split("/")[-1].split("#")[-1]
        dom_name = dom.split("/")[-1].split("#")[-1]
        rng_name = rng.split("/")[-1].split("#")[-1]
        lines.append(f"- {name}: {dom_name} → {rng_name}")

    return "\n".join(lines)
```

---

## Boas Práticas e Armadilhas

### Fazer
- Sempre declarar `owl:Ontology` com `rdfs:label` e `owl:versionInfo`
- Usar `rdfs:comment` para descrever cada conceito em linguagem de negócio
- Separar T-Box (estável) de A-Box (volátil) quando volume > 10k indivíduos
- Versionar arquivos `.ttl` no Git — Turtle é diff-friendly
- Usar `CLUSTER BY (predicate)` na Delta table para performance

### Não Fazer
- **Não usar `owl:Thing` como range de ObjectProperty** sem restrição adicional
- **Não criar classes genéricas como "Entidade" ou "Objeto"** sem domínio específico
- **Não misturar OWL e SKOS** nesta fase — esperar roadmap de SKOS
- **Não armazenar valores PII como literais na ontologia** — usar blank nodes ou IDs mascarados
- **Não usar `owlready2` com reasoning em executores Spark** — usar no driver ou fora do cluster
- **Não criar propriedades sem `rdfs:domain` e `rdfs:range`** — compromete o reasoning

---

## Escalação

| Situação                                        | Escalar Para         |
|-------------------------------------------------|----------------------|
| Executar script rdflib localmente               | `python-expert`      |
| Criar Spark notebook no Fabric                  | `spark-expert`       |
| Propriedade detectada como PII                  | `governance-auditor` |
| Ontologia precisa alimentar Semantic Model BI   | `semantic-modeler`   |
| Formato de destino não listado nesta skill      | Consultar roadmap em `kb/semantic-web/index.md` |
