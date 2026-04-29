# Padrão: Evaluation Framework

## Contexto

Escolher entre rubric determinística e LLM-as-judge para avaliar qualidade de outputs de agentes. Ambas têm casos de uso distintos e complementares.

## Solução

```python
# ── Rubric determinística (já implementada em evals/runner.py) ────────────
# Melhor para: routing check, must_include, anti-alucinação, CI/CD

rubric = {
    "must_include": ["bronze", "silver", "gold"],
    "must_not_include": ["não sei", "não tenho acesso"],
    "min_length": 250,
    "max_length": 3000,
}
# Score: 1.0 (tudo ok) | 0.5 (parcial ≥50%) | 0.0 (falha)


# ── LLM-as-judge (avaliação qualitativa periódica) ────────────────────────
# Melhor para: coerência técnica, completude semântica, tom

JUDGE_PROMPT = """\
Avalie a resposta abaixo com nota 0–10:
- Tecnicamente correto para Databricks/Fabric: peso 40%
- Completo para o que foi perguntado: peso 40%
- Sem alucinações ou informações inventadas: peso 20%

Pergunta: {query}
Resposta: {response}

Retorne apenas JSON: {{"score": <0-10>, "reason": "<1 frase>"}}
"""
```

## Decision Matrix

| Critério | Rubric Determinística | LLM-as-judge |
|----------|----------------------|-------------|
| Velocidade | Muito rápida (ms) | Lenta (1–5s por query) |
| Custo | Gratuita | Token cost adicional |
| Cobertura | must_include, formato, length | Semântica, coerência, completude |
| Reprodutibilidade | 100% determinística | Variação entre runs |
| Quando usar | CI/CD, smoke tests, anti-regressão | Avaliação qualitativa periódica |

## Tradeoffs

| Vantagem (rubric) | Desvantagem (rubric) |
|-------------------|--------------------|
| Zero custo, fast CI | Não detecta respostas erradas que incluem os termos |
| 100% reproduzível | Requer curadoria manual dos must_include |

## Related

- [agentic-workflow.md](agentic-workflow.md)
- [../specs/genai-patterns.yaml](../specs/genai-patterns.yaml)
