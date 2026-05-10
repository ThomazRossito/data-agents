---
domain: industry
updated_at: 2026-04-30
agents: [catalog-intelligence, business-analyst, governance-auditor, data-quality-steward]
---

# Industry Knowledge Base — Índice

Base de conhecimento de verticais de indústria. Contém casos de uso, schemas de referência,
KPIs e regras de conformidade por setor para guiar análise de catálogo, descoberta de valor
e alinhamento de dados ao negócio.

---

## Verticais Disponíveis

| Vertical | Arquivo | Casos de Uso Principais |
|----------|---------|------------------------|
| **Financial Services** | `kb/industry/financial-services.md` | Crédito, AML/KYC, IFRS 9, Churn, NBO, Open Finance |
| **Retail** | `kb/industry/retail.md` | Demand Forecasting, RFM, Dynamic Pricing, Omnichannel |
| **Manufacturing** | `kb/industry/manufacturing.md` | OEE, Manutenção Preditiva, SPC, S&OP, IoT |
| **Healthcare** | `kb/industry/healthcare.md` | Readmissão, Sepse, Leito Inteligente, Sinistralidade ANS |
| **Energy** | `kb/industry/energy.md` | Smart Meter Analytics, SAIDI/SAIFI, Oil & Gas Upstream, Geração Renovável |
| **Telecom** | `kb/industry/telecom.md` | CDR Analytics, Churn, Network KPIs, ARPU, Fraude SIM Swap |
| **Agribusiness** | `kb/industry/agribusiness.md` | Monitoramento de Safra, Mark-to-Market, EUDR/RTRS, Carbon Credits, Rastreabilidade |
| **Insurance** | `kb/industry/insurance.md` | Pricing GLM/ML, Detecção de Fraude, IBNR, Telemática UBI, SUSEP |
| **Logistics** | `kb/industry/logistics.md` | OTIF, Track & Trace, Gestão de Frota, Acuracidade de Inventário, Carbon Footprint |
| **Education** | `kb/industry/education.md` | Early Warning de Evasão, Funil de Captação, LMS Analytics, Inadimplência, NPS Acadêmico |

---

## Como Usar

### Identificar a indústria do cliente

Verificar pelas palavras-chave no contexto do usuário:

- **Financial Services**: banco, seguradora, corretora, crédito, inadimplência, BACEN, IFRS, DPD, ECL, sinistro (seguros), COAF
- **Retail**: loja, SKU, estoque, e-commerce, PDV, GMV, giro, campanha, atribuição, cesta
- **Manufacturing**: fábrica, linha de produção, OEE, sensor, PLM, manutenção, MTBF, turno, refugo, scrap
- **Healthcare**: hospital, clínica, paciente, CID, prontuário, operadora, sinistralidade, AIH, ANS, LGPD Art.11
- **Agribusiness**: fazenda, safra, talhão, soja, milho, commodity, CAR, NDVI, rastreabilidade, EUDR, RTRS, trading, hedge, cooperativa, agroindústria
- **Insurance**: seguradora, apólice, sinistro, SUSEP, IBNR, prêmio, segurado, subscrição, resseguro, fraude de sinistro, telemática
- **Logistics**: transportadora, frete, entrega, OTIF, rastreamento, armazém, WMS, frota, last-mile, CTe, ANTT, cross-dock, fulfillment
- **Education**: escola, universidade, IES, aluno, matrícula, evasão, LMS, EAD, ENADE, INEP, MEC, PROUNI, FIES, frequência, edtech

### Carregar a KB da vertical antes de análise

```python
# Para catalog-intelligence analisando tabelas financeiras:
Read("kb/industry/financial-services.md")

# Para business-analyst processando transcript de reunião de saúde:
Read("kb/industry/healthcare.md")
```

### Estrutura de cada KB de indústria

Cada arquivo segue o padrão:
1. **Casos de Uso por Objetivo** — tabela com caso, descrição e domínios de dados necessários
2. **Schemas de Referência** — DDL comentado com melhores práticas (PII, particionamento, tipos)
3. **KPIs de Referência** — fórmulas, benchmarks e thresholds regulatórios
4. **Conformidade e Privacidade** — LGPD, reguladores setoriais (BACEN, ANS, ANVISA), HIPAA
5. **Anti-Padrões Específicos** — erros comuns da vertical com severidade e risco

---

## Regras de Uso

1. **Consultar SEMPRE antes de inferir casos de uso** — nunca inventar casos de uso sem base na KB
2. **Indicar a fonte das inferências** — "baseado em kb/industry/retail.md §Casos de Uso"
3. **PII detectada** → alertar antes de documentar (ver regras em `kb/governance/`)
4. **Vertical não identificada** → perguntar ao usuário antes de assumir
5. **KB ausente para a vertical** → reportar lacuna e usar conhecimento geral com baixa confiança

---

## Expandindo as KBs

Para adicionar uma nova vertical, seguir o template em `kb/_templates/domain.md` e criar
o arquivo `kb/industry/<vertical>.md`. Adicionar a entrada na tabela acima.

Verticais prioritárias para expansão futura: Public Sector/GovTech, Media & Entertainment, Real Estate.
