---
mcp_validated: "2026-04-15"
---

# KB: Microsoft Fabric — Índice

**Domínio:** Arquitetura, padrões e boas práticas do Microsoft Fabric.
**Agentes:** pipeline-architect, sql-expert, semantic-modeler

---

## Conteúdo Disponível

### Conceitos (`concepts/`)

| Arquivo                                  | Conteúdo                                                              |
|------------------------------------------|-----------------------------------------------------------------------|
| `concepts/lakehouse-concepts.md`         | OneLake, Delta, Medallion no Fabric — conceitos e decisões           |
| `concepts/direct-lake-cross-reference.md`| Direct Lake Fabric-specific — **canonical em** `kb/semantic-modeling/concepts/direct-lake-canonical.md` |
| `concepts/rti-concepts.md`               | RTI, Eventhouse, KQL Database, Eventstreams — conceitos              |
| `concepts/cross-platform-concepts.md`    | Shortcuts, Mirroring, integração Fabric ↔ Databricks — conceitos    |

### Padrões (`patterns/`)

| Arquivo                              | Conteúdo                                                              |
|--------------------------------------|-----------------------------------------------------------------------|
| `patterns/lakehouse-patterns.md`     | SQL de Lakehouse, V-Order, Medallion no Fabric, Delta config         |
| `patterns/rti-patterns.md`           | KQL queries, Activator rules, Eventstream setup                     |
| `patterns/data-factory-patterns.md`  | Data Factory JSON, Dataflows Gen2, orquestração Fabric              |
| `patterns/shortcut-patterns.md`      | REST API shortcuts, Mirroring setup, paths ABFSS                    |

---

## Regras de Negócio Críticas

### Lakehouse e OneLake
- Sempre use Delta Lake como formato de armazenamento padrão no Lakehouse.
- Organize os dados no padrão Medallion: `Bronze/`, `Silver/`, `Gold/` dentro do Lakehouse.
- Use `V-Order` nas tabelas Gold para otimização de leitura pelo Direct Lake.
- Prefira Shortcuts para acessar dados externos sem duplicação (zero-copy).

### Direct Lake (Power BI)
- Tabelas Gold devem ser otimizadas com `V-Order` para máxima performance no Direct Lake.
- Evite colunas com alta cardinalidade sem necessidade analítica.
- Colunas de data devem ser do tipo `DATE` (não `TIMESTAMP`) para integração com dim_data.
- Nunca use `PARTITION BY` em tabelas destinadas ao Direct Lake — use `CLUSTER BY`.

### Real-Time Intelligence (RTI)
- Use Eventhouse (KQL Database) para dados de streaming e análise em tempo real.
- Configure Activator para alertas automáticos baseados em thresholds de qualidade.
- Eventstreams são a fonte preferida para ingestão de dados em tempo real no Fabric.

### Governança no Fabric
- Use OneLake Data Catalog para documentar e classificar ativos de dados.
- Configure sensitivity labels para dados PII e confidenciais.
- Use Workspace Roles para controle de acesso granular.
- Monitore lineage via `mcp__fabric_community__get_lineage` antes de qualquer mudança estrutural.
