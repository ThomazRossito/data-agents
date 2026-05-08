---
name: owl-to-fabric-iq
description: "Protocolo de bridge OWL 2 → Fabric IQ Ontology. Mapeia classes OWL para entity types, object properties para relationship types, datatype properties para propriedades de entity type, e axiomas OWL para contextualizations. Use ao importar ou sincronizar um modelo OWL para o Fabric IQ Ontology via MCP."
updated_at: 2026-05-08
source: internal
---

# SKILL: Bridge OWL 2 → Fabric IQ Ontology

> **Pré-requisito:** `fabric-ontology-mcp` instalado e `az login` executado.
> Ferramentas via `fabric_ontology_all` — ver `mcp_servers/fabric_ontology/server_config.py`.

---

## Mapeamento Conceitual

| Construto OWL 2           | Fabric IQ Ontology               | Ferramenta MCP                  |
|---------------------------|----------------------------------|---------------------------------|
| `owl:Class`               | Entity Type                      | `add_entity_type`               |
| `owl:DatatypeProperty`    | Property no Entity Type          | `add_property`                  |
| `owl:ObjectProperty`      | Relationship Type                | `add_relationship_type`         |
| `owl:NamedIndividual`     | Instância (fora do escopo do IQ) | —                               |
| `owl:Restriction`         | Contextualization                | `add_contextualization`         |
| Delta table / Lakehouse   | Data Binding                     | `add_data_binding`              |

### Tabela de Tipos de Dados

| OWL / XSD Range        | Fabric `valueType` |
|------------------------|--------------------|
| `xsd:string`, `rdfs:Literal` | `"String"`   |
| `xsd:boolean`          | `"Boolean"`        |
| `xsd:dateTime`, `xsd:date` | `"DateTime"`   |
| `xsd:integer`, `xsd:long`, `xsd:int` | `"BigInt"` |
| `xsd:double`, `xsd:float`, `xsd:decimal` | `"Double"` |
| `owl:Thing` (range genérico) | `"Object"`    |

---

## Protocolo de Import (passo a passo)

### Passo 0 — Descoberta

```
# Listar workspaces e ontologias existentes
mcp__fabric_ontology__list_workspaces()
mcp__fabric_ontology__list_ontologies(workspace_id="<FABRIC_WORKSPACE_ID>")
```

Anotar `workspace_id` e `ontology_id`. Se a ontologia ainda não existe:

```
mcp__fabric_ontology__create_ontology(
    workspace_id="<FABRIC_WORKSPACE_ID>",
    display_name="<Nome da Ontologia>",
    description="<Descrição curta>"
)
```

---

### Passo 1 — Extrair Classes OWL → Entity Types

```python
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS

g = Graph()
g.parse("minha_ontologia.ttl")

entity_types = []
for cls in g.subjects(RDF.type, OWL.Class):
    name_raw = str(cls).split("/")[-1].split("#")[-1]
    label = next(g.objects(cls, RDFS.label), name_raw)
    comment = next(g.objects(cls, RDFS.comment), "")
    entity_types.append({
        "owl_uri": str(cls),
        "name": name_raw,          # será o ID no Fabric IQ
        "display_name": str(label),
        "description": str(comment),
    })
```

Para cada entity type extraído:

```
mcp__fabric_ontology__add_entity_type(
    workspace_id="<FABRIC_WORKSPACE_ID>",
    ontology_id="<ONTOLOGY_ID>",
    name="<name>",                      # slug único — sem espaços
    display_name="<display_name>",
    description="<description>"          # opcional
)
```

**Regra de nomenclatura:** `name` deve ser `[a-zA-Z][a-zA-Z0-9_-]{0,127}`. Usar o fragmento
URI (parte após `#` ou último `/`) como base. Substituir espaços por `_`.

---

### Passo 2 — Extrair DatatypeProperties → Properties

```python
for prop in g.subjects(RDF.type, OWL.DatatypeProperty):
    name = str(prop).split("/")[-1].split("#")[-1]
    domain = next(g.objects(prop, RDFS.domain), None)
    range_uri = str(next(g.objects(prop, RDFS.range), ""))
    label = next(g.objects(prop, RDFS.label), name)

    # Mapear xsd type → valueType Fabric
    value_type = _XSD_TO_FABRIC.get(range_uri.split("#")[-1].lower(), "String")

    if domain:
        et_name = str(domain).split("/")[-1].split("#")[-1]
        yield {
            "entity_type": et_name,
            "prop_name": name,
            "display_name": str(label),
            "value_type": value_type,
        }

_XSD_TO_FABRIC = {
    "string": "String", "boolean": "Boolean",
    "datetime": "DateTime", "date": "DateTime",
    "integer": "BigInt", "long": "BigInt", "int": "BigInt",
    "double": "Double", "float": "Double", "decimal": "Double",
}
```

Para cada property:

```
mcp__fabric_ontology__add_property(
    workspace_id="<FABRIC_WORKSPACE_ID>",
    ontology_id="<ONTOLOGY_ID>",
    entity_type_name="<et_name>",
    name="<prop_name>",
    value_type="String",                # ou conforme tabela acima
    display_name="<label>",
    nullable=True
)
```

---

### Passo 3 — Extrair ObjectProperties → Relationship Types

