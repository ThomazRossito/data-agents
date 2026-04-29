# Fabric Lakehouse & OneLake

## OneLake como Base
OneLake é o storage unificado do Fabric — uma instância por tenant, multi-cloud (Azure/AWS/GCP). Todos os itens Fabric (Lakehouse, Warehouse, KQL DB) leem/escrevem em OneLake via Delta Parquet com ABFS.

## Estrutura de Pastas no Lakehouse
```
Lakehouse/
├── Tables/          ← Managed Delta tables (gerenciadas pelo Lakehouse)
│   ├── bronze/
│   ├── silver/
│   └── gold/
└── Files/           ← Unmanaged files (raw, configs, checkpoints)
    ├── raw/
    └── staging/
```
> **GA Abril/2026:** Nested folders agora suportados em `Tables/` — usar hierarquia por schema/domain.

## Lakehouse vs Warehouse — Quando Usar
| Preciso de... | Use |
|---------------|-----|
| Pipeline PySpark + SQL | Lakehouse |
| DWH + relatórios T-SQL | Warehouse |
| Dados vindos de Spark | Lakehouse |
| Self-service SQL por times BI | Warehouse |
| Shared tables multi-time | Lakehouse + shortcuts |

## Shortcuts
Shortcuts criam ponteiros para dados externos sem copiar. Aparecem como tabelas Delta no Lakehouse.

```
Lakehouse/Tables/external_sales → aponta para ADLS Gen2 container/path
```

**Boas práticas:**
- Usar shortcuts para dados que já existem em ADLS ou outro workspace
- Não criar shortcuts para dados temporários
- Permissão necessária: Storage Blob Data Reader na conta ADLS

## Mirroring
Fabric Mirroring replica dados externos (Azure SQL, Cosmos, Snowflake) para OneLake em tempo real via CDC.

```
Fonte → Mirroring → OneLake (Delta) → Lakehouse/Warehouse
```

## Direct Lake (Semantic Models)
Semantic models com Direct Lake leem Delta diretamente do OneLake — sem import nem DirectQuery.
- Fallback automático para DirectQuery se tabela exceder limites (ver patterns/direct-lake.md)
- Requirem tabelas Delta com parquet bem particionado

## Fabric Data Engineering Checklist
- [ ] Tabelas em `Tables/` para managed, `Files/` para raw/unmanaged
- [ ] Nomenclatura: `schema.nome_tabela` snake_case
- [ ] Particionamento por data para tabelas > 10M linhas
- [ ] OPTIMIZE + VACUUM agendados semanalmente
- [ ] Shortcuts documentados no catálogo (OneNote/Purview)
