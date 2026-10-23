# Laya Games · Snake v0.1

Snake com uma janela Pygame e painel das decisões do **Laya v000**, modelo base
`convaiinnovations/laya`, sem treino. Interface em português; estado e efeitos
das ações enviados ao modelo em inglês.

**Implementação em validação: o gabarito ainda perde por fome nos níveis maiores.
A v0.1 não está concluída.** Veja [estado do algoritmo e QA](docs/ALGORITMO.md).

Leia [Instalação no Windows/PowerShell](docs/INSTALACAO.md).
O [planejamento aprovado](docs/PLANEJAMENTO.md) é a fonte da verdade do projeto.

```powershell
.\scripts\instalar.ps1
.\.venv\Scripts\python.exe -m jogos.snake --partidas 1 --nivel 15 --versao v000 --modo normal
```

Na janela, selecione o nível e a versão e clique **Start**. O modelo é carregado
somente nesse momento. F11 alterna tela cheia e Tab esconde o painel. Há caixa
de velocidade, botões −1/+1, Retry e partidas automáticas. O modo rápido mostra
progresso e resumo, sem desenhar o tabuleiro.

| Mapa | Vitória (gomos, incluindo cabeça) | Passos sem comer |
|---|---:|---:|
| 15 × 15 | 50 | 60 |
| 20 × 20 | 90 | 80 |
| 25 × 25 | 140 | 100 |

30 × 30 adiado para depois da v0.1; configuração preservada em `NIVEIS_ADIADOS`.

Paredes e corpo matam. O rabo desocupa sua casa no mesmo passo, salvo ao comer.
Uma comida vale `max(10, 100 - 10 × excesso)`; o excesso usa a distância BFS
medida quando a comida apareceu. Se não havia caminho estático, a distância é
registrada como `null` e não há penalidade mensurável de excesso. Comer no último
passo permitido evita a fome. Não há mudança automática de nível.

## Organização

- `nucleo/`: contrato genérico, vocabulário, configuração e adaptador Laya.
- `jogos/snake/`: regras puras, algoritmo, sessão, GUI e sons sintetizados.
- `treino/`, `tutor/`: somente placeholders para versões futuras.
- `tests/`: pytest, mocks sem torch/Laya e GUI headless.
- `scripts/`: instalação Windows e QA do algoritmo.
- `modelos/`, `runs/`: dados locais ignorados pelo Git.

`LAYA_HOME` configura a raiz de dados. O padrão é o diretório atual; o instalador
usa `C:\Users\lucas\laya-games`. Modelos locais ficam em `modelos/laya_vNNN`.
Sem snapshot local, v000 usa o identificador público; versões inexistentes falham
com mensagem, sem substituir o modelo silenciosamente.

O adaptador chama `laya.load(...).system_one(...)`, com **uma pergunta choice e
três efeitos** (reto/esquerda/direita). CUDA usa autocast fp16; CPU é o fallback.
Carregamento e inferência ficam fora da thread gráfica. A tela mostra dispositivo,
VRAM quando há CUDA, latência, confiança, concordância, histórico e mapa recebido.
Não há tutor, treino, calibração ou modo de comparação visual na v0.1.

## Runs e auditoria

Cada sessão cria `runs/Laya_AAAA-MM-DD_HH-MM` (sufixo se houver colisão):

- `sessao.json`: lista de comidas gerada com `secrets.randbelow`, nível, versão,
  hardware, placar `Laya_Data_Hora`, status e resultados.
- `Laya_Data_Hora.json`: placar automático, com os resultados de cada run.
- `run_NNNN_laya.json`: estado por passo, probabilidades, escolha, confiança,
  jogada do algoritmo, latência, pontos, tempo e passos/s efetivos.
- `run_NNNN_algoritmo.json`: partida independente com o mesmo início da lista.
- `run_NNNN_comparacao.json`: pontos/passos/morte e concordância por passo,
  calculados em código. Não é o modo visual de comparação previsto para v0.2.
- `run_NNNN_laya_parcial.json`: checkpoint se houver erro ou fechamento.

Casas ocupadas são puladas. O próximo par de runs começa depois do maior índice
consumido pelo par anterior. A lista é gravada antes da primeira inferência; não
há sorteio oculto durante uma run. Gravações JSON usam substituição atômica.

## Desenvolvimento e QA

Para testar sem baixar torch nem pesos:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pytest pygame-ce==2.5.8 numpy==2.5.4
.venv/bin/python -m pytest -m 'not slow'
.venv/bin/python -m pytest -m slow --qa-partidas 10
.venv/bin/python scripts/qa_algoritmo.py  # padrão: 200 por nível, exige 100%
```

Os testes configuram `SDL_VIDEODRIVER=dummy` e `SDL_AUDIODRIVER=dummy`.
O teste slow ampliado exige 1000 partidas por nível; a opção rápida reduz a amostra,
não o critério de 100%. Nenhuma derrota é descartada ou substituída. O script
salva as listas das falhas para reprodução e retorna código 1 se houver derrota.
