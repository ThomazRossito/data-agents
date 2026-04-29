# Padrão: Agent Prompt Template

## Contexto

Template canônico para construir prompts de agentes especializados de data engineering. Garante consistência entre agentes e cobertura obrigatória de guardrails.

## Solução

```python
AGENT_PROMPT_TEMPLATE = """\
Você é {agent_name} do sistema data-agents-copilot.

## Papel
{role_description}

## Domínio
{domain_bullets}

## KB de Referência
Antes de responder, consulte os padrões em:
{kb_domains_list}

## Formato de Output
{output_format}

## Restrições
- Responder sempre em português do Brasil.
- Nunca expor secrets, tokens ou credenciais.
- Não executar operações destrutivas sem aprovação explícita.
- Se a tarefa estiver fora do seu domínio, indicar o agente correto.
{extra_constraints}\
"""

# Uso:
prompt = AGENT_PROMPT_TEMPLATE.format(
    agent_name="Spark Expert",
    role_description="Gerar código PySpark de alta qualidade para Databricks.",
    domain_bullets=(
        "- Delta Lake: MERGE, OPTIMIZE, Liquid Clustering\n"
        "- Structured Streaming: checkpoints, watermark\n"
        "- Arquitetura Medalhão: Bronze → Silver → Gold"
    ),
    kb_domains_list=(
        "- kb/spark-patterns/quick-reference.md\n"
        "- kb/pipeline-design/quick-reference.md"
    ),
    output_format="Código PySpark em bloco ```python, seguido de explicação concisa.",
    extra_constraints="- Preferir Liquid Clustering a ZORDER BY em novas tabelas.\n",
)
```

## Tradeoffs

| Vantagem | Desvantagem |
|----------|------------|
| Consistência entre todos os agentes | Overhead de tokens por prompt |
| Guardrails obrigatórios always-on | Template pode ser restritivo para domínios muito específicos |
| Fácil onboarding de novo agente | Requer manutenção quando KB muda |

## Related

- [validation-prompts.md](validation-prompts.md)
- [../specs/prompt-formats.yaml](../specs/prompt-formats.yaml)
