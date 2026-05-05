---
mcp_validated: "2026-05-05"
---

# KB: Web Semântica e Ontologias — Índice

**Domínio:** OWL, RDF, SKOS e padrões de web semântica aplicados ao ecossistema de dados.
**Agentes:** ontology-engineer

> **Escopo atual:** OWL é o formato primário implementado.
> **Roadmap:** RDF puro, SKOS, SPARQL, Turtle, N-Triples e JSON-LD serão cobertos em fases futuras.

---

## Conteúdo Disponível

### Conceitos (`concepts/`)

| Arquivo                                        | Conteúdo                                                                              |
|------------------------------------------------|---------------------------------------------------------------------------------------|
| `concepts/owl-concepts.md`                     | OWL 2: classes, propriedades, indivíduos, axiomas, perfis, formatos de serialização  |
| `concepts/onelake-rdf-storage-concepts.md`     | Como armazenar e processar arquivos OWL/RDF no Microsoft Fabric OneLake              |

### Padrões (`patterns/`)

| Arquivo                                        | Conteúdo                                                                              |
|------------------------------------------------|---------------------------------------------------------------------------------------|
| `patterns/owl-python-patterns.md`              | rdflib e owlready2: carregar, criar, serializar, consultar ontologias OWL            |
| `patterns/owl-fabric-patterns.md`              | Import/export de OWL no Fabric: OneLake Files → Spark → Delta                       |

---

## Regras Críticas

### OWL no Fabric — Limitações de Plataforma

- O Microsoft Fabric **não possui triple store nativo** nem endpoint SPARQL.
- Arquivos OWL/RDF são armazenados como **arquivos binários na seção Files do OneLake Lakehouse**.
- Processamento é feito via **Spark notebooks** com a biblioteca `rdflib` (Python).
- Para queries SPARQL complexas, use `rdflib` em memória ou serviço externo (Apache Jena Fuseki).
- Para consultas SQL sobre ontologias, converta triples para **tabela Delta** (subject, predicate, object).

### Formatos de Serialização OWL — Decisão de Formato

| Formato         | Extensão       | Melhor Para                              | Suporte rdflib |
|----------------|----------------|------------------------------------------|----------------|
| Turtle          | `.ttl`         | Leitura humana, versionamento Git        | ✅ Completo    |
| RDF/XML         | `.owl`, `.rdf` | Interoperabilidade máxima, legado        | ✅ Completo    |
| OWL/XML         | `.owx`         | Ferramentas OWL (Protégé, HermiT)        | ✅ Completo    |
| N-Triples       | `.nt`          | Ingestão em lote, streaming, Spark       | ✅ Completo    |
| JSON-LD         | `.jsonld`      | APIs REST, integração web                | ✅ Completo    |

> **Padrão do projeto:** Use **Turtle** (`.ttl`) para versionamento e colaboração. Use **N-Triples** para ingestão Spark. Use **RDF/XML** quando a ferramenta de destino exigir.

### Boas Práticas de Ontologia

- Defina **namespace próprio** para cada ontologia (`https://ontologia.empresa.com.br/<dominio>/`).
- Documente cada classe e propriedade com `rdfs:comment` e `rdfs:label` em português e inglês.
- Use **OWL 2 DL** como perfil padrão — balanceia expressividade e decidibilidade.
- Separe **T-Box** (schema: classes e propriedades) de **A-Box** (instâncias/indivíduos) em arquivos distintos quando o volume justificar.
- Para SKOS (vocabulários controlados), aguardar roadmap — não misturar SKOS com OWL nesta fase.

### Escalação de Responsabilidades

- **ontology-engineer** → design, validação, serialização e integração da ontologia.
- **python-expert** → execução de scripts rdflib locais, testes unitários de ontologia.
- **spark-expert** → notebooks Spark no Fabric para processamento de ontologias em escala.
- **governance-auditor** → alinhamento entre ontologia e metadados de governança (Unity Catalog tags, PII).
- **semantic-modeler** → mapeamento entre ontologia OWL e Semantic Model Power BI (se necessário).
