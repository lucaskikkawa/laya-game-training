# Planejamento laya-game-training (Planejamento aprovado em 22/10/2026)
Atualizado: 22/10/2026 (Python 3.14 como padrão)

## Objetivo
O Laya joga jogos em Pygame em tempo real e aprende de verdade, não por tentativa aleatória, com conhecimento que passa de um jogo pra outro.
Usa vocabulário genérico: eu, perigo, recompensa, espaço livre, e as ações descritas pelo efeito.
Monorepo: nucleo/, treino/, tutor/, jogos/snake/

## Snake: visual e regras
Gomos verdes quadrados com uma linha fina entre eles, cabeça verde-escura com olhos, comida vermelha e fundo azul-marinho.
Paredes e o próprio corpo matam.

Níveis, escolhidos por Lucas numa tela de seleção, sem subir de nível automaticamente:

| Mapa | Vitória | Limite sem comer |
|---|---|---|
| 15x15 | 50 gomos | 60 passos |
| 20x20 | 90 gomos | 80 passos |
| 25x25 | 140 gomos | 100 passos |

30x30 adiado para depois da v0.1. Configuração preservada em
`NIVEIS_ADIADOS`: meta de 200 gomos e limite de 120 passos; não aparece no menu,
na CLI nem no QA dos níveis jogáveis.

Pontos: cada comida vale 100 menos 10 por passo além do caminho ideal, com mínimo de 10.
O ideal continua sendo o BFS estático calculado quando a comida aparece; se não
existir, registra `None` e não se cobra excesso mensurável.

Regra da comida (decisão do Lucas, opção a): a próxima casa da lista salva só
recebe comida se estiver vazia e alcançável da cabeça em até o limite sem comer
do nível, considerando a liberação temporal do corpo atual: segmento de índice
`i` (cabeça = 0) libera sua casa após `len(corpo) - i` passos. A busca considera
casa e tempo, sem espera parada. Candidatas ocupadas ou inalcançáveis a tempo
são puladas, sem sorteio adicional. O resultado depende apenas do estado e da
lista salva; níveis e limites permanecem os da tabela.

O estado é o mapa inteiro em caracteres (. H B T F), mais a direção e o vocabulário genérico.
As jogadas são reto, esquerda e direita.
Opcional: a distância do algoritmo até a comida pra cada jogada.

## Modos
- Normal: animações suaves e som gerado por código, 1 passo/s por padrão, caixa de texto e botões +/-1.
- Rápido: o jogo não é desenhado, só uma tela de carregamento com o progresso (runs concluídas de N, tempo, resumo parcial). Número fixo de passos/s, ajustável, com padrão de 5 passos/s (ajustar depois de medir). Estimativa de base: na GTX 1650, isso usaria cerca de 70% da GPU, com (cerca de 80 a 250 ms por jogada na GTX 1650 em fp16), a medir na v0.1. Uma sessão de 50 runs levaria uns 20 a 60 minutos. Se o Laya calcular cada uma das 3 jogadas separadamente, pode cair pra uns 2 passos/s. A Intel UHD 630 não treina nem roda o Laya. Ela pode desenhar a janela: na instalação, configurar o python.exe como "Economia de energia" nas configurações de gráficos do Windows, e o Laya continua na GTX 1650 pelo CUDA. O Pygame desenha a maior parte pelo processador.
- Comparação: visual, a 1 passo/s como o modo normal. A janela tem 4 seções: 2 jogos e 2 painéis, com duas versões do Laya, por exemplo v001 e v002, nas mesmas comidas. Ao final, uma tabela comparando as duas, que só existe no modo comparação. As duas versões são carregadas no mesmo programa, o que dá uns 2,0 a 2,4 GB de memória de vídeo, pela estimativa.
- Seletor de versão do Laya (v000, v001...) na tela inicial.
- Modo automático: depois do game over, a próxima partida começa sozinha.
- Controles: Start (conecta com o Laya), Retry, "Partidas seguidas X", botão Treinar e a linha de comando `--partidas N`, que o Boss pode rodar no PC do Lucas, com aprovação dele, abrindo a janela na tela do Lucas. O mesmo vale pro treino.

## GUI (uma janela só: jogo de um lado, painel do outro, 60 fps)
- O que o Laya recebeu (estado), as probabilidades por jogada (ex.: 80/9/11), a escolha, a confiança e a latência.
- Barras de probabilidade animadas.
- Seta na cabeça com cor de acordo com a confiança.
- Medidor de confiança.
- Concordância com o algoritmo ao vivo.
- Histórico e mini gráfico de confiança.
- Placar com animação.
- No modo rápido o jogo e o painel não são desenhados, só a tela de carregamento com o progresso.
- A janela pode ir pra tela cheia ou ser redimensionada.
- Atalho pra esconder o painel.

