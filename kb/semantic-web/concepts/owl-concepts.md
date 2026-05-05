# Conceitos OWL 2 — Web Ontology Language

> **Escopo atual:** OWL é o formato primário do projeto.
> **Roadmap:** RDF puro, SKOS, Turtle standalone, SPARQL endpoint e JSON-LD serão implementados em fases futuras.

---

## O que é OWL?

OWL (Web Ontology Language) é o padrão W3C para representar ontologias na web semântica.
Uma ontologia OWL descreve **o que existe** em um domínio e **como os conceitos se relacionam** —
de forma que tanto humanos quanto máquinas possam interpretar e raciocinar sobre ela.

OWL é construído sobre RDF (Resource Description Framework): toda ontologia OWL é também um
documento RDF válido, expresso em triples `(sujeito, predicado, objeto)`.

---

## Blocos Construtivos do OWL 2

### Classes (`owl:Class`)
Representam categorias ou tipos de entidades no domínio.

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <https://ontologia.empresa.com.br/rh/> .

ex:Funcionario a owl:Class ;
    rdfs:label "Funcionário"@pt, "Employee"@en ;
    rdfs:comment "Pessoa vinculada à empresa por relação empregatícia."@pt .

ex:Gerente a owl:Class ;
    rdfs:subClassOf ex:Funcionario ;
    rdfs:label "Gerente"@pt .
```

### Propriedades

**Object Properties** (`owl:ObjectProperty`) — relacionam dois indivíduos:
```turtle
ex:gerenciaEquipe a owl:ObjectProperty ;
    rdfs:domain ex:Gerente ;
    rdfs:range  ex:Equipe ;
    rdfs:label  "gerencia equipe"@pt .
```

**Datatype Properties** (`owl:DatatypeProperty`) — relacionam um indivíduo a um valor literal:
```turtle
ex:nomeCompleto a owl:DatatypeProperty ;
    rdfs:domain  ex:Funcionario ;
    rdfs:range   xsd:string ;
    rdfs:label   "nome completo"@pt .

ex:cpf a owl:DatatypeProperty ;
    rdfs:domain ex:Funcionario ;
    rdfs:range  xsd:string ;
    rdfs:comment "CPF mascarado (LGPD). Nunca armazenar em claro nesta ontologia."@pt .
```

**Annotation Properties** (`owl:AnnotationProperty`) — metadados sobre a ontologia:
```turtle
ex:versaoSistema a owl:AnnotationProperty ;
    rdfs:comment "Versão do sistema de origem que gerou este indivíduo."@pt .
```

### Indivíduos (`owl:NamedIndividual`)
Instâncias específicas das classes — a A-Box da ontologia:
```turtle
ex:joao_silva a owl:NamedIndividual, ex:Funcionario ;
    ex:nomeCompleto "João da Silva" ;
    ex:gerenciaEquipe ex:equipe_dados .
```

### Axiomas Essenciais

| Axioma                    | OWL                          | Significado                                        |
|--------------------------|------------------------------|----------------------------------------------------|
| Subclasse                | `rdfs:subClassOf`            | A é um tipo de B                                   |
| Equivalência             | `owl:equivalentClass`        | A e B representam o mesmo conceito                 |
| Disjunção                | `owl:disjointWith`           | Nenhum indivíduo pode ser A e B ao mesmo tempo     |
| Restrição de cardinalidade| `owl:minCardinality`, `owl:maxCardinality` | Limites numéricos para relações  |
| União                    | `owl:unionOf`                | A ou B                                             |
| Interseção               | `owl:intersectionOf`         | A e B                                              |

---

## Perfis OWL 2

| Perfil      | Expressividade | Decidibilidade | Uso Recomendado                                  |
|-------------|----------------|----------------|--------------------------------------------------|
| OWL 2 Full  | Máxima         | Não garantida  | Pesquisa — evitar em produção                    |
| **OWL 2 DL**| Alta           | **Garantida**  | **Padrão do projeto** — modelagem de domínio     |
| OWL 2 EL    | Média          | P-time         | Ontologias médicas grandes (SNOMED, GO)          |
| OWL 2 QL    | Baixa-Média    | LogSpace       | Consultas SQL sobre ontologias                   |
| OWL 2 RL    | Média          | P-time         | Sistemas de regras (RuleML, SWRL)                |

> **Regra do projeto:** Use **OWL 2 DL** salvo necessidade explícita de outro perfil.

---

## Formatos de Serialização

OWL não tem um formato único de arquivo — a mesma ontologia pode ser salva em qualquer
serialização RDF. As mais comuns:

### Turtle (`.ttl`) — padrão do projeto para desenvolvimento
```turtle
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix ex:   <https://ontologia.empresa.com.br/dominio/> .