```python
for prop in g.subjects(RDF.type, OWL.ObjectProperty):
    name = str(prop).split("/")[-1].split("#")[-1]
    domain = next(g.objects(prop, RDFS.domain), None)
    range_cls = next(g.objects(prop, RDFS.range), None)
    label = next(g.objects(prop, RDFS.label), name)

    if domain and range_cls:
        source_et = str(domain).split("/")[-1].split("#")[-1]
        target_et = str(range_cls).split("/")[-1].split("#")[-1]
        yield {
            "name": name,
            "display_name": str(label),
            "source_entity_type": source_et,
            "target_entity_type": target_et,
        }
```

Para cada relationship type:

```
mcp__fabric_ontology__add_relationship_type(
    workspace_id="<FABRIC_WORKSPACE_ID>",
    ontology_id="<ONTOLOGY_ID>",
    name="<name>",
    display_name="<display_name>",
    source_entity_type_name="<source_et>",
    target_entity_type_name="<target_et>"
)
```

---

### Passo 4 — Mapear Delta Tables → Data Bindings

Após criar os entity types, vincular cada um a sua tabela Delta correspondente:

```
mcp__fabric_ontology__add_data_binding(
    workspace_id="<FABRIC_WORKSPACE_ID>",
    ontology_id="<ONTOLOGY_ID>",
    entity_type_name="<et_name>",
    lakehouse_id="<LAKEHOUSE_ID>",
    table_name="<schema.table_name>",
    node_key_columns=["<pk_column>"]    # chave de identificação única da linha
)
```

Para descobrir as tabelas disponíveis:

```
mcp__fabric_ontology__discover_lakehouse_tables(
    workspace_id="<FABRIC_WORKSPACE_ID>",
    lakehouse_id="<LAKEHOUSE_ID>"
)
```

---

### Passo 5 — Mapear owl:Restriction → Contextualizations

Contextualizations conectam um relationship type a tabelas reais, definindo quais colunas
fazem o join entre entidade origem e entidade destino.

```
mcp__fabric_ontology__add_contextualization(
    workspace_id="<FABRIC_WORKSPACE_ID>",
    ontology_id="<ONTOLOGY_ID>",
    relationship_type_name="<rel_name>",
    source_lakehouse_id="<SOURCE_LH_ID>",
    source_table_name="<source_table>",
    source_node_key_columns=["<fk_column>"],     # FK na tabela origem
    destination_lakehouse_id="<DEST_LH_ID>",
    destination_table_name="<dest_table>",
    destination_node_key_columns=["<pk_column>"] # PK na tabela destino
)
```

**Armadilha crítica:** `destination_node_key_columns` deve apontar para a **PK da tabela
destino**, não para a coluna FK da origem. Erro aqui resulta em 0 rows no grafo.

Exemplo correto para `FactSales → DimProduct`:
```
source_table_name="FactSales",
source_node_key_columns=["ProductId"],         # FK em FactSales
destination_table_name="DimProduct",
destination_node_key_columns=["ProductId"]     # PK em DimProduct ← CORRETO
```

Exemplo incorreto (resulta em 0 rows):
```
destination_node_key_columns=["StoreId"]       # ← ERRADO: chave de outra dimensão
```

---

### Passo 6 — Verificação

```
# Inspecionar estado final
mcp__fabric_ontology__get_ontology(
    workspace_id="<FABRIC_WORKSPACE_ID>",
    ontology_id="<ONTOLOGY_ID>"
)

# Listar entity types criados
mcp__fabric_ontology__list_entity_types(
    workspace_id="<FABRIC_WORKSPACE_ID>",
    ontology_id="<ONTOLOGY_ID>"
)

# Listar relationship types criados
mcp__fabric_ontology__list_relationship_types(
    workspace_id="<FABRIC_WORKSPACE_ID>",
    ontology_id="<ONTOLOGY_ID>"
)

# Preview de uma tabela de dados para confirmar binding
mcp__fabric_ontology__preview_lakehouse_table(
    workspace_id="<FABRIC_WORKSPACE_ID>",
    lakehouse_id="<LAKEHOUSE_ID>",
    table_name="<tabela>"
)
```

---

## Casos Especiais

### Classes sem domain/range declarado

Se uma `owl:ObjectProperty` não tiver `rdfs:domain` ou `rdfs:range` declarados, **não criar**
o relationship type automaticamente. Reportar ao usuário e perguntar quais entity types
deve conectar.

### Hierarquia de Classes (`rdfs:subClassOf`)

O Fabric IQ Ontology não tem conceito nativo de hierarquia de entity types. Estratégias:
1. **Achatamento:** criar entity types independentes para cada subclasse, duplicando propriedades
2. **Herança via propriedade:** adicionar property `parentType: String` ao entity type filho
3. **Documentação apenas:** adicionar `description` com `subClassOf: <NomePai>` no entity type

Escolher conforme complexidade. Estratégia 1 é a mais simples para começar.

### OWL com múltiplos domínios

`rdfs:domain` pode ser um `owl:unionOf` com múltiplas classes. Nesse caso, criar um
relationship type separado para cada combinação (domain_i, range).

---

## Escalação

| Situação                                        | Ação                              |
|-------------------------------------------------|-----------------------------------|
| `name` inválido (caracteres especiais, URI longa) | Normalizar: slug ASCII ≤128 chars |
| Property com range desconhecido                 | Usar `"String"` como default      |
| Contextualization retorna 0 rows                | Verificar `destination_node_key_columns` — ver seção acima |
| Erro 403 ao chamar MCP                          | Executar `az login` e tentar novamente |
| Ontologia já existe e precisa ser atualizada    | Usar skill `fabric-ontology-owl` → seção "Schema Sync" |
