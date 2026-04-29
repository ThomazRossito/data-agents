# Fabric Data Factory

## Copy Activity vs Dataflow Gen2

| Critério | Copy Activity | Dataflow Gen2 |
|----------|--------------|----------------|
| Uso | Mover dados entre fontes | Transformar + carregar |
| Engine | Pipeline engine | Mashup (Power Query) |
| Scale | Alto (paralelismo nativo) | Médio |
| Código | JSON/config | GUI + M language |
| Melhor para | Ingestão raw → Bronze | Silver → Gold simples |

## Estrutura de Pipeline
```
Pipeline
├── Activities
│   ├── Copy Data          ← ingestão
│   ├── Dataflow Gen2      ← transformação
│   ├── Notebook           ← PySpark customizado
│   ├── Script             ← SQL inline
│   └── Wait / If Condition / ForEach
└── Parameters
    ├── source_path
    └── target_table
```

## Linked Services Comuns
| Serviços | Tipo |
|---------|------|
| Azure Blob / ADLS Gen2 | Cloud storage |
| Azure SQL Database | Relacional |
| REST API | HTTP |
| Lakehouse (OneLake) | Fabric native |
| Warehouse | Fabric native |

## Boas Práticas
- Parametrizar source/target em vez de hardcode
- Usar pipeline parameters + config-driven para multi-ambiente
- Prefer Copy Activity para volumes > 1 GB (mais rápido que Dataflow)
- Dataflow Gen2 para transformações visuais de times BI
- Monitorar via Monitoring Hub (erros, duração, CU)

## Monitoramento
```
Fabric Portal → Monitoring Hub → Pipeline runs
Filtrar por: workspace, status, data
Drill down em atividade com erro para ver detalhes de exception
```

## Padrão Config-Driven (recomendado)
```json
{
  "pipeline": "generic_copy",
  "parameters": {
    "source_type": "ADLS",
    "source_path": "@pipeline().parameters.source",
    "target_lakehouse": "@pipeline().parameters.lakehouse",
    "target_table": "@pipeline().parameters.table"
  }
}
```
