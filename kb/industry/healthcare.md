---
domain: industry
industry: healthcare
updated_at: 2026-04-30
agents: [catalog-intelligence, business-analyst, governance-auditor, data-quality-steward]
---

# Healthcare — Knowledge Base de Indústria

Referência de casos de uso, schemas típicos, KPIs e conformidade para times de dados
atuando em hospitais, clínicas, planos de saúde (operadoras), laboratórios e pharma.

---

## Casos de Uso de Dados por Objetivo

### Clínico e Assistencial

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Readmissão Hospitalar | Predição de pacientes com risco de retorno em 30 dias após alta | `encounters`, `diagnoses`, `procedures`, `medications`, `vitals` |
| Sepse Early Warning | Detecção precoce de sepse via critérios SIRS + qSOFA em tempo real | `vitals`, `lab_results`, `medications`, `nursing_notes` |
| Triagem de Pronto-Socorro | Score de prioridade automático baseado em sinais vitais e queixa | `triage_events`, `vitals`, `chief_complaint`, `historical_dx` |
| Leito Inteligente | Previsão de ocupação de leitos por unidade para planejamento de capacidade | `admissions`, `discharges`, `transfers`, `scheduled_procedures` |
| Custo por Episódio | Análise de custo total de tratamento por diagnóstico e prestador | `claims`, `procedures`, `medications`, `materials`, `drg_codes` |

### Operadoras de Plano de Saúde (ANS)

| Caso de Uso | Descrição | Regulação |
|-------------|-----------|-----------|
| Sinistralidade | Razão entre sinistros pagos e receita de mensalidades | ANS RN 195 |
| Fila de Autorização | Tempo de resposta a pedidos de autorização médica | ANS RN 259 (24h urgência) |
| Rede Credenciada | Análise de performance e cobertura da rede de prestadores | ANS |
| Fraude em Contas Médicas | Detecção de faturamento indevido (unbundling, upcoding) | ANS, CFM |

### Pharma e Lab

| Caso de Uso | Descrição |
|-------------|-----------|
| Clinical Trial Analytics | Análise de eficácia e segurança de estudos clínicos — CONSORT compliance |
| Drug Interaction Detection | Alerta de interações medicamentosas na prescrição |
| Lab Turnaround Time | Tempo desde coleta até resultado disponível no prontuário |
| Supply Chain de Medicamentos | Rastreamento de lotes, vencimento, temperatura (cold chain) |

---

## Schemas Típicos (Reference Architecture HL7 FHIR-inspired)

