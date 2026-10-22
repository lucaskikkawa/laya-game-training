# Algoritmo de referência: implementação e limite atual

**Ainda não atende ao requisito de 100% de vitórias. A v0.1 não está pronta
para aceitação enquanto o teste slow não passar nos quatro níveis.**

O código atual não consulta comidas futuras. Em cada estado:

1. Calcula distâncias BFS até a recompensa e simula caminhos mínimos.
2. Confere se o corpo simulado, já crescido, permite alcançar o rabo.
3. Prefere trajetórias que deixem todo o espaço livre acessível. Examina outras
   aproximações da comida e pequenos desvios para liberar mais rabo.
4. Se necessário, busca configurações temporais do corpo com um orçamento
   limitado; rejeita trajetórias que excedam o prazo restante para comer.
5. Se não encontra uma rota aceitável, alonga o caminho seguro até o rabo e
   reavalia após um passo. O último fallback é uma jogada sem colisão imediata.

O cache de trajetória é invalidado se o estado divergir do previsto, inclusive
quando usado para sugerir jogadas nos estados produzidos pelo Laya.

## Por que isso não é uma prova de vitória

Alcançar o rabo depois de comer verifica uma saída naquele instante. Não garante
que a próxima comida estará acessível antes da fome. Seguir um caminho longo
até o rabo pode exceder 60/80/100/120 passos; manter-se sem colisões não basta.

Um ciclo hamiltoniano fixo também não resolve o requisito: um ciclo de centenas
de casas pode colocar a comida a mais passos que o limite. Além disso, mapas
15×15 e 25×25 não têm ciclo hamiltoniano cobrindo todas as casas: o grafo é
bipartido e tem número ímpar de vértices. Apenas adicionar atalhos sem uma prova
sobre o prazo não permite chamar a estratégia de garantida.

As tentativas atuais de atalhos/busca temporal ainda apresentaram derrotas por
fome em amostras aleatórias, especialmente nos mapas maiores. O teste de
aceitação preserva esse erro: não usa xfail, não ressorteia comidas e não
transforma derrotas em vitórias. Não se deve tratar as sugestões atuais como
rótulos perfeitos para um treino futuro.

## Reprodução

```bash
.venv/bin/python -m pytest -m 'not slow'
.venv/bin/python -m pytest -m slow --qa-partidas 10
.venv/bin/python -m pytest -m slow  # padrão: 1000 por nível
.venv/bin/python scripts/qa_algoritmo.py --partidas 1000
```

O script retorna 1 se houver qualquer derrota e salva os resumos e as listas
completas das falhas em `runs/qa_algoritmo.json`. O pytest salva as falhas em seu
diretório temporário e informa o caminho na asserção. Todas essas listas usam
`secrets.randbelow`; a amostra reduzida é um diagnóstico, não substitui as
1000 partidas exigidas.

Ainda falta uma estratégia com garantia de alcance da próxima comida no prazo,
ou um planejador completo que demonstre isso para a sequência da sessão. Nenhum
resultado atual autoriza afirmar uma taxa de 100%. As regras, os limites e a
distribuição de comidas não foram alterados para facilitar o teste.