Relatório do Gemini (via agy):
- Modo normal: um relatório por run.
- Modo comparação: um relatório depois de cada run, focado nas diferenças entre as duas versões.
- Modo rápido: um único relatório das X runs da sessão, sem relatórios individuais.

Onde aparece: na tela de resultado do Pygame, um resumo curto com uns 3 pontos principais e o botão "Ver relatório completo". Esse botão abre o relatório inteiro no navegador, como uma página salva junto da run.

Telas de resultado:
- Modo normal: tela de resultado a cada run.
- Modo rápido: tela de resumo só no fim da sessão.

## Algoritmo (gabarito, não pode errar)
- Híbrido na v0.1 (etapa 3): BFS principal com teste do rabo após crescer e
  ciclo de segurança pré-calculado por nível. Entra em segurança se faltar
  caminho seguro, a área livre alcançável for menor que a cobra ou o rabo
  ficar inalcançável. O planejador BFS completo não exige ordem circular;
  tamanho e desalinhamento não são gatilhos. Reavalia o BFS em cada passo de
  segurança e preserva rotas temporais validadas mesmo com risco estático de
  área/rabo, incluindo perto do limite sem comer.
  O ciclo e os atalhos ordenados ficam como recursos do modo segurança.
- 20x20: ciclo completo. 15x15 e 25x25: ciclo com uma casa omitida, `(n-1, 0)`,
  com saída validada para comer nela e posterior reentrada; sem garantia
  total. O limite sem comer permanece 100 no 25x25. Detalhes em
  `docs/ALGORITMO.md`; a etapa não certifica novamente o QA completo.
- Cada passo registra `modo` (`bfs`/`seguranca`) e `motivo_seguranca`; os
  resumos das runs contam os passos em segurança por motivo.
- O script de QA roda 200 partidas por nível por padrão e exige 100% de vitórias. Qualquer derrota reprova o QA e é registrada para reprodução.

Resultados históricos anteriores ao híbrido e à correção única: 15x15 **200/200**,
20x20 **200/200**, 25x25 **198/200**. O 25x25 ainda não satisfaz os 100%.
Após a correção única, somente as falhas 62 e 128 foram repetidas com as
mesmas listas: **2/2 vitórias**. Isso não certifica os 200 casos após a alteração.
O QA completo não foi executado nesta rodada.
O teste `slow` ampliado mantém 1.000 partidas por nível, quando solicitado.

## Arquivos de cada sessão
- Run do Laya: `Laya_AAAA-MM-DD_HH-MM`, com o estado, as probabilidades, a escolha, a confiança e a jogada ideal em cada passo.
- Run do algoritmo: um jogo à parte, com a mesma lista de comidas pré-sorteada. Aplica a mesma regra de comida alcançável a tempo descrita acima.
- Ambas as runs registram `pulos`: `{indice, posicao, motivo, passo}`, com motivo
  `ocupada` ou `inalcancavel`, e `comidas_efetivas` (comidas que apareceram).
  Índices dos arquivos são absolutos na lista da sessão, a partir de zero;
  `passo` é o total de movimentos já executados (0 na abertura).
  O Jogo mantém os mesmos registros com índices locais à sua lista.
- A sessão registra `valida_para_treino=true` e `motivo=null` inicialmente.
  Se qualquer run independente do algoritmo perder, toda a sessão recebe
  `valida_para_treino=false`, `motivo="algoritmo_perdeu"`, inclusive runs anteriores
  e posteriores. Uma vitória posterior não reabilita a sessão. A regra vale no
  modo normal e também no rápido. O painel de resultado avisa a exclusão e a
  comparação registra os campos. `treino/selecao.py` seleciona somente sessões
  concluídas explicitamente válidas; sessões antigas sem a marcação também
  ficam de fora. Nenhuma run de sessão inválida deve alimentar o treino.
- Placar automático `Laya_Data_Hora`.

Comparações, feitas pelo código, sem Gemini:
- Geral: pontos, passos e morte das duas runs.
- Pulos e comidas efetivas de cada run, com aviso e primeiro índice (base zero)
  de divergência das sequências efetivas. Uma sequência que termina antes
  diverge no primeiro elemento ausente. Os corpos podem diferir entre Laya e
  algoritmo, portanto os pulos também podem diferir apesar da lista comum.
