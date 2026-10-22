# Snake Laya

Jogo Snake em Python/Pygame jogado em tempo real pelo modelo de decisão [Laya](https://huggingface.co/convaiinnovations/laya).

## Como funciona
1. **Jogo (Pygame):** grid médio/grande, pontuação e tempo, com painel lateral mostrando as decisões do Laya (probabilidade de reto / esquerda / direita, estado recebido, confiança e latência).
2. **Laya:** recebe um resumo em texto da situação e escolhe a jogada.
3. **Algoritmo:** ao fim da partida, percorre o histórico e marca a melhor jogada em cada passo.
4. **Tutor Gemini:** analisa a partida e as correções do algoritmo e sugere o que treinar.
5. **Retreino:** o Laya é ajustado com as correções entre sessões.

## Estrutura
- `src/` código do jogo, painel, algoritmo, tutor e treino
- `docs/` documentação
- `runs/` partidas gravadas (fora do git)

Pesos do modelo e partidas gravadas não vão para o GitHub.
