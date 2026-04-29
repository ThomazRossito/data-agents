# KB: lakehouse-ops

## Domínio
Operação, manutenção, observabilidade e otimização de Lakehouses em produção.

## Conteúdo
- `quick-reference.md` — comandos de manutenção, thresholds, runbook de incidente
- `patterns/maintenance-runbook.md` — VACUUM, OPTIMIZE, Z-ORDER, compaction schedule
- `patterns/incident-triage.md` — diagnóstico e resposta a falhas de pipeline/lakehouse
- `patterns/cost-optimization.md` — redução de CU/DBU, storage tiering, cluster right-sizing
- `patterns/migration-runbook.md` — checklist operacional para migração entre plataformas
- `specs/maintenance-schedule.yaml` — schedule padrão de manutenção por camada

## Quando usar
Qualquer tarefa envolvendo: sustentação, manutenção Delta, VACUUM, OPTIMIZE,
monitoramento de pipelines, incidentes de ingestão, otimização de custo,
migração de dados, observabilidade de Lakehouse.
