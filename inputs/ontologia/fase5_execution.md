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
7. Gerar arquivo output/retail_ontology_ingest.ipynb com o código Spark completo
   de ingestão Delta (limitação: core_create-item requer base64 IPYNB que o MCP não
   encoda — o .ipynb é gerado local para importação manual no Fabric)
8. Criar views SQL via fabric_sql:
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

Tudo criado automaticamente no Fabric, exceto a execução do notebook (limitação da API).
O relatório deve confirmar cada critério de aceite do SPEC aprovado — não apenas "funcionou".

---

## Após a execução

1. Importar o notebook no Fabric: **Home → Import Notebook → selecione `output/retail_ontology_ingest.ipynb`**
2. Executar o notebook com **Run All** para popular `ontology_triples`
2. Verificar no SQL Analytics: `SELECT COUNT(*) FROM ontology_triples` — deve retornar 180+ linhas
3. Verificar as views: `SELECT * FROM vw_retail_classes` — deve retornar 5 classes
4. Registrar a versão no histórico do SPEC (seção Histórico de Revisões)
