# Formato das runs do Snake (snake-v0.2)

Cada sessão tem `sessao.json`, `comidas.json`, placar e, por partida,
`run_NNNN_laya.json`, `run_NNNN_algoritmo.json`, seus respectivos
`.jsonl.gz` e `run_NNNN_comparacao.json`. Os JSON são gravados por substituição
atômica; as linhas são escritas durante a partida, com gzip e UTF-8.

Os metadados da sessão e das duas runs incluem `commit_codigo` (git rev-parse
HEAD, ou null se indisponível), `nivel`, `versao_laya` (checkpoint escolhido),
`versao_pacote_laya` (ou null) e `arquivo_comidas` (relativo à pasta da sessão).
O hash identifica o HEAD; alterações locais sem commit não mudam esse hash.
O campo `passos` de cada JSON aponta para seu arquivo `.jsonl.gz`.
`inicio_lista` indica o deslocamento inicial da run em `comidas.json`; todos os
índices persistidos (movimentos, snapshot, pulos e comidas efetivas) já incluem
esse deslocamento. Uma run terminada na abertura tem gzip válido sem linhas,
snapshot com `passo=0` e a auditoria das candidatas consultadas.

## Cada linha de movimento

| Campo | Significado |
|---|---|
| `passo` | Número do movimento, começando em 1 |
| `cabeca`, `corpo` | Coordenadas [x,y]; corpo completo em ordem da cabeça ao rabo |
| `direcao` | 0=norte, 1=leste, 2=sul, 3=oeste |
| `comida`, `indice_comida` | Posição e índice absoluto, base zero, em comidas.json; null se ausente |
| `passos_sem_comer`, `restante_limite` | Fome atual e passos restantes do limite original do nível |
| `area_alcancavel` | Número de casas livres alcançáveis por flood fill estático da cabeça; exclui cabeça e corpo |
| `distancia_bfs_comida` | Distância estática atual, ou null se não houver caminho/comida |
| `rabo_alcancavel` | Há caminho estático até o rabo, permitindo apenas ele como destino ocupado |
| `escolha` | Ação relativa: straight, left ou right |
| `modo` | `bfs` ou `seguranca`, decisão do algoritmo antes do movimento |
| `motivo_seguranca` | `bfs_sem_caminho_seguro`, `area_pequena`, `rabo_inalcancavel`; null em modo bfs |
| `estrategia`, `motivo` | Estratégia/motivo registrado pelo decisor |
| `ideal_bfs_ao_aparecer` | BFS original usado para pontuação, ou null |
| `latencia_ms` | Tempo de decisão |
| `pontos_ganhos`, `pontos` | Ganho no movimento e total depois dele |

Estado e métricas descrevem **antes** do movimento; pontos descrevem **depois**.
Assim, a primeira linha tem `passo=1` e corpo inicial. O corpo completo, nível,
direção e comida permitem reconstruir o tabuleiro sem texto duplicado por linha.
O estado em texto ainda é entregue à GUI/modelo durante o jogo.

Somente o Laya registra `probabilidades` por direção relativa (`straight`,
`left`, `right`, em relação à `direcao` anterior ao movimento), `confianca`,
`jogada_ideal` do algoritmo no mesmo estado, `concorda` e `estrategia_ideal`.
A partida independente do algoritmo pode ter corpo, comidas efetivas e duração
diferentes, apesar de começar com a mesma lista. `estrategia`/`motivo` do Laya
identificam a decisão do modelo, sem atribuir a ele uma explicação que não
forneceu; `estrategia_ideal` descreve a estratégia do oráculo naquele estado.
`modo` e `motivo_seguranca` na run do Laya descrevem o oráculo que sugeriu
`jogada_ideal`; não indicam que o modelo seguiu essa ação. Na run independente
eles descrevem a decisão executada pelo algoritmo. O motivo segue a prioridade
rabo inalcançável, área pequena e BFS sem caminho seguro; o motivo da transição
pode persistir até o alinhamento do corpo, conforme `ALGORITMO.md`.
Na run independente, `estrategia` e `motivo` recebem a estratégia informada pelo
algoritmo, sem alterar suas decisões. Colisões também contam como movimento e
possuem uma linha; a cabeça no registro é a posição anterior à tentativa.