- Passo a passo, estilo xadrez online.

## Ciclo
1. Sessão de runs no modo rápido. O tamanho é configurável, com padrão de 50, mas pode ser 10, 30 etc. As runs do modo normal também viram dados de treino. Quem decide quando já tem dados suficientes pra começar um novo treino é o Lucas (botão Treinar).
2. Correção.
3. Tutor.
4. Montagem do .jsonl.
5. Treino.
6. Cerca de 10 runs de calibração: partidas novas com comidas fixas, que servem de teste fixo e de calibração. Também cobrem situações antigas, pra ver se ele esqueceu algo.
7. Calibração (ajuste de temperatura), feita só na versão nova, depois do treino. Leva poucos segundos.
8. Salvar `laya_vNNN` com o ajuste e as notas.
9. Próximo ciclo.

Versões: `laya_v000` é a base sem treino e serve de referência. `laya_v001` é o primeiro treino. O v000 também pode jogar as runs de calibração, pra medir a evolução desde o início.
Se uma versão piorar, é descartada e voltamos pra anterior.

Dados de treino:
- Erros do Laya, corrigidos pelo algoritmo.
- Exemplos resolvidos tirados da run do algoritmo.
- Um caderno fixo de exemplos antigos, misturado em cerca de 30% de cada treino.

Limite de cerca de 30 minutos por treino no PC. Se passar, diminuímos os exemplos ou usamos o Kaggle.

## Tutor
- Gemini 3.5 Flash Lite no high, SOMENTE pelo `agy` (linha de comando do Antigravity) no PC do Lucas, usando a cota do AI Pro, como no FutaMugen. Sem API do Gemini, sem google-genai, sem chave no .env.
- O `agy` ainda não está instalado (só o app e a IDE do Antigravity em C:\Users\lucas\AppData\Local\Programs\). Instalar depois.
- No começo, o tutor é só o `agy`. Se a cota do `agy` acabar (ou ele falhar), o fallback é o Codex, modelo `gpt-6-luna` (GPT-6 Luna) em esforço médio (modelos do Codex: luna, sol, astra; nome confirmado).
- O prompt do tutor fica versionado em tutor/.
- Gera um relatório pra humanos e um arquivo de dados com as situações a reforçar e o peso de cada uma.
- Na v0.3, comparar lado a lado com o 3.8 Flash.

## Treino e ambiente
- REGRA DE HARDWARE: o Pygame roda no processador e na GPU integrada (Intel UHD 630). O Laya, para jogar e treinar, roda na GTX 1650 pelo CUDA.
- PC do Lucas: Dell G15, GTX 1650 4 GB, 32 GB de RAM, Windows 11.
- Usar um venv com Python 3.14 (PC do Lucas: 3.14.5) e torch com CUDA 12.6.
- Fine-tuning completo não cabe em 4 GB, então congelamos a maior parte do modelo.
- Teste de CPU contra GPU.
- Kaggle: também vamos testar o treino lá. São 2 T4, 29 GB de RAM, sessões de até 12 h e 30 h de GPU por semana. Precisa verificar o telefone, o que é quase certo, mas não achei a regra oficial.

## Equipe e fluxo de desenvolvimento
- Todo o desenvolvimento acontece no computador do Boss na nuvem; o jogo e o Laya rodam no PC do Lucas.
- Preparação do PC do Lucas (primeiro passo da v0.1): o Boss (único bot com acesso ao PC, sempre com aprovação do Lucas) cria a pasta C:\Users\lucas\laya-games\, faz o clone do repo, cria o venv, instala torch 2.14.1+cu126 (index cu126), transformers 5.20.2, pygame-ce, numpy, atualiza o laya pra 0.4.13, baixa o modelo convaiinnovations/laya (~1 GB) e confirma que o CUDA enxerga a GTX 1650.
- O desenvolvimento acontece no computador do Boss. O repositório é público: github.com/lucaskikkawa/laya-game-training.
- Dev Laya Games: dev sênior, usando o Codex `gpt-6.1-sol` no esforço médio, pra economizar cota.
- QA Laya Games: testa os PRs, o jogo, os arquivos de run e o treino no PC e no Kaggle.
- Revisor GitHub Laya Games: revisa a organização do repositório.
- Branches: main, develop e feature/fix/release, sempre entrando por PR.
- O .gitignore deixa de fora o .env, as runs, os modelos e os pesos (.safetensors, .pt e afins) e os .jsonl.
- Os bots só são atualizados com este planejamento quando ele estiver fechado, e só começam quando o Lucas disser "pode seguir".

