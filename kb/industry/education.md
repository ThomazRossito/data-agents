---
domain: industry
industry: education
updated_at: 2026-04-30
agents: [catalog-intelligence, business-analyst, governance-auditor, data-quality-steward]
---

# Education — Knowledge Base de Indústria

Referência de casos de uso, schemas típicos, KPIs e conformidade para times de dados
atuando em instituições de ensino superior (IES), redes de educação básica, edtechs,
plataformas EAD, sistemas de ensino e secretarias de educação.

---

## Casos de Uso de Dados por Objetivo

### Desempenho Acadêmico

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Early Warning de Risco de Evasão | Identificação de alunos com risco de abandono antes do fim do período | `enrollments`, `grades`, `attendance`, `financial_aid`, `lms_engagement` |
| Análise de Desempenho por Turma | Comparação de desempenho entre turmas, professores e currículos | `grades`, `dim_courses`, `dim_teachers`, `dim_students` |
| Predição de Aprovação/Reprovação | Forecast de aprovação por aluno e disciplina | `grades`, `attendance`, `activity_submissions`, `prior_performance` |
| Progressão de Aprendizado (LXP) | Acompanhamento do progresso em trilhas e microlearning | `lms_events`, `quiz_scores`, `content_completions`, `dim_learning_paths` |

### Captação e Retenção

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Funil de Captação | Taxa de conversão de leads em inscritos e matriculados por canal e curso | `leads`, `applications`, `enrollments`, `dim_courses`, `dim_channels` |
| Churn de Matrícula | Predição de cancelamento de matrícula por período | `enrollments`, `financial_history`, `academic_performance`, `interactions` |
| Fidelização de Ex-Alunos | Engajamento com alumni para extensão, pós-graduação e indicação | `alumni`, `completions`, `career_outcomes`, `engagement_history` |
| NPS Acadêmico | Análise de satisfação de alunos por curso, professor e serviço | `nps_surveys`, `dim_students`, `dim_courses`, `service_touchpoints` |

### Gestão Financeira e Inadimplência

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Inadimplência de Mensalidades | Monitoramento de alunos com parcelas em atraso e risco de evasão financeira | `financial_contracts`, `payments`, `dim_students`, `collection_events` |
| Previsão de Receita | Forecast de receita de mensalidades por período letivo | `enrollments`, `contracts`, `historical_payments`, `churn_probability` |
| Bolsas e Financiamentos | Gestão e impacto de bolsas PROUNI, FIES e institucionais | `scholarships`, `financial_aid`, `dim_students`, `enrollment_outcomes` |

---

## Schemas Típicos (Reference Architecture)

```sql
-- Alunos (ATENÇÃO: dados pessoais de menores e adultos — proteção especial)
-- LGPD + ECA (para menores de 18 anos)
CREATE TABLE silver.dim_students (
  student_id            STRING NOT NULL,        -- ID interno — nunca CPF/RA em claro
  cpf_hash              STRING,                 -- SHA-256 — nunca em claro
  ra_hash               STRING,                 -- RA pseudonimizado
  birth_year            INT,                    -- apenas ano (sem data completa)
  is_minor              BOOLEAN,                -- < 18 anos → proteção reforçada
  gender                STRING,                 -- M | F | NB | U
  state_code            STRING,
  entry_semester        STRING,                 -- "2023.1"
  entry_type            STRING,                 -- VESTIBULAR | ENEM | TRANSFERENCIA | PROUNI | FIES
  scholarship_type      STRING,                 -- PROUNI_INTEGRAL | PROUNI_PARCIAL | FIES | INSTITUCIONAL | NENHUMA
  PRIMARY KEY (student_id)
);

-- Matrículas por Período Letivo
CREATE TABLE silver.fct_enrollments (
  enrollment_id         STRING NOT NULL,
  student_id            STRING NOT NULL,
  course_id             STRING NOT NULL,
  academic_period       STRING NOT NULL,        -- "2024.1", "2024.2"
  enrollment_date       DATE,
  cancellation_date     DATE,
  enrollment_status     STRING,                 -- ACTIVE | CANCELLED | GRADUATED | TRANSFERRED | TRANCADO
  cancellation_reason   STRING,
  tuition_amount_brl    DECIMAL(12,4),          -- mensalidade bruta
  discount_pct          DECIMAL(5,2),           -- desconto concedido (%)
  net_tuition_brl       DECIMAL(12,4),          -- mensalidade líquida
  PRIMARY KEY (enrollment_id)
)
PARTITIONED BY (academic_period);

-- Notas e Avaliações
CREATE TABLE silver.fct_grades (
  grade_id              STRING NOT NULL,
  student_id            STRING NOT NULL,
  course_id             STRING NOT NULL,
  subject_id            STRING NOT NULL,
  teacher_id_hash       STRING,                 -- professor pseudonimizado
  academic_period       STRING NOT NULL,
  assessment_type       STRING,                 -- PROVA | TRABALHO | PROJETO | PARTICIPACAO | FINAL
  score                 DECIMAL(5,2),           -- nota (0-10 ou 0-100 dependendo da escala)
  max_score             DECIMAL(5,2),           -- nota máxima possível
  weight                DECIMAL(4,2),           -- peso na média (0-1)
  is_passing            BOOLEAN,
  PRIMARY KEY (grade_id)
)
PARTITIONED BY (academic_period);

-- Frequência / Presença
CREATE TABLE silver.fct_attendance (
  attendance_id         STRING NOT NULL,
  student_id            STRING NOT NULL,
  subject_id            STRING NOT NULL,
  class_date            DATE NOT NULL,
  attended              BOOLEAN,
  absence_type          STRING,                 -- JUSTIFIED | UNJUSTIFIED | null (se presente)
  cumulative_absence_pct DECIMAL(5,2),          -- % acumulada de faltas até esta aula
  PRIMARY KEY (attendance_id)
)
PARTITIONED BY (class_date);

-- Engajamento LMS (plataformas EAD e híbrido)
CREATE TABLE silver.fct_lms_events (
  event_id              STRING NOT NULL,
  student_id            STRING NOT NULL,
  course_id             STRING NOT NULL,
  content_id            STRING,
  event_ts              TIMESTAMP NOT NULL,
  event_type            STRING,                 -- LOGIN | VIDEO_PLAY | VIDEO_COMPLETE | QUIZ_START | QUIZ_SUBMIT | FORUM_POST | DOWNLOAD
  duration_seconds      INT,                    -- tempo em segundos no conteúdo
  completion_pct        DECIMAL(5,2),           -- % do conteúdo assistido/lido
  device_type           STRING,                 -- DESKTOP | MOBILE | TABLET
  PRIMARY KEY (event_id)
)
PARTITIONED BY (DATE(event_ts));

-- Score de Risco de Evasão (Gold — atualizado periodicamente)
CREATE TABLE gold.fct_dropout_risk (
  risk_id               STRING NOT NULL,
  student_id            STRING NOT NULL,
  enrollment_id         STRING NOT NULL,
  calculated_date       DATE NOT NULL,
  risk_score            DECIMAL(5,4),           -- 0.0-1.0 (1.0 = máximo risco)
  risk_tier             STRING,                 -- HIGH | MEDIUM | LOW
  main_risk_factors     ARRAY<STRING>,          -- ['financial_delay', 'low_attendance', 'poor_grades']
  recommended_action    STRING,                 -- IMMEDIATE_CONTACT | FINANCIAL_COUNSELING | ACADEMIC_SUPPORT
  PRIMARY KEY (risk_id)
)
PARTITIONED BY (calculated_date);
```