```sql
-- Pacientes (PHI — Dados de Saúde Protegidos)
-- ATENÇÃO: Todo acesso deve ser auditado e com consentimento LGPD
CREATE TABLE silver.dim_patients (
  patient_id        STRING NOT NULL,          -- identificador interno pseudonimizado
  mrn_hash          STRING,                   -- Medical Record Number — SHA-256
  cpf_hash          STRING,                   -- nunca CPF em claro
  birth_year        INT,                      -- apenas ano — sem data completa em Silver
  sex               STRING,                   -- M | F | O | U (unknown)
  ethnicity         STRING,
  zip_code_prefix   STRING,                   -- apenas 5 dígitos (não endereço completo)
  PRIMARY KEY (patient_id)
);

-- Encontros Clínicos (admissões, consultas, emergências)
CREATE TABLE gold.fct_encounters (
  encounter_id      STRING NOT NULL,
  patient_id        STRING NOT NULL,
  encounter_type    STRING,                   -- INPATIENT | OUTPATIENT | EMERGENCY | TELEHEALTH
  facility_id       STRING,
  department        STRING,
  admit_ts          TIMESTAMP,
  discharge_ts      TIMESTAMP,
  length_of_stay_days DECIMAL(6,2),
  drg_code          STRING,                   -- Diagnosis Related Group (AIH/SUS ou privado)
  primary_diagnosis STRING,                   -- CID-10 code
  discharge_disposition STRING,              -- HOME | TRANSFER | DECEASED | AMA
  total_cost        DECIMAL(12,2),
  PRIMARY KEY (encounter_id)
)
PARTITIONED BY (DATE(admit_ts));

-- Diagnósticos (ICD-10 / CID-10)
CREATE TABLE silver.fct_diagnoses (
  diagnosis_id      STRING NOT NULL,
  encounter_id      STRING NOT NULL,
  patient_id        STRING NOT NULL,
  icd10_code        STRING NOT NULL,
  icd10_description STRING,
  diagnosis_type    STRING,                   -- PRIMARY | SECONDARY | COMORBIDITY
  diagnosed_by      STRING,                   -- provider_id
  diagnosed_ts      TIMESTAMP,
  PRIMARY KEY (diagnosis_id)
);

-- Sinais Vitais (séries temporais)
CREATE TABLE silver.fct_vitals (
  vital_id          STRING NOT NULL,
  patient_id        STRING NOT NULL,
  encounter_id      STRING,
  recorded_ts       TIMESTAMP NOT NULL,
  vital_type        STRING,                   -- HEART_RATE | BLOOD_PRESSURE_SYS | BLOOD_PRESSURE_DIA | TEMPERATURE | O2_SAT | RESPIRATORY_RATE | WEIGHT | HEIGHT
  value             DECIMAL(8,2),
  unit              STRING,                   -- bpm | mmHg | Celsius | % | /min | kg | cm
  is_critical       BOOLEAN,                  -- fora do range de referência
  PRIMARY KEY (vital_id)
)
PARTITIONED BY (DATE(recorded_ts));

-- Resultados de Exames
CREATE TABLE silver.fct_lab_results (
  result_id         STRING NOT NULL,
  patient_id        STRING NOT NULL,
  encounter_id      STRING,
  order_ts          TIMESTAMP,
  collection_ts     TIMESTAMP,
  result_ts         TIMESTAMP,
  turnaround_minutes INT,                     -- result_ts - collection_ts
  loinc_code        STRING,                   -- LOINC padronizado
  test_name         STRING,
  value             STRING,                   -- string para aceitar numérico e texto
  numeric_value     DECIMAL(12,4),
  unit              STRING,
  reference_low     DECIMAL(12,4),
  reference_high    DECIMAL(12,4),
  is_abnormal       BOOLEAN,
  abnormal_flag     STRING,                   -- H | HH | L | LL | A (abnormal)
  PRIMARY KEY (result_id)
)
PARTITIONED BY (DATE(collection_ts));

-- Sinistros (Operadoras de Plano)
CREATE TABLE gold.fct_claims (
  claim_id          STRING NOT NULL,
  beneficiary_id    STRING NOT NULL,
  provider_id       STRING NOT NULL,
  service_date      DATE NOT NULL,
  submission_date   DATE,
  payment_date      DATE,
  procedure_codes   ARRAY<STRING>,            -- TUSS / CBHPM codes
  diagnosis_codes   ARRAY<STRING>,            -- CID-10
  claimed_amount    DECIMAL(12,2),
  paid_amount       DECIMAL(12,2),
  denial_reason     STRING,
  claim_status      STRING,                   -- SUBMITTED | APPROVED | DENIED | APPEALED | PAID
  PRIMARY KEY (claim_id)
)
PARTITIONED BY (service_date);
```

---

## KPIs de Referência

### Hospitalares

| KPI | Fórmula | Benchmark |
|-----|---------|-----------|
| **Taxa de Readmissão 30d** | Readmissões em 30d / Altas × 100 | Meta: < 15% (ACSA) |
| **ALOS** (Average Length of Stay) | Soma de `length_of_stay_days` / Nº de internações | Varia por DRG — comparar vs grupo |
| **Taxa de Ocupação** | Leitos ocupados / Leitos disponíveis × 100 | Eficiência: 75–85% |
| **Taxa de Mortalidade Hospitalar** | Óbitos / Total internações × 100 | Benchmark por DRG (risk-adjusted) |
| **Custo por Paciente-Dia** | Custo total / Paciente-dias | Benchmarking por especialidade |
| **Lab TAT** (Turnaround Time) | `result_ts - collection_ts` em minutos | Urgência: < 60 min; rotina: < 24h |

### Operadoras de Plano