## Auditoria e término

Os JSON de ambas as runs guardam `pulos`: índice absoluto na lista, `posicao`,
`motivo` (`ocupada` ou `inalcancavel`), `passo` já executado (0 na abertura) e
`area_alcancavel` estática naquele instante. `comidas_efetivas` guarda índice,
posição e passo de nascimento. A alcançabilidade que decide o nascimento é
**temporal**, com liberação do corpo e limite original; difere da área estática.
Se nenhuma casa atualmente livre é alcançável no prazo, a partida termina com
`sem_comida_valida` antes de consultar candidatas, sem fabricar milhares de pulos.
Isso também vale ao posicionar a próxima comida após um movimento que comeu:
o índice da lista e a auditoria anterior são preservados, sem novos `pulos` ou
`comidas_efetivas`. Ambas as runs registram `motivo_termino="sem_comida_valida"`
e `resumo.morte="sem_comida_valida"`; no snapshot final, `comida` e
`indice_comida` são `null`, e o passo inclui o movimento que acabou de comer.
Se existem casas válidas, mas acabam as candidatas, termina com `lista_esgotada`.

`motivo_termino` é `vitoria`, `corpo`, `parede`, `fome`, `lista_esgotada`,
`sem_comida_valida` ou `erro`. `snapshot_final` guarda corpo, cabeça, direção,
comida/índice, fome, prazo, total de passos e tabuleiro em texto. `resumo` inclui
pontos, passos, gomos, vitória, morte e comidas consumidas. Inclui ainda
`passos_seguranca_por_motivo`, com as três chaves sempre presentes (zero
quando não houver ocorrências), por exemplo:

```json
{"bfs_sem_caminho_seguro": 4, "area_pequena": 2, "rabo_inalcancavel": 0}
```

Cada linha em segurança incrementa só o seu motivo; a soma é o total de passos
em segurança. Na run do Laya essa contagem se refere ao oráculo. Os contadores
também são persistidos em runs parciais/com erro e nos resumos da comparação.
O identificador `snake-v0.2` é a versão do formato de arquivo, independente da
versão do jogo: o algoritmo híbrido integra a v0.1. O campo legado
`resumo.morte` conserva `limite_sem_comer`, normalizado para `fome` no término.
Interrupções produzem `laya_parcial.json` e fecham o gzip, inclusive sem movimentos;
exceções de decisão (Laya ou oráculo local) fecham e salvam a run parcial na
própria sessão, mesmo sem GUI. O campo `erro` da run parcial contém tipo e
mensagem da exceção, ou `null` para interrupção voluntária; o término desta
última também é `erro`, pois não foi um fim natural da partida.
Exceções da partida independente fecham o gzip e produzem JSON do algoritmo
com término/status `erro`, detalhes em `erro`, snapshot e resumo do último estado.
As linhas já concluídas continuam legíveis; uma decisão que falhou antes do
movimento não gera linha. A run concluída do Laya é preservada e não recebe
uma cópia parcial por falha posterior do algoritmo. Em colisões, o snapshot
mantém a última posição válida do corpo e a direção da tentativa fatal.

A comparação aponta os dois gzip em `passo_a_passo`; alinhe pelo campo `passo`,
permitindo linhas ausentes quando uma run termina antes. Guarda concordância,
resumos, pulos, comidas efetivas e primeiro índice de divergência das sequências.

`valida_para_treino` e `motivo` continuam na sessão e comparação. Perder ou falhar
na run independente do algoritmo invalida toda a sessão com `algoritmo_perdeu`;
uma vitória posterior não reabilita os dados. Falhas de lista do Laya também
invalidam a sessão. A sessão é a autoridade para runs anteriores.
`treino/selecao.py` só aceita sessão concluída, explicitamente válida, sem motivo;
formatos antigos sem marcação e sessões interrompidas/com erro ficam de fora.

Leitura de exemplo:

```python
import gzip
import json

with gzip.open(pasta / run['passos'], 'rt', encoding='utf-8') as arquivo:
    for linha in arquivo:
        movimento = json.loads(linha)
```
