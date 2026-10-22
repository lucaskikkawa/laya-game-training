# Algoritmo de referência e regra da comida

O QA exige 100% de vitórias em todos os níveis e preserva qualquer derrota
para reprodução. O script usa 200 partidas por nível por padrão, exigindo 100%.
O teste slow ampliado mantém 1.000 partidas por nível quando solicitado.
Os níveis jogáveis da v0.1 são 15x15, 20x20 e 25x25. O 30x30 está adiado,
com sua configuração (200 gomos, 120 passos) em `NIVEIS_ADIADOS`.

O código atual não consulta comidas futuras. Em cada estado:

1. Calcula distâncias BFS até a recompensa e simula caminhos mínimos.
2. Confere se o corpo simulado, já crescido, permite alcançar o rabo.
3. Prefere trajetórias que deixem todo o espaço livre acessível. Examina outras
   aproximações da comida e pequenos desvios para liberar mais rabo. Penaliza
   articulações do espaço livre: casas cuja ocupação separaria regiões,
   mesmo quando não existem becos.
4. Se necessário, busca configurações temporais do corpo com um orçamento
   limitado; rejeita trajetórias que excedam o prazo restante para comer.
   A deduplicação usa o corpo completo e ordenado: corpos com a mesma
   ocupação, mas ordens diferentes, liberam passagens em tempos diferentes.
   Esta é a correção única desta rodada; os demais orçamentos foram mantidos.
5. Tenta desvios em direção ao rabo antes de se aproximar da comida, simulando
   a trajetória completa e respeitando o prazo restante.
6. Se necessário, tenta A* com o corpo inteiro, guiado por distâncias temporais
   que consideram quando o corpo inicial libera cada passagem. O último fallback é uma jogada
   sem colisão imediata.

O cache de trajetória é invalidado se o estado divergir do previsto, inclusive
quando usado para sugerir jogadas nos estados produzidos pelo Laya.
Rotas reparadas e alternativas da busca são comparadas pela mesma avaliação;
uma alternativa de maior risco não substitui uma candidata melhor já encontrada.

## Regra da comida e auditoria

A decisão do Lucas (opção a) filtra a lista salva antes de aparecer cada comida.
A casa deve estar vazia e existir alcance da cabeça em até o limite sem comer
do nível. A busca usa estados (casa, tempo) e a liberação do corpo atual:
segmento `i`, com cabeça de índice 0, libera após `len(corpo) - i` passos.
Não existe espera parada. Casas podem ser revisitadas em instantes distintos,
pois uma passagem posterior pode encontrar um segmento já liberado.

Uma candidata ocupada é pulada com motivo `ocupada`; uma candidata vazia sem
alcance dentro do prazo é pulada com `inalcancavel`. Não há aleatoriedade nessa
seleção: estado e lista iguais produzem comida e pulos iguais. Esgotar a lista
continua sendo erro de sessão, sem sortear outra comida.

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
falham, uma busca A* com orçamento considera o corpo inteiro e a fome restante.
As heurísticas e o orçamento não constituem uma prova matemática de vitória.

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

## Resultados registrados

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
