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
conectado, sem becos ou articulações. Pode reparar a rota com pequenos desvios
ou recorrer às buscas sobre configurações do corpo e a desvios pelo rabo.
O planejador completo é executado quando não há uma rota em cache; o caminho
rápido fica disponível para os atalhos do modo segurança. As buscas completas
podem aumentar a latência em estados difíceis.

Cada nível mantém um ciclo imutável pré-calculado e seu índice por casa,
mesmo enquanto o BFS joga. O modo `seguranca` é acionado quando:

- o rabo é inalcançável no flood fill estático: `rabo_inalcancavel`;
- a área livre alcançável é menor que o número de gomos: `area_pequena`;
- não há rota validada pelo planejador: `bfs_sem_caminho_seguro`.

Essa é também a prioridade dos motivos quando vários gatilhos coincidem.
A área exclui cabeça e corpo; o teste do rabo permite o próprio rabo como
único destino ocupado. O motivo é reavaliado antes de cada movimento.

O tamanho e o desalinhamento do corpo não acionam segurança. A ordem circular
não restringe as rotas BFS nem a emergência: impor essa ordem a partir de
metade da meta (apenas cerca de 11% do tabuleiro) causava fome. Os atalhos
ordenados ficam restritos ao recurso de segurança: avançam sem ultrapassar
o rabo nem saltar a comida, reservando folga para crescimento.

Na segurança, um corpo alinhado tenta atalhos ordenados e depois o sucessor
do ciclo. Se estiver desalinhado, segue um caminho livre até o rabo, preferindo
avançar na ordem do ciclo. Não mantém uma transição obrigatória até alinhar:
o planejador principal é tentado novamente no próximo passo e, cessados os
gatilhos reais, o BFS retoma imediatamente. Uma rota temporal com crescimento
e escape validados tem prioridade sobre seguir o ciclo ou alinhar, mesmo com
gatilho estático de área/rabo ainda ativo: o rabo pode ser liberado durante a
rota. Essa decisão mantém `modo=seguranca` e o motivo real. A partir de 75%
do limite sem comer, identifica a estratégia como `seguranca_bfs_comida_no_prazo`. Se o rabo não puder
ser seguido, a emergência prioriza escape, área e prazo. Sem saída validada,
resta uma ação sem colisão imediata, se existir.

No 20x20 o ciclo cobre as 400 casas. No 15x15 e no 25x25, a paridade impede
um ciclo hamiltoniano completo: o ciclo cobre respectivamente 224 e 624
casas e deixa `(n-1, 0)` de fora. Essa casa continua pertencendo ao jogo e
pode receber comida. O BFS pode chegar a essa casa por qualquer rota com
crescimento e escape validados. O recurso de ciclo tenta preservar a ordem
até o último movimento até essa casa. **Não há garantia
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
Os relatórios somam `passos`, `passos_seguranca` e `mortes_fome_seguranca`
por nível, inclusive nas vitórias. A última contagem considera morte por
`limite_sem_comer` no movimento marcado como segurança; o histórico das
falhas inclui `modo` e `motivo_seguranca`.

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

## Validação da regressão do híbrido (2026-10-22)

Removida a imposição de ordem circular a partir de metade da meta e a
transição persistente por desalinhamento. Restaurado o planejador completo;
rotas temporais com escape validado não são interrompidas por um alerta
estático de área/rabo. Níveis, metas e limites permanecem iguais.

QA de 10 partidas por nível, quatro processos, sem repetir sorteios nem
descartar falhas desta execução:

| Nível | Vitórias | Passos em segurança / totais | Mortes por fome em segurança |
| --- | --- | --- | --- |
| 15x15 | 10/10 | 49/7288 | 0 |
| 20x20 | 10/10 | 265/19088 | 0 |
| 25x25 | 9/10 | 871/39719 | 1 |

Total: **29/30 (96,7%)**. O script ainda retorna reprovação porque exige
100%: houve uma fome residual em segurança com 132 gomos no 25x25,
partida 0. A lista completa e o histórico estão em `/workspace/qa/x.json`;
não foi substituída por outro sorteio. Não é uma certificação de 100%.

As duas listas originais de `tests/fixtures/derrotas_25x25.json` venceram:
**2/2**, com **198/7920** passos em segurança e **zero** mortes por fome
em segurança. Relatório: `/workspace/qa/repeticao.json`.

`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/pytest -q -m 'not slow'`:
**128 passed, 5 deselected**.