## Observações sobre o Laya
- Sem treino, o Laya joga quase ao acaso. No teste deles, o fine-tuning subiu a precisão de 0,36 pra 0,77. Ele não raciocina passo a passo e não tem níveis de esforço.
- Tokens do mapa 30x30: o mapa vazio dá cerca de 119, o normal cerca de 130 a 250, e o pior caso (zigue-zague com 200 gomos) cerca de 456, o que cabe nos 512. Compactar por linha ficou pior, por isso foi descartado.

## Roadmap
- v0.1, primeiro passo: Preparação do PC do Lucas: o Boss (único bot com acesso ao PC, sempre com aprovação do Lucas) cria a pasta C:\Users\lucas\laya-games\, faz o clone do repo, cria o venv, instala torch 2.14.1+cu126 (index cu126), transformers 5.20.2, pygame-ce, numpy, atualiza o laya pra 0.4.13, baixa o modelo convaiinnovations/laya (~1 GB) e confirma que o CUDA enxerga a GTX 1650.
- v0.1: jogo, painel, níveis, algoritmo híbrido com BFS e ciclo de segurança (QA padrão de 200 partidas/nível, 100%) e runs. O Laya começa sem treino (v000). Medir GPU e passos/s.
- v0.2: treino no PC, calibração (runs de calibração + temperatura), modo comparação e teste de treino no Kaggle.
- v0.3: tutor via `agy` (relatórios + arquivo de pesos); comparar 3.5 Flash Lite com 3.8 Flash.
- v0.4: fluxo Kaggle completo.
- v0.5: segundo jogo e teste de transferência.

## Transferência para outros jogos
- Treinar em 2 ou 3 jogos simples com o mesmo vocabulário genérico e depois testar num jogo novo. O Mario foi só um exemplo e não será usado.
- Mais pra frente, misturar os tamanhos de mapa no treino.

## Em discussão
- Segundo jogo: decidir depois.


## Versões (verificadas em 22/10/2026, todas são as mais recentes)
- laya 0.4.13. O PC do Lucas tem a 0.3.28 e vai atualizar no venv. Repositório: NandhaKishorM/laya, modelos em huggingface.co/convaiinnovations.
- Checkpoint `convaiinnovations/laya`: 421M parâmetros, ModernBERT-large, 512 tokens.
- Alternativa `laya-multilingual`: 322M parâmetros, 1024 tokens, até 8192.
- torch 2.14.1+cu126, transformers 5.20.2 (fixar), pygame-ce 2.5.8, numpy 2.5.4. Todos rodam no Windows com Python 3.14 (torch tem wheel cp314 win_amd64 no índice cu126).
- Placa de vídeo, por estimativa: dois Laya em fp16 no mesmo programa ocupam uns 2,0 a 2,4 GB e cabem na GTX 1650. A medição de verdade fica pra v0.1.
- Treino no PC: só congelando a maior parte do modelo (LoRA ou só a parte final). O treino completo precisa de mais de 6,7 GB.

## Decisões da última rodada de pendências (22/10/2026)
1. Código: chega ao PC do Lucas por git clone/pull das releases, feito pelo Boss com aprovação do Lucas. Aprovado.
2. Se o `agy` falhar ou a cota acabar: fallback para o Codex, modelo `gpt-6-luna` (GPT-6 Luna) em esforço médio (nome confirmado).
3. Pasta no PC: C:\Users\lucas\laya-games\ (runs\, modelos\, relatorios\). Aprovado.
4. Testes de GPU só no PC do Lucas (meu computador não tem GPU).
5. Idioma: interface do Pygame, painel e relatórios em português. O texto interno de estado lido pelo Laya fica em inglês (o modelo padrão é em inglês; o laya-multilingual existe como opção). Sons simples e divertidos, escolhidos pelo Boss.
6. As listas de comida da calibração nunca entram no treino. As listas de comida são geradas com o módulo `secrets` do Python (entropia do sistema operacional, que mistura ruído de hardware) e salvas por sessão.
7. O prompt do tutor fica versionado em tutor/.
8. Backup do rascunho no Google Drive (feito). Reclonar só o laya-game-training agora; FutaMugen e os repositórios do WhatsApp só quando forem retomados. Refazer o login do Codex se precisar.

## Pendências
- Nenhuma pendência aberta no momento.
