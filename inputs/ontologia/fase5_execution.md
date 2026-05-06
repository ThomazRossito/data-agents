# Fase 5 — Execution: Gerar a Ontologia no Fabric

**Agente:** `/ontology`
**Pré-requisito:** `output/ontologia/fase3_spec.md` aprovado (checklist seção 9 preenchido)
**Produz:**
- `output/ontologia/fase5_execution_report.md`
- `output/retail_ontology.ttl` (local)
- `Files/ontologies/domain/retail_ontology.ttl` (OneLake)
- Notebook Spark criado no workspace Fabric
- Views SQL executadas no SQL Analytics Endpoint

---

## Prompt

```
/ontology

Leia o documento de especificação aprovado em output/ontologia/fase3_spec.md
e execute a criação completa da ontologia OWL 2 no Microsoft Fabric.

IMPORTANTE: o SPEC é a fonte de verdade. Se houver qualquer decisão de design
no SPEC que difira da inferência automática padrão (Padrão 10), o SPEC prevalece.

Lakehouse de origem: OntologiaDataLH
Workspace: Workspace Ontologia
Namespace: https://ontologia.empresa.com.br/retail/
Versão: 1.0.0

Execute os 8 passos do Padrão 10 (kb/semantic-web/patterns/owl-fabric-patterns.md):

1. Listar e confirmar as tabelas no Lakehouse via MCP
2. Inspecionar schema de cada tabela
3. Inferir T-Box conforme as decisões documentadas no SPEC
   - Classes: exatamente as definidas na seção 2 do SPEC
   - Object Properties: exatamente as definidas na seção 3 do SPEC
   - Datatype Properties: exatamente as definidas na seção 4 do SPEC
   - Axiomas: conforme seção 5 do SPEC
4. Validar com validate_owl_structure_from_graph() — zero ERRORs obrigatório
   Verificar também os critérios de aceite da seção 7 do SPEC
5. Serializar em output/retail_ontology.ttl
6. Upload para Files/ontologies/domain/retail_ontology.ttl no OntologiaDataLH
7. Criar o notebook no workspace Fabric:
   - Gerar output/retail_ontology_ingest.ipynb com código Spark completo
   - Encodar em base64 via Bash e criar no Fabric via core_create-item
   - Se falhar: instruir importação manual
8. Criar views SQL dentro do notebook (última célula) — executadas no Run All:
   - vw_retail_classes
   - vw_retail_properties
   - vw_class_hierarchy

Gerar relatório final em output/ontologia/fase5_execution_report.md com:
- Status de cada um dos 8 passos (OK / WARN / ERROR)
- Comparação entre o SPEC aprovado e o que foi gerado (desvios, se houver)
- Critérios de aceite da seção 7 do SPEC: cada um passou ou falhou?
- Instrução explícita ao usuário: executar o notebook "retail_ontology_ingest"
  no workspace Fabric com Run All para popular a tabela Delta ontology_triples
```

---

## O que esperar no output

Tudo criado automaticamente no Fabric: TTL no OneLake, notebook criado no workspace, views SQL
geradas pela última célula do notebook. A única ação manual é o **Run All** do notebook.

O relatório deve confirmar cada critério de aceite do SPEC aprovado — não apenas "funcionou".

**Pré-requisito:** `AGENT_PERMISSION_MODE=bypassPermissions` no `.env` e service principal
(`AZURE_CLIENT_ID`) adicionado como **Contributor** no workspace Fabric (Manage Access).
Verificar também: Fabric Admin Portal → Tenant Settings → Developer Settings →
"Allow service principals to use Fabric APIs" habilitado.

---

## Após a execução

1. Abrir o notebook **retail_ontology_ingest** criado no workspace Fabric
2. Executar com **Run All** para popular `ontology_triples` e criar as views
3. Verificar no SQL Analytics: `SELECT COUNT(*) FROM ontology_triples` — deve retornar 180+ linhas
4. Verificar as views: `SELECT * FROM vw_retail_classes` — deve retornar 5 classes
5. Registrar a versão no histórico do SPEC (seção Histórico de Revisões)