<https://ontologia.empresa.com.br/dominio/>
    a owl:Ontology ;
    rdfs:label "Ontologia do Domínio"@pt ;
    owl:versionInfo "1.0.0" .
```

### RDF/XML (`.owl`, `.rdf`) — máxima interoperabilidade
```xml
<?xml version="1.0"?>
<rdf:RDF xmlns:owl="http://www.w3.org/2002/07/owl#"
         xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">
  <owl:Ontology rdf:about="https://ontologia.empresa.com.br/dominio/">
    <rdfs:label xml:lang="pt">Ontologia do Domínio</rdfs:label>
  </owl:Ontology>
</rdf:RDF>
```

### N-Triples (`.nt`) — ingestão em lote e Spark
```
<https://ontologia.empresa.com.br/rh/Funcionario> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> .
<https://ontologia.empresa.com.br/rh/Funcionario> <http://www.w3.org/2000/01/rdf-schema#label> "Funcionário"@pt .
```

### JSON-LD (`.jsonld`) — integração com APIs REST
```json
{
  "@context": {
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "ex": "https://ontologia.empresa.com.br/dominio/"
  },
  "@id": "ex:Funcionario",
  "@type": "owl:Class",
  "rdfs:label": [{"@value": "Funcionário", "@language": "pt"}]
}
```

---

## Namespaces — Convenção do Projeto

```
Base URI:    https://ontologia.empresa.com.br/
Padrão:      https://ontologia.empresa.com.br/<dominio>/
Exemplos:
  - https://ontologia.empresa.com.br/rh/         — RH e Pessoas
  - https://ontologia.empresa.com.br/financeiro/  — Financeiro
  - https://ontologia.empresa.com.br/produto/     — Catálogo de Produtos
  - https://ontologia.empresa.com.br/dados/       — Metadados de Engenharia de Dados
```

Cada arquivo de ontologia deve declarar seu próprio URI como `owl:Ontology` e versão via `owl:versionInfo`.

---

## Separação T-Box / A-Box

| Componente  | Conteúdo                           | Arquivo sugerido             |
|-------------|-------------------------------------|------------------------------|
| **T-Box**   | Classes, propriedades, axiomas      | `<dominio>_schema.ttl`       |
| **A-Box**   | Indivíduos, asserções de fatos      | `<dominio>_data.ttl`         |
| **Mapping** | OWL ↔ tabelas Delta                 | `<dominio>_mapping.ttl`      |

> Para domínios pequenos (< 10k indivíduos), T-Box e A-Box podem coexistir no mesmo arquivo.
> Para domínios grandes, separe T-Box (estável, versionada) de A-Box (volátil, gerada por pipeline).

---

## Bibliotecas Python

| Biblioteca    | Versão mín. | Uso Principal                                  | Instalação                   |
|---------------|-------------|------------------------------------------------|------------------------------|
| `rdflib`      | 7.0         | Parse, serialização, SPARQL in-memory, grafos  | `pip install rdflib`         |
| `owlready2`   | 0.47        | Manipulação OWL, reasoning (HermiT via Java)   | `pip install owlready2`      |
| `pyshacl`     | 0.25        | Validação de shapes SHACL (futuro)             | `pip install pyshacl`        |

> **Nota:** `owlready2` com reasoning requer Java ≥ 11. Em ambientes Fabric (Spark), use
> apenas `rdflib` por padrão — Java pode não estar disponível na versão do executor.

---

## Roadmap de Formatos (Fases Futuras)

| Fase | Formato / Padrão     | Capacidade Adicionada                                |
|------|---------------------|------------------------------------------------------|
| 1    | **OWL** ✅ (atual)  | Design, import/export, integração Fabric OneLake     |
| 2    | **SKOS**            | Vocabulários controlados, tesauros, taxonomias       |
| 3    | **SPARQL**          | Endpoint de consulta, federação entre grafos         |
| 4    | **RDF shapes/SHACL**| Validação de instâncias contra shapes                |
| 5    | **Linked Data**     | Publicação de URIs dereferenceable, content negoc.   |
