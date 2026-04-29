# Naming Convention

## Objetivo
Descreva o padrão oficial de nomenclatura para objetos no catálogo de dados.

## Escopo
- Catálogos
- Schemas
- Tabelas
- Colunas
- Volumes
- Funções

## Regras Globais
- Formato base: snake_case
- Charset permitido: a-z, 0-9, underscore (_)
- Início obrigatório: letra minúscula
- Tamanho máximo por objeto: 64
- Duplo underscore (__) permitido?: [sim/nao]
- Palavras reservadas proibidas: [lista]

## Prefixos por Camada
Defina o prefixo esperado para cada camada ou domínio.

| Contexto | Prefixo Obrigatório | Exemplo Válido |
|---|---|---|
| raw | raw_ | raw_pedidos |
| bronze | brz_ | brz_pedidos |
| silver | slv_ | slv_pedidos_limpos |
| gold | gld_ | gld_receita_diaria |
| mart | mrt_ | mrt_vendas_mensal |

## Regras para Schemas
- Padrão obrigatório:
- Prefixos permitidos:
- Sufixos permitidos:
- Exemplos válidos:
- Exemplos inválidos:

## Regras para Tabelas
- Padrão obrigatório:
- Prefixo por schema/camada:
- Sufixos técnicos permitidos (ex: _hist, _snap):
- Abreviações proibidas:
- Exemplos válidos:
- Exemplos inválidos:

## Regras para Colunas
- Identificador de chave primária: [ex: <entidade>_id]
- Identificador de chave estrangeira: [ex: <entidade>_id]
- Datas: [ex: _date ou _dt]
- Timestamps: [ex: _at, _timestamp, _ts]
- Booleanas: [ex: is_, has_, _flag]
- Métricas numéricas: [ex: *_amount, *_qty, *_pct]
- Exemplos válidos:
- Exemplos inválidos:

## Regras Semânticas
- Termos de negócio preferenciais:
- Sinônimos proibidos:
- Idioma padrão (pt/en):
- Singular ou plural:

## Exceções Permitidas
Liste exceções explícitas com justificativa e prazo de revisão.

| Objeto | Exceção | Justificativa | Expira em |
|---|---|---|---|

## Política de Renome
- Renome automático permitido?: [sim/nao]
- Renome exige aprovação humana?: [sim/nao]
- Janela de execução: [horário/janela]
- Estratégia de compatibilidade (views, aliases, depreciação):

## SQL de Referência
Inclua exemplos oficiais de CREATE TABLE seguindo o padrão.

## Checklist de Validação
- [ ] Objeto está em snake_case
- [ ] Prefixo de camada correto
- [ ] Sem palavra reservada
- [ ] Sem abreviação proibida
- [ ] Colunas de data/timestamp conforme padrão
- [ ] Nome semanticamente claro
- [ ] Tamanho máximo respeitado