| KPI | Fórmula | Threshold |
|-----|---------|-----------|
| **Sinistralidade** | Sinistros Pagos / Receita de Mensalidades | ANS alerta: > 75% |
| **Tempo de Autorização** | `auth_end_ts - auth_request_ts` | ANS: urgência < 2h; eletivo < 5 dias |
| **Taxa de Negativa** | Pedidos negados / Total de pedidos × 100 | Monitorado pela ANS |
| **NPS Beneficiários** | % Promotores − % Detratores | Excelente: > 40 |

---

## Conformidade e Privacidade

### LGPD em Saúde

```sql
-- Dados de saúde são DADOS SENSÍVEIS sob LGPD Art. 11
-- Requerem consentimento EXPLÍCITO e finalidade específica

-- Estrutura de consentimento
CREATE TABLE silver.fct_consents (
  consent_id        STRING NOT NULL,
  patient_id        STRING NOT NULL,
  consent_type      STRING,                   -- TREATMENT | RESEARCH | DATA_SHARING | MARKETING
  granted_ts        TIMESTAMP,
  revoked_ts        TIMESTAMP,
  is_active         BOOLEAN,
  legal_basis       STRING,                   -- LGPD_ART11_I (saúde) | LGPD_ART11_II_A (consentimento)
  consented_by      STRING,                   -- PATIENT | GUARDIAN | LEGAL_REPRESENTATIVE
  PRIMARY KEY (consent_id)
);

-- Verificação: todo acesso a PHI deve ter consentimento ativo
-- Esta query deve retornar 0 em produção
SELECT COUNT(*) as unauthorized_access
FROM silver.fct_encounters e
LEFT JOIN silver.fct_consents c
  ON e.patient_id = c.patient_id
  AND c.consent_type = 'TREATMENT'
  AND c.is_active = TRUE
WHERE c.consent_id IS NULL;
```

### HIPAA (para operações internacionais / dados de empresas US)

- PHI (Protected Health Information): 18 identificadores que devem ser removidos ou pseudonimizados
- Audit log obrigatório para todo acesso a dados de pacientes
- Criptografia em repouso e em trânsito para todos os dados PHI

### Regulação ANS

```sql
-- RN 195: Sinistralidade deve ser reportada mensalmente
-- RN 259: Prazos máximos de autorização por tipo de procedimento

-- Validação de prazo de autorização (RN 259)
SELECT
  authorization_id,
  procedure_type,
  urgency_level,
  TIMESTAMPDIFF(HOUR, request_ts, decision_ts) AS hours_to_decide,
  CASE
    WHEN urgency_level = 'URGENCIA' AND TIMESTAMPDIFF(HOUR, request_ts, decision_ts) > 2 THEN 'VIOLACAO_ANS'
    WHEN urgency_level = 'ELETIVO'  AND TIMESTAMPDIFF(DAY,  request_ts, decision_ts) > 5 THEN 'VIOLACAO_ANS'
    ELSE 'OK'
  END AS compliance_status
FROM silver.fct_authorizations
WHERE DATE(request_ts) >= current_date() - 30
ORDER BY compliance_status DESC;
```

---

## Anti-Padrões Específicos de Healthcare

| ID | Anti-padrão | Risco |
|----|-------------|-------|
| HC01 | Dados de pacientes sem pseudonimização em Silver/Gold | CRITICAL — violação LGPD Art. 11 + ANVISA |
| HC02 | Resultados de exames sem código LOINC/TUSS padronizado | HIGH — comparação entre sistemas impossível |
| HC03 | ALOS calculado incluindo transferências como alta | MEDIUM — ALOS subestimado |
| HC04 | Sinistralidade calculada sem ajuste de IBNR (Incurred But Not Reported) | HIGH — sinistralidade subestimada |
| HC05 | Dados de PHI em logs de aplicação ou mensagens de erro | CRITICAL — violação LGPD + HIPAA |
| HC06 | Análise de readmissão sem ajuste por risco (risk adjustment) | HIGH — hospitais com casos complexos penalizados injustamente |
| HC07 | Acesso a dados de paciente sem registro em audit log | HIGH — violação de conformidade LGPD Art. 37 |
