# License

## data-agents-copilot

Este projeto é distribuído sob a **MIT License**.

```
MIT License

Copyright (c) 2024-2025 Data Agents Copilot Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Referência ao Projeto Original

Este projeto é uma adaptação e extensão do trabalho original:

**[data-agents](https://github.com/ThomazRossito/data-agents)** por Thomaz Rossito

### Modificações Principais

Este fork adiciona:

- ✅ Integração nativa com **GitHub Copilot Chat** (`/naming`, `/spark`, `/sql`, etc.)
- ✅ **Naming Convention Governance** com auto-trigger em CREATE TABLE
- ✅ **Cost-Aware Agent Selection** (Tier 3 para queries simples)
- ✅ Documentação e infraestrutura Git completa

### Obrigações de Atribuição

Se você usar este projeto ou o repositório original, seja em forma modificada ou não:

1. **Mantenha este arquivo** com referência ao original
- **Credite Thomaz Rossito** no README ou documentação
3. **Inclua a MIT License** integralmente em distribuições
4. **Mencione modificações** — changelog clara

Exemplo de atribuição:

```markdown
## Créditos

Baseado em [data-agents](https://github.com/ThomazRossito/data-agents) de Thomaz Rossito.

Modificações: Integração com GitHub Copilot Chat, Naming Governance, Cost Optimization.
```

---

## Dependências de Terceiros

Este projeto depende de várias bibliotecas open-source sob suas respectivas licenças:

- **OpenAI Python SDK** — MIT License
- **Pydantic** — MIT License
- **Databricks SDK** — Apache 2.0
- **Typer** — MIT License
- **Rich** — MIT License
- **Python-dotenv** — BSD 3-Clause

Para lista completa, consulte `pyproject.toml` e `pip freeze`.

---

## Contribuições

Ao contribuir para este projeto, você concorda que suas contribuições serão licenciadas sob a mesma MIT License.

Veja [CONTRIBUTING.md](./CONTRIBUTING.md) para detalhes.

---

Dúvidas sobre licença? Abra uma [Discussion](https://github.com/arthurfr23/data-agents-copilot/discussions) no GitHub.
