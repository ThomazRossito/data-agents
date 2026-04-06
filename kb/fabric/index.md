# KB: Microsoft Fabric — Índice

**Domínio:** Arquitetura, padrões e boas práticas do Microsoft Fabric.
**Agentes:** pipeline-architect, sql-expert, semantic-modeler

---

## Conteúdo Disponível

| Arquivo                        | Conteúdo                                                                  |
|--------------------------------|---------------------------------------------------------------------------|
| `lakehouse-patterns.md`        | Padrões de Lakehouse, OneLake, Delta e Medallion no Fabric                |
| `direct-lake-rules.md`         | Regras para tabelas otimizadas para Direct Lake e Power BI                |
| `rti-eventhouse-patterns.md`   | Padrões de Real-Time Intelligence, Eventhouse e KQL                       |
| `data-factory-patterns.md`     | Padrões de Data Factory, Dataflows Gen2 e orquestração                    |
| `cross-platform-shortcuts.md`  | Shortcuts, Mirroring e integração Fabric ↔ Databricks                     |

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
