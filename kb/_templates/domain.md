# Template — Novo Domínio KB

> **Como usar este template:**
> 1. Copiar esta pasta para `kb/<nome-do-dominio>/`
> 2. Criar subpastas: `concepts/`, `patterns/`, `anti-patterns/` (opcionais, conforme necessidade)
> 3. Preencher o `index.md` — ele é o único arquivo injetado automaticamente pelo `loader.py`
> 4. Criar arquivos de conteúdo e referenciá-los no `index.md`
> 5. Adicionar o domínio ao `kb_domains` do frontmatter dos agentes que devem usá-lo

---

## Estrutura recomendada

```
kb/<dominio>/
├── index.md          ← OBRIGATÓRIO — injetado no system prompt dos agentes
├── concepts/         ← Conceitos fundamentais (o que é, como funciona)
│   ├── overview.md
│   └── <conceito>.md
├── patterns/         ← Padrões recomendados (como fazer certo)
│   └── <padrao>.md
├── anti-patterns/    ← O que evitar (referencia kb/shared/anti-patterns.md se já coberto)
│   └── <anti-padrao>.md
└── quick-reference.md  ← Cheat sheet de comandos / referência rápida (opcional)
```

---

## index.md — Template

```markdown
# <Nome do Domínio> — Knowledge Base Index

> Versão: 1.0 | Atualizado em: YYYY-MM-DD | Agentes: <lista de agentes que usam>

## Visão Geral

<2-3 parágrafos descrevendo o domínio: o que cobre, quando é relevante, qual o contexto de uso no data-agents>

## Regras Fundamentais

1. <Regra 1 — obrigatória para qualquer tarefa neste domínio>
2. <Regra 2>
3. <Regra 3>

## Arquivos de Referência

| Arquivo | Conteúdo | Quando consultar |
|---------|----------|-----------------|
| `concepts/overview.md` | Conceitos fundamentais | Antes de qualquer tarefa nova |
| `patterns/<padrao>.md` | Padrões recomendados | Ao implementar <X> |
| `quick-reference.md` | Comandos e sintaxe | Durante implementação |

## Anti-Padrões Críticos

> Ver `kb/shared/anti-patterns.md` para lista completa.
> Anti-padrões específicos deste domínio:

| ID | Anti-padrão | Severidade |
|----|-------------|-----------|
| D01 | <anti-padrão específico do domínio> | CRITICAL / HIGH / MEDIUM |

## Referências Externas

- [Documentação oficial](<url>)
- Skill relacionada: `skills/<dominio>/`
- KB relacionada: `kb/<outro-dominio>/`
```

---

## Convenções de Qualidade

### Arquivo de conteúdo (concepts/, patterns/)

```markdown
---
topic: <nome do tópico>
domain: <nome do domínio>
updated_at: YYYY-MM-DD
source: <databricks_docs | fabric_docs | web_search | internal>
---

# <Título>

## Contexto

<Por que este conceito/padrão existe? Qual problema resolve?>

## Definição / Implementação

<Conteúdo principal com exemplos de código onde aplicável>

## Quando Usar

<Critérios claros — quando este padrão é a escolha certa>

## Quando NÃO Usar

<Casos onde este padrão é a escolha errada>

## Referências

- <links, KBs relacionadas, skills>
```

---

## Checklist de Qualidade para PR/Review de nova KB

- [ ] `index.md` criado e autossuficiente (pode ser lido isoladamente)
- [ ] `updated_at` preenchido em todos os arquivos
- [ ] `source` documentado (de onde veio a informação)
- [ ] Exemplos de código testados ou referenciados de documentação oficial
- [ ] Anti-padrões específicos do domínio documentados ou referenciados
- [ ] Agentes relevantes atualizados com novo `kb_domains` no frontmatter
- [ ] Domínio listado no `CLAUDE.md` na seção de Knowledge Bases (se aplicável)

---

## Agentes e kb_domains

Para que um agente use o novo domínio, adicionar ao frontmatter em `agents/registry/<agente>.md`:

```yaml
kb_domains: [existente1, existente2, <novo-dominio>]
```

O `loader.py` injeta automaticamente o `index.md` do novo domínio no system prompt do agente.
