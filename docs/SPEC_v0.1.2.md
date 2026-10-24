# Spec v0.1.2 (fechada 23/10/2026, liberada 23/10 14:00)
Base: `develop` c66d9cd. Branch: `feature/v0.1.2`. Fora do escopo (v0.5): menu principal, tela de configurações, config salva, tela de resultado, redesign.

## 1. Correção da janela (bug que motivou)
- Hoje abre em 1280x860, maior que a tela com escala do Windows; barra de título some.
- Trazer do PR #5 (`feature/v0.1.2-menus`) SÓ a correção da janela; depois o PR #5 é fechado sem merge.
- Critério: a janela cabe na área útil da tela (com escala 125%/150%), barra de título visível, dá pra mover e fechar.

## 2. Pendências da v0.1
- Arquivo de pontuação também guarda os pontos do algoritmo.
- Histórico de confiança do Laya preenchido em toda jogada (hoje fica quase vazio).
- Pausa com P e espaço; mostra "PAUSADO" por cima do jogo.
- No erro, a mensagem de falha sai antes do resumo zerado.

## 3. Retoque leve de UX (mesma tela, mesmas cores; sem redesign)
- Botões: clareiam no hover, afundam/escurecem ~100 ms no clique, cursor "mãozinha".
- Botões de alternar (Nível, Laya, Modo, Automático) no formato `<  Nível: 15x15  >`; clique direito ou seta volta a opção anterior.
- Treinar desativado com aparência clara e texto "disponível na v0.2".
- Campos (Partidas, Passos/s): borda destacada quando selecionados, cursor piscando; rejeitar letras e valores fora do limite, voltando ao último valor válido.
- Grade alinhada: rótulos e campos na mesma coluna, espaçamento igual.
- Teclado: Enter inicia, setas mudam a opção em foco, Tab passa entre controles.
- Status ao iniciar: "Carregando o Laya na GPU..." em vez de tela parada.

## 4. Modo rápido sem janela
- `python -m jogos.snake --partidas N --modo rapido --sem-janela`: roda sem abrir o Pygame, salva os dados igual ao modo com janela.
- `--sem-janela` com outro modo: avisa e não roda. `--partidas N` sem `--sem-janela` continua como hoje.
- Painel ao vivo no terminal (~4x/s, redesenha no lugar, sem rolar):
  - Cabeçalho: nível, versão do Laya, dispositivo (GPU GTX 1650 ou CPU), VRAM usada.
  - Sessão: barra de progresso (3/10), tempo passado, estimado pro fim, médio por partida.
  - Partida atual: comidas/meta (12/50 gomos), passos, passos sem comer x limite (23/60), pontos Laya x algoritmo, % jogadas iguais ao algoritmo, confiança média, ms por decisão, jogadas/s.
  - Acumulado: pontos totais Laya x algoritmo, melhor partida, vitórias, fim das partidas (parede / corpo / limite sem comer).
  - Resumo final em tabela + onde os dados foram salvos.
  - Ctrl+C para com segurança e salva o que já rodou.
- Base pra v0.4 (Kaggle não tem tela).

## 5. Atalho .bat opcional
- `Laya Games - Modo rápido.bat`: pergunta quantas partidas e roda `--modo rapido --sem-janela`. O instalador oferece criar (opcional, nada muda no PC sem confirmação).

## 6. Esquema de modelos (já entregue nesta branch)
- `config/modelos.yaml` (tabela 3B) + `scripts/tarefa.sh` (escolhe modelo, lê cota, avisa 50%/80%, backup, log). Regras: `docs/equipe/REGRAS_MODELOS.md`.

## Divisão sugerida (tipo -> `scripts/tarefa.sh`)
| Item | Tipo |
|---|---|
| 1 janela, 4 sem-janela/painel | logica |
| 2 pendências | logica (pontuação/confiança), bug-simples (ordem das mensagens) |
| 3 UX | ui |
| 5 .bat | instalador |
| testes | teste |

## Pronto quando
- Testes passam (1 linha), QA aprova checklist, Revisor aprova 1x, instalado no PC do Lucas.
