# Direct Lake

## O que é Direct Lake
Direct Lake é um modo de conexão para Semantic Models que lê Delta Parquet diretamente do OneLake — sem copiar dados (Import) e sem query em tempo real contra DB (DirectQuery).

## Comparativo de Modos
| Modo | Performance | Custo CU | Atualização | Limites |
|------|------------|----------|-------------|---------|
| **Import** | Mais rápido (in-memory) | Baixo (refresh) | Agendado | Tamanho RAM |
| **DirectQuery** | Médio | Alto (toda query) | Sempre atual | Latência DB |
| **Direct Lake** | Quase igual ao Import | Baixo | Ao abrir | Requer Delta |

## Regras de Fallback
Direct Lake cai automaticamente para DirectQuery quando:
1. Tabela excede limite de linhas do SKU (F2: ~150M, F64: ilimitado)
2. Tabela não é Delta gerenciada (shortcut read-only pode falhar)
3. Schema mismatch entre modelo e tabela

```
Monitorar: Fabric Portal → Semantic Model → Refresh History → "Fallback count"
```

## Requisitos de Tabela para Direct Lake
- Formato: Delta Parquet no OneLake (não Parquet puro)
- Localização: `Tables/` do Lakehouse (managed)
- Particionamento: por data recomendado para > 10M linhas
- OPTIMIZE + VACUUM aplicados (reduz V-Order latency)

## V-Order (Fabric)
Fabric aplica V-Order ao escrever Delta — otimização de leitura da Microsoft que melhora Direct Lake. Já habilitado por padrão em Lakehouses.

```python
# Via Spark no Fabric — confirmar V-Order ativo
spark.conf.set("spark.microsoft.delta.optimizeWrite.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.binSize", "1073741824")
```

## Como Criar Semantic Model com Direct Lake
1. Criar Lakehouse com tabelas Delta
2. Fabric Portal → New item → Semantic Model
3. Selecionar Lakehouse → tabelas Delta
4. Modo detectado automaticamente como Direct Lake
5. Publicar → conectar Power BI

## Limites por SKU
| SKU | Max linhas/tabela | Max tabelas |
|-----|-------------------|-------------|
| F2 | ~150M | 10 |
| F8 | ~300M | 50 |
| F32 | ~1B | 200 |
| F64 | Sem limite prático | Sem limite |
