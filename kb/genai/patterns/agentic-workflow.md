# Padrão: Supervisor + Specialist Workflow

## Contexto

Arquitetura Hub-and-Spoke com um Supervisor central que roteia para agentes especialistas por domínio. É a topologia implementada neste projeto.

## Solução

```
User Input
    ↓
Supervisor.route()
    ├── security_hook.check()       ← bloqueia inputs destrutivos
    ├── Regex/keyword detection     ← TABLE_CREATION, GOVERNANCE patterns
    ├── KB context loading          ← constitution + domain quick-reference
    ├── Confidence assessment       ← Agreement Matrix sem MCP externo
    │       ├── CRITICAL < 0.98   → REFUSE imediato
    │       ├── IMPORTANT < 0.95  → ASK usuário
    │       └── STANDARD ≥ 0.90   → PROCEED
    ├── Workflow detection          ← WF-01…WF-04 (colaboração multi-agente)
    └── Agent delegation
            ├── spark_expert       (T1 — PySpark, Delta Lake)
            ├── sql_expert         (T1 — SQL, read-only via MCP)
            ├── pipeline_architect (T1 — ÚNICO com permissão de escrita)
            ├── data_quality       (T2 — DQX, Great Expectations)
            ├── dbt_expert         (T2 — dbt Core)
            ├── naming_guard       (T2 — nomenclatura Unity Catalog)
            ├── governance_auditor (T2 — PII, LGPD, auditoria)
            ├── python_expert      (T1 — Python puro)
            └── geral              (T3 — conceitual, barato)
```

## Princípios do Design

1. **KB-First**: Supervisor carrega KB antes de qualquer chamada ao LLM
2. **Tier separation**: T1 para complexidade, T3 para custo
3. **Single write agent**: `pipeline_architect` é o único com permissão de escrita
4. **Hooks transversais**: security, audit, cost_guard sem acoplamento com agentes
5. **Confidence gate**: recusa operações CRITICAL com score abaixo do threshold

## Tradeoffs

| Vantagem | Desvantagem |
|----------|------------|
| Specialists otimizados por domínio | Latência adicional de roteamento |
| Controle granular de custos (tiers) | Mais arquivos para manter |
| Auditabilidade por agente | Coordenação pode falhar em edge cases |

## Related

- [evaluation-framework.md](evaluation-framework.md)
- [../specs/genai-patterns.yaml](../specs/genai-patterns.yaml)
