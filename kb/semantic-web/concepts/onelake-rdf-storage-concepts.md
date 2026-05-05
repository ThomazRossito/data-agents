# Armazenamento de OWL/RDF no Microsoft Fabric OneLake

---

## Realidade do Fabric: Sem Triple Store Nativo

O Microsoft Fabric **não possui** triple store nativo nem endpoint SPARQL. Toda integração
com arquivos OWL/RDF no Fabric é feita via camadas de armazenamento e processamento convencionais:

```
OneLake Files          ← armazenamento bruto: .ttl, .owl, .rdf, .nt, .jsonld
    ↓
Spark Notebook (rdflib) ← processamento: parse, transform, validação
    ↓
Delta Table (triples)   ← armazenamento estruturado: subject, predicate, object, graph
    ↓
SQL Analytics Endpoint  ← consultas SQL sobre a ontologia
```

Para SPARQL queries sobre a ontologia completa, `rdflib` é usado **em memória** dentro de
um Spark driver — não existe SPARQL federado ou endpoint HTTP nativo no Fabric.

---

## Estrutura de Diretórios no OneLake Lakehouse

```
Lakehouse: ontology_lh
├── Files/
│   └── ontologies/
│       ├── raw/                   ← ontologias brutas importadas de fontes externas
│       │   ├── schema_org_v25.ttl
│       │   └── obo_go_2024.owl
│       ├── domain/                ← ontologias do domínio (T-Box)
│       │   ├── rh_schema_v1.ttl
│       │   ├── financeiro_schema_v2.ttl
│       │   └── dados_schema_v1.ttl
│       └── instances/             ← instâncias geradas por pipeline (A-Box)
│           ├── rh_data_2026_05.nt
│           └── financeiro_data_2026_05.nt
└── Tables/
    ├── ontology_triples/          ← todos os triples em formato Delta
    ├── ontology_classes/          ← view das classes extraídas
    └── ontology_properties/       ← view das propriedades extraídas
```

---

## Fluxo de Import (Externo → OneLake → Delta)

```
1. Arquivo OWL externo (.ttl / .owl / .nt)
        ↓ (upload via fabric_official MCP ou manualmente)
2. OneLake Files/ontologies/raw/
        ↓ (Spark notebook com rdflib)
3. Parse em Graph rdflib
        ↓ (serializar triples como rows)
4. PySpark DataFrame: (subject, predicate, object, graph, source_file, loaded_at)
        ↓ (salvar em Delta com V-Order)
5. Delta Table: ontology_lh.ontology_triples
        ↓ (views SQL para classes, propriedades, indivíduos)
6. SQL Analytics Endpoint para queries ad-hoc
```

---

## Fluxo de Export (Delta → OneLake → Arquivo)

```
1. Delta Table: ontology_lh.ontology_triples (ou T-Box isolado)
        ↓ (Spark notebook: rows → rdflib Graph)
2. Reconstrução do grafo rdflib
        ↓ (serializar no formato alvo)
3. Arquivo .ttl / .owl / .nt / .jsonld em memória
        ↓ (upload para OneLake Files ou download direto)
4. OneLake Files/ontologies/export/<nome>_<data>.<ext>
```

---

## Schema da Tabela Delta de Triples

```sql
CREATE TABLE ontology_lh.ontology_triples (
    subject     STRING NOT NULL,   -- URI ou blank node
    predicate   STRING NOT NULL,   -- URI do predicado
    object      STRING NOT NULL,   -- URI, blank node, ou literal com type/lang
    graph       STRING,            -- Named graph (null = default graph)
    datatype    STRING,            -- XSD datatype para literais (null para URIs)
    lang_tag    STRING,            -- Language tag (pt, en) para strings literais
    source_file STRING,            -- arquivo de origem
    loaded_at   TIMESTAMP          -- timestamp de carga
)
USING DELTA
CLUSTER BY (predicate)  -- cluster por predicado acelera queries por tipo de relação
```

> O cluster por `predicate` permite filtrar eficientemente por tipo de relação
> (ex: todas as `rdfs:subClassOf`, todos os `rdf:type owl:Class`).

---

## Autenticação OneLake via MCP

O MCP oficial da Microsoft (`fabric_official`) usa autenticação Azure:
- Credencial lida automaticamente via `az login` ou Service Principal no `.env`.
- Ferramentas disponíveis: `onelake_upload_file`, `onelake_download_file`,
  `onelake_list_files`, `onelake_delete_file`, `onelake_create_directory`.

Para ambientes sem `az login` (automação, CI/CD), configure Service Principal no `.env`:
```
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
FABRIC_WORKSPACE_ID=...
```

---

## Limitações Conhecidas

| Limitação                              | Impacto                                    | Workaround                                     |
|----------------------------------------|--------------------------------------------|------------------------------------------------|
| Sem SPARQL endpoint nativo             | Não há HTTP endpoint para SPARQL           | `rdflib` em-memória no Spark driver            |
| Sem triple store persistente           | Grafo não é first-class citizen no Fabric  | Delta table de triples como store              |
| `owlready2` reasoning exige Java ≥ 11  | Pode falhar em executores Spark            | Usar rdflib puro; reasoning fora do Spark      |
| OneLake sem suporte nativo a Content Negotiation | Não serve `.ttl` vs `.jsonld` por Accept header | Arquivo estático por formato |
| Arquivos grandes (> 1GB) de N-Triples  | Parse `rdflib` em driver pode usar muita RAM | Usar Spark RDF parser (spark-rdf ou custom UDF)|

---

## Decisão: Quando Usar Cada Abordagem

| Cenário                                      | Abordagem Recomendada                           |
|----------------------------------------------|-------------------------------------------------|
| Ontologia pequena (< 100k triples), leitura  | `rdflib` em Spark driver, memória               |
| Ontologia grande (> 100k triples), ingestão  | N-Triples + Spark para Delta table              |
| Queries pontuais sobre classes/propriedades  | SQL no `ontology_triples` Delta table           |
| SPARQL complexo com múltiplas classes        | `rdflib` em-memória no driver                  |
| Publicação para sistemas externos (APIs)     | Export para arquivo + `onelake_download_file`  |
| Versionamento / colaboração                  | Turtle (`.ttl`) no OneLake Files + Delta de backup |
