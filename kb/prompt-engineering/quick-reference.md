# Prompt Engineering Quick Reference

> Tabelas de lookup rápido. Para exemplos completos ver arquivos linkados.

## Seleção de Técnica

| Técnica | Melhor para | Ganho de acurácia | Custo de tokens |
|---------|------------|-------------------|-----------------|
| Zero-shot | Classificação simples, roteamento | Baseline | Baixo |
| Few-shot | Formato sensível, tom específico | +15–25% | Médio |
| Chain-of-Thought | Raciocínio, lógica, diagnóstico | +20–40% | Médio |
| Self-consistency | Decisões de alto risco | +10–15% | Alto |
| Multi-pass extraction | Extração de documentos complexos | +25–35% | Alto |

## Temperature Guide

| Tipo de tarefa | Temperature | Razão |
|---------------|-------------|-------|
| Extração de dados / PII detection | 0.0 | Determinístico, factual |
| Classificação / roteamento de agente | 0.0–0.2 | Labels consistentes |
| Geração de código (SQL, PySpark) | 0.0–0.2 | Correção crítica |
| Sumarização técnica | 0.3–0.5 | Variação aceitável |
| Documentação / explicação | 0.5–0.7 | Diversidade de expressão |

## Estrutura Canônica de Prompt

| Seção | Obrigatório | Propósito |
|-------|------------|-----------|
| Role / System | Sim | Definir persona e restrições do agente |
| Task | Sim | O que o LLM deve fazer (verbo explícito) |
| Context / Input | Sim | Dados ou descrição do problema |
| Output Format | Sim | Estrutura esperada (JSON, Markdown, tabela) |
| Examples (few-shot) | Recomendado | Ensinar por demonstração |
| Constraints | Recomendado | Guardrails e casos extremos |
| KB Reference | Para agentes DE | "Consulte kb/spark-patterns antes de gerar código" |

## Decision Matrix

| Use Case | Solução |
|----------|---------|
| Extrair schema de SQL não estruturado | Multi-pass + Pydantic validation |
| Classificar query por tipo (DDL/DML/SELECT) | Zero-shot CoT + temperature 0.0 |
| Gerar código PySpark idiomático | Few-shot com exemplos do KB |
| Validar output antes de usar | `patterns/validation-prompts.md` |
| Prompt reutilizável entre agentes | `patterns/agent-prompt-template.md` |

## Common Pitfalls

| Evite | Prefira |
|-------|---------|
| Instruções vagas ("seja útil") | Instruções explícitas ("Gere DDL com schema completo") |
| Omitir formato de output | Sempre especificar estrutura (JSON schema ou Markdown) |
| Alta temperatura para extração | `temperature=0.0` para tarefas factuais |
| Prompt monolítico | Seções composáveis (role + task + format + constraints) |
| Trust cego no output do LLM | Validar com Pydantic antes de usar resultado |

## Related

| Tópico | Arquivo |
|--------|---------|
| Template canônico de agente | patterns/agent-prompt-template.md |
| Validação de output | patterns/validation-prompts.md |
| Formatos e campos obrigatórios | specs/prompt-formats.yaml |
