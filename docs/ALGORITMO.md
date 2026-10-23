# Algoritmo de referência e regra da comida

O QA exige 100% de vitórias em todos os níveis e preserva qualquer derrota
para reprodução. O script usa 200 partidas por nível por padrão, exigindo 100%.
O teste slow ampliado mantém 1.000 partidas por nível quando solicitado.
Os níveis jogáveis da v0.1 são 15x15, 20x20 e 25x25. O 30x30 está adiado,
com sua configuração (200 gomos, 120 passos) em `NIVEIS_ADIADOS`.

## Híbrido na v0.1 (etapa 3)

O BFS continua sendo o principal, sem consultar comidas futuras. Calcula uma
rota temporal até a comida, simula o crescimento e testa o escape até o rabo.
Compara seis aproximações ponderadas, preferindo manter o espaço livre
conectado, sem becos ou articulações. Pode reparar a rota com pequenos desvios;
a reparação tem orçamento de cerca de 15 ms e retorna ao encontrar uma solução
sem esses defeitos. As buscas extensas sobre configurações do corpo continuam
disponíveis para diagnóstico, mas não são executadas em cada decisão do jogo.
O caminho rápido evita essas buscas para visar decisões abaixo de ~50 ms no
25x25; isso é uma meta de latência, não um prazo rígido em qualquer máquina.

Cada nível mantém um ciclo imutável pré-calculado e seu índice por casa,
mesmo enquanto o BFS joga. O modo `seguranca` é acionado quando:

- o rabo é inalcançável no flood fill estático: `rabo_inalcancavel`;
- a área livre alcançável é menor que o número de gomos: `area_pequena`;
- não há rota validada pelo planejador, ou ela é incompatível com a ordem
  exigida para a transição: `bfs_sem_caminho_seguro`.

Essa é também a prioridade dos motivos quando vários gatilhos coincidem.
A área exclui cabeça e corpo; o teste do rabo permite o próprio rabo como
único destino ocupado. O motivo é reavaliado antes de cada movimento.

A partir de metade da meta de gomos do nível, o BFS deve respeitar a ordem
circular do ciclo. Atalhos no estilo Tapsell avançam a cabeça sem ultrapassar
o rabo nem saltar a comida. Reservam uma casa de folga, uma adicional ao
crescer e outra para atalhos maiores que uma aresta. Toda a rota é simulada,
inclusive seu crescimento, para verificar a ordem em cada passo. Corpo
alinhado significa ordem circular do rabo até a cabeça, admitindo lacunas;
não exige segmentos consecutivos no ciclo.

Na segurança, um corpo alinhado tenta atalhos ordenados e depois o sucessor
do ciclo. Se estiver desalinhado, segue um caminho livre até o rabo, preferindo
avançar na ordem do ciclo para desfazer o desalinho, sem comer durante
essa aproximação. Mantém a transição enquanto estiver
desalinhado, mesmo que a área volte a crescer; só retoma o BFS ao alinhar e
cessarem os gatilhos. Seguir o rabo não prova convergência para todo corpo
arbitrário, e o limite sem comer continua valendo durante a transição.
Se o rabo não puder ser seguido, a emergência prioriza escape, área e prazo;
atalhos de emergência também verificam a ordem quando aplicável. Sem saída
validada, resta uma ação sem colisão imediata, se existir.

No 20x20 o ciclo cobre as 400 casas. No 15x15 e no 25x25, a paridade impede
um ciclo hamiltoniano completo: o ciclo cobre respectivamente 224 e 624
casas e deixa `(n-1, 0)` de fora. Essa casa continua pertencendo ao jogo e
pode receber comida. Para uma cobra grande, a exceção só permite sair da
ordem no último movimento até essa comida, com crescimento e escape
validados; depois segue o rabo para reentrar e alinhar. **Não há garantia
total de vitória nos mapas ímpares**, nem de comer dentro do prazo seguindo
apenas o ciclo, mesmo no mapa par. Níveis, metas, pontuação e limites
permanecem 15/50/60, 20/90/80 e 25/140/100.

O cache de trajetória é invalidado se o estado divergir do previsto, inclusive
quando usado para sugerir jogadas nos estados produzidos pelo Laya. Rotas
reparadas e alternativas são comparadas pela mesma avaliação. Cada passo
registra `modo` e `motivo_seguranca`, e os resumos contam os passos por motivo
conforme [FORMATO_RUN.md](FORMATO_RUN.md). O híbrido faz parte da v0.1.

## Regra da comida e auditoria

A decisão do Lucas (opção a) filtra a lista salva antes de aparecer cada comida.
A casa deve estar vazia e existir alcance da cabeça em até o limite sem comer
do nível. A busca usa estados (casa, tempo) e a liberação do corpo atual:
segmento `i`, com cabeça de índice 0, libera após `len(corpo) - i` passos.
Não existe espera parada. Casas podem ser revisitadas em instantes distintos,
pois uma passagem posterior pode encontrar um segmento já liberado.

