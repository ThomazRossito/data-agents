# KB: Data Mesh — Índice

Base de conhecimento para design e avaliação de arquitetura Data Mesh com Data Products.

Agente responsável: `data-mesh-architect`

---

## Domínios Cobertos

### 1. Princípios do Data Mesh
- **Domain Ownership**: cada domínio de negócio é dono dos seus dados de ponta a ponta
- **Data as a Product**: dados expostos como produtos com interface, SLA e discoverability
- **Self-Serve Data Platform**: infraestrutura que permite autonomia dos domínios
- **Federated Computational Governance**: políticas globais + autonomia local por domínio

### 2. Modelagem de Domínios
- Identificação de domínios alinhados ao negócio (Bounded Contexts de DDD)
- Tipos de domínio: Source-aligned, Aggregate, Consumer-aligned
- Mapeamento de entidades e eventos por domínio
- Estratégia de decomposição monolítico → malha

### 3. Data Products — Especificação
- Anatomia: `input ports`, `transformation logic`, `output ports`, `control plane`
- Contratos de saída: schema, SLA, versionamento, backwards compatibility
- Discovery: catálogo centralizado com metadata de cada Data Product
- Qualidade: SLA por produto (freshness, completeness, accuracy)
- Governança: ownership, stewardship, ciclo de vida do produto

### 4. Self-Serve Data Platform
- Camadas: Infrastructure (storage, compute), Control plane (catalog, lineage), Experience (self-serve tools)
- Implementação em Databricks: Unity Catalog como control plane, Lakehouse como storage
- Implementação em Fabric: OneLake como storage universal, Purview como catalog
- Requisitos para autonomia dos domínios: deploys independentes, monitoramento por domínio

### 5. Federated Governance
- Políticas globais obrigatórias: PII masking, retention, access control
- Autonomia local: schema design, naming conventions, SLA internos
- Interoperabilidade: protocolos de troca entre domínios (Event Hub, Delta Sharing)
- Comitê de Governança: composição, cadência de reuniões, processo de aprovação

### 6. Avaliação de Maturidade
- Níveis 0-3: Ad hoc → Silos → Plataforma centralizada → Data Mesh
- Dimensões: Ownership, Discoverability, Interoperability, Governance, Quality
- Score por dimensão (0-25 cada, total 100)
- Roadmap para evolução de maturidade

---

## Padrões Recomendados

### Organização
- Um time de produto por domínio (5-8 pessoas, inclui engenheiro de dados)
- Catálogo federado com registro obrigatório de cada Data Product
- Changelog e versionamento de cada produto (semver)

### Técnico
- Interfaces de saída padronizadas: Delta Sharing, REST APIs, Event Streams
- IaC por domínio: cada domínio gerencia sua própria infraestrutura via Databricks Asset Bundles ou Fabric Deployment Pipelines
- Observabilidade por produto: lineage, freshness, quality score visíveis no catálogo

### Anti-Padrões
- Central data team implementando tudo (não é Data Mesh, é plataforma centralizada com outro nome)
- Data Product sem SLA definido e monitorado
- Domínios que consomem dados de outros domínios via queries diretas no storage (bypassa contratos)
- Governança apenas em documentos sem enforcement técnico

---

## Recursos
- "Data Mesh" — Zhamak Dehghani (O'Reilly 2022)
- [datamesh-architecture.com](https://www.datamesh-architecture.com/)
- Databricks: Unity Catalog como control plane para Data Mesh
- Microsoft Fabric: OneLake + Purview como fundação de Data Mesh