---

## KPIs de Referência

### Acadêmico

| KPI | Fórmula | Benchmark |
|-----|---------|-----------|
| **Taxa de Evasão** | Alunos que saíram sem concluir / Matriculados início do período × 100 | IES privada BR: 25-35%/ano (INEP) |
| **Taxa de Conclusão** | Formados / Ingressantes (mesmo período) × 100 | Meta regulatória: > 50% em 2× o prazo |
| **Taxa de Aprovação** | Aprovados / Total cursando × 100 | Meta por disciplina: > 70% |
| **Taxa de Frequência** | Aulas assistidas / Total de aulas × 100 | Mínimo legal: 75% (LDB) |
| **NPS Acadêmico** | % Promotores − % Detratores | Excelente: > 50 |

### Financeiro

| KPI | Fórmula | Benchmark |
|-----|---------|-----------|
| **Inadimplência** | Receita em atraso / Receita total esperada × 100 | IES privada: 15-25% |
| **Ticket Médio** | Receita líquida total / Nº de alunos ativos | Monitorar por curso e turno |
| **LTV do Aluno** | Ticket médio mensal × Duração esperada do curso | Projetar por taxa de churn |
| **CAC** (Captação) | Custo total de marketing + vendas / Novos matriculados | Monitorar por canal |

---

## Conformidade e Privacidade

### LGPD + ECA em Educação

```sql
-- Alunos menores de 18 anos têm proteção REFORÇADA (LGPD + ECA Art. 17)
-- Consentimento deve ser dos responsáveis legais, não do menor
-- Dados de desempenho de menores → finalidade pedagógica exclusiva

-- Verificação: identificar alunos menores com dados expostos sem proteção adicional
SELECT
  COUNT(*) AS minors_with_pii_risk
FROM silver.dim_students
WHERE is_minor = TRUE
  AND (cpf_hash IS NULL OR LENGTH(cpf_hash) != 64);

-- INEP: dados de matrículas reportados anualmente via Censo da Educação Superior
-- Obrigatório para IES — LGPD permite com base legal de obrigação legal (Art. 7, II)
```

### Regulação Setorial

- **LDB** (Lei 9.394/96) — frequência mínima 75%, carga horária mínima por curso
- **MEC/INEP** — Censo da Educação Superior (CES) obrigatório anualmente
- **ENADE** — avaliação trienal por curso (obrigatória para IES)
- **PROUNI/FIES** — prestação de contas ao MEC sobre bolsistas

---

## Anti-Padrões Específicos de Education

| ID | Anti-padrão | Risco |
|----|-------------|-------|
| ED01 | CPF ou RA de aluno em claro em qualquer tabela Silver/Gold | CRITICAL — violação LGPD; agravante se menor de 18 anos (ECA) |
| ED02 | Taxa de evasão calculada incluindo transferências como evasão | HIGH — superestima evasão; transferidos não são evadidos |
| ED03 | Frequência calculada por aluno sem separar EAD de presencial | HIGH — critérios distintos (presencial: 75% obrigatório; EAD: varia) |
| ED04 | Score de risco de evasão sem explicabilidade das features | MEDIUM — modelo opaco pode gerar discriminação; usar SHAP values |
| ED05 | NPS calculado incluindo respostas de alunos com menos de 30 dias matriculados | MEDIUM — alunos novos não têm experiência suficiente para avaliar |
| ED06 | LMS events sem separação por tipo de dispositivo | LOW — análise de engajamento mobile vs desktop ficam mescladas |