Uma candidata ocupada é pulada com motivo `ocupada`; uma candidata vazia sem
alcance dentro do prazo é pulada com `inalcancavel`. Não há aleatoriedade nessa
seleção: estado e lista iguais produzem comida e pulos iguais.

Antes de consultar a lista a cada nova comida, verifica-se uma vez se alguma
casa atualmente livre é alcançável no prazo. Se nenhuma for, a partida encerra
imediatamente com `sem_comida_valida`, inclusive logo após comer. Não avança o
índice nem acrescenta pulos ou comidas efetivas; a auditoria anterior permanece.
Essa verificação usa o mesmo alcance temporal do filtro, não o BFS estático.
Se houver casa válida, mas a lista acabar sem fornecê-la, o término continua
sendo `lista_esgotada`, sem sortear outra comida.

`Jogo.pulos` guarda `{indice, posicao, motivo, passo}`; `passo` conta movimentos
já executados, incluindo 0 na abertura. `comidas_efetivas` guarda índice, posição
e passo das comidas que apareceram, inclusive a última ainda não consumida.
Os arquivos de Laya (também parciais) e algoritmo persistem essas listas com
índices absolutos na lista da sessão, a partir de zero. No Jogo são locais.
A comparação inclui ambas as listas e `divergencia_comidas`, primeiro índice
base zero na sequência efetiva em que diferem (ou `null`), e um `aviso` textual.
Uma sequência mais curta diverge no primeiro elemento ausente; índice ou posição
diferentes também contam. **Os pulos podem diferir entre Laya e algoritmo pois
os corpos diferem**, mesmo partindo da mesma lista salva.

O `ideal_comida` e os pontos continuam usando o BFS estático ao aparecer, sem
liberação temporal. Um ideal inexistente continua registrado como `None`, sem
excesso mensurável na pontuação. A busca temporal apenas decide o nascimento.

O planejador simula o corpo para validar rotas e prefere manter o espaço livre
conectado, sem becos ou passagens que separem regiões ao serem ocupadas.
O raio do espaço livre deixou de ser requisito para uma
rota: cada nova comida já passa pelo filtro de prazo. Quando as rotas habituais
falham, o híbrido entra em segurança. As heurísticas não constituem uma prova
matemática de vitória.

## Reprodução

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -m pytest -m 'not slow'
.venv/bin/python -m pytest -m slow --qa-partidas 10
.venv/bin/python -m pytest -m slow  # padrão: 1000 por nível
.venv/bin/python scripts/qa_algoritmo.py  # padrão: 200, exige 100%
.venv/bin/python scripts/qa_algoritmo.py --repetir-falhas tests/fixtures/derrotas_25x25.json --saida /tmp/qa_repeticao_25x25.json
```

O script usa listas de 20.000 candidatas por partida, retorna 1 se houver qualquer
derrota ou erro de sessão (inclusive lista esgotada) e salva os resumos, pulos e
listas completas das falhas em `/tmp/qa_algoritmo.json`. O progresso é registrado
conforme cada partida termina, sem aguardar partidas anteriores. O pytest salva as falhas em seu
diretório temporário e informa o caminho na asserção. Todas essas listas usam
`secrets.randbelow`; o padrão do script é 200 por nível e nenhuma falha é aceita.
A repetição usa exclusivamente as listas salvas, sem sorteios novos, informa
cada partida e imprime o resultado final; aceita fixtures ou o relatório de QA.

## Resultados históricos (anteriores ao híbrido)

Antes da correção única: **15x15 200/200**, **20x20 200/200**,
**25x25 198/200**; portanto o 25x25 foi reprovado. Listas completas preservadas
em `tests/fixtures/derrotas_25x25.json` (partidas 62 e 128). No relatório
original `/tmp/qa_algoritmo_otimizado.json`, a 62 morreu no corpo; a 128
registrou lista esgotada (não fome/limite). Não se substituem nem estendem
as listas para a repetição. A reprodução dessas duas falhas não certifica
o nível inteiro.

### Derrotas 25x25: causa raiz

A busca perdia diversidade de futuros do corpo; preservar sua ordem na deduplicação mantém os tempos distintos de liberação do rabo.
Na 62, o planejamento levou à armadilha e à colisão com 123 gomos; na 128, comer deixou a cabeça sem saída com 134 gomos.
Na 128, os quatro vizinhos só liberariam nos passos 101, 103, 131 e 133: nenhum antes do limite de 100, portanto os pulos eram legítimos, sem fome nem loop.
A correção atua no planejamento antes da armadilha, sem aumentar listas; as regressões repetem as duas listas originais e verificam que uma candidata alcançável encerra os pulos.

Após a correção única (deduplicação pelo corpo ordenado), foram repetidas
somente as partidas **62: vitória** e **128: vitória**, com as mesmas listas
completas: **2/2 (100%)**. Relatório: `/tmp/qa_repeticao_25x25.json`.
O QA completo não foi executado nesta rodada.
