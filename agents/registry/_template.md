---
name: agent-name
description: "Descrição do agente. Use para: [casos de uso]. Invoque quando: [condições de trigger]."
model: claude-sonnet-4-6
tools: [Read, Grep, Glob, Write]
mcp_servers: []
kb_domains: []
tier: T1
---
# Agent Name

## Identidade e Papel

Você é o **Agent Name**, especialista em [domínio].

---

## Protocolo KB-First — Obrigatório

Antes de qualquer ação, consulte as Knowledge Bases relevantes.

### Mapa KB + Skills por Tipo de Tarefa

| Tipo de Tarefa | KB a Ler Primeiro | Skill Operacional (se necessário) |
|----------------|-------------------|-----------------------------------|
| [tarefa]       | `kb/dominio/index.md` | `skills/skill.md`             |

---

## Capacidades Técnicas

[Descreva as capacidades técnicas do agente]

---

## Ferramentas MCP Disponíveis

[Liste as ferramentas MCP disponíveis]

---

## Protocolo de Trabalho

[Descreva o protocolo passo a passo]

---

## Formato de Resposta

```
[Defina o formato de resposta esperado]
```

---

## Restrições

1. [Restrição 1]
2. [Restrição 2]

---

## Campos do Frontmatter

| Campo         | Obrigatório | Descrição                                                                 |
|---------------|-------------|---------------------------------------------------------------------------|
| `name`        | Sim         | Identificador único do agente (kebab-case)                                |
| `description` | Sim         | Descrição para o Supervisor usar no roteamento                            |
| `model`       | Sim         | Modelo Claude: `claude-sonnet-4-6` ou `claude-opus-4-6`                   |
| `tools`       | Sim         | Lista de tools. Aliases: `databricks_all`, `databricks_readonly`, `fabric_all`, `fabric_readonly`, `fabric_rti_all`, `fabric_rti_readonly` |
| `mcp_servers` | Não         | Lista de MCP servers: `databricks`, `fabric`, `fabric_community`, `fabric_rti` |
| `kb_domains`  | Não         | Domínios de KB do agente. Quando `INJECT_KB_INDEX=true` (padrão), o loader injeta o `index.md` de cada domínio no prompt do agente automaticamente |
| `tier`        | Não         | Tier de complexidade: `T1` (core), `T2` (especializado), `T3` (avançado). Consumido pelo loader para model routing quando `TIER_MODEL_MAP` está configurado no `.env` |
