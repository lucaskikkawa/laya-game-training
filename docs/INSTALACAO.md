# Instalação no Windows 11 (PowerShell)

O jogo usa Python 3.14 (o PC do Lucas tem 3.14.5), CUDA na NVIDIA quando disponível e CPU como fallback.
O modelo base não recebe treino nesta versão. Tenha Git, o Python Launcher (`py`)
e o driver NVIDIA instalados. Reserve espaço para o ambiente e o modelo (~1 GB).

1. Abra o PowerShell e clone o repositório:

   ```powershell
   git clone https://github.com/lucaskikkawa/laya-game-training.git C:\Users\lucas\laya-games
   cd C:\Users\lucas\laya-games
   ```

2. Execute o instalador (Windows PowerShell 5.1 ou PowerShell 7). Ele cria o venv, instala as versões fixadas, baixa o
   modelo público (checkpoint inglês da raiz) e informa se CUDA está disponível e qual GPU foi detectada:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\instalar.ps1
   ```

   Para outra pasta ou Python (a versão precisa ser compatível com os wheels):

   ```powershell
   .\scripts\instalar.ps1 -Destino D:\laya-games -Python 3.13   # opcional: outra versão do Python
   ```

   O script espera um checkout no destino; quando o destino está vazio, pode
   criar um clone local do checkout de origem. Não sobrescreve arquivos existentes.
   Não execute como administrador. Se uma versão fixada não estiver disponível,
   a instalação para com erro; o script não troca versões silenciosamente.
   Pode executá-lo novamente: reutiliza o venv, as versões instaladas e o snapshot local.

3. O instalador define `LAYA_HOME` como a raiz que contém `modelos/` e `runs/`.
   Abra um novo PowerShell ou defina a variável na janela atual:

   ```powershell
   $env:LAYA_HOME = 'C:\Users\lucas\laya-games'
   .\.venv\Scripts\Activate.ps1
   python -m jogos.snake --nivel 15 --versao v000 --modo normal
   ```

   Sem `--partidas`, clique **Iniciar** no menu principal, confira nível, versão e velocidade
   e clique **Começar** para conectar
   ao Laya. A primeira conexão pode demorar. O modo normal começa em 1 passo/s.
   O jogo mostra a run, as decisões e o resultado; Repetir cria uma nova sessão.
   Comandos completos sem ativar o venv, para uma partida normal no mapa 15×15:

   ```powershell
   .\.venv\Scripts\python.exe -m jogos.snake --partidas 1 --nivel 15 --versao v000 --modo normal
   .\.venv\Scripts\python.exe -m jogos.snake --partidas 1 --nivel 15 --versao v000 --modo normal --cpu
   ```

4. Para uma sessão rápida:

   ```powershell
   python -m jogos.snake --partidas 50 --nivel 20 --versao v000 --modo rapido --passos-por-segundo 5
   ```

   Com `--partidas N`, a sessão inicia sem clique, avança automaticamente e encerra com um resumo de pontos no terminal.
   A tela mostra progresso, tempo e resumo parcial,
   sem desenhar o tabuleiro. A velocidade pedida é um teto: a inferência pode
   limitar a velocidade real, que é medida nos JSONs. `--cpu` força CPU.

## Intel UHD e NVIDIA

Em **Configurações > Sistema > Tela > Elementos gráficos**, adicione
`C:\Users\lucas\laya-games\.venv\Scripts\python.exe`, abra **Opções** e escolha
**Economia de energia (Intel UHD)**. Isso permite deixar a janela/Pygame na
integrada. A inferência continua utilizando a NVIDIA explicitamente pelo CUDA.
A Intel UHD não executa CUDA. O painel mostra o dispositivo e a VRAM medida.

Para conferir manualmente:

```powershell
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

Se CUDA estiver indisponível, confira o driver NVIDIA e a instalação de torch
pelo índice `https://download.pytorch.org/whl/cu126`. Não instale um segundo
ambiente por cima do Python global.

## Pastas e controles

- `modelos/laya_v000`: snapshot de `convaiinnovations/laya`. Se não existir,
  v000 pode ser carregado pelo identificador público. Versões locais `laya_vNNN`
  aparecem na seleção. Só v000 é fornecida; não há treino na v0.1.
- `runs/Laya_AAAA-MM-DD_HH-MM[_NN]`: metadados, lista de comidas e runs JSON.
  Com `LAYA_HOME`, ambas as pastas ficam nessa raiz; sem ela, no diretório atual.
- **Configurações**: resolução (Automática usa o tamanho inicial adaptado ao desktop),
  janela/tela cheia, limite de FPS, vsync, painel e som. **Aplicar** salva em
  `config/usuario.json` (em `LAYA_HOME`, se definido) e aplica as preferências.
  Vsync depende do suporte do driver. **Voltar** descarta alterações não aplicadas.
- F11: tela cheia; Tab: painel. Esc: configuração da partida ou preferências →
  menu principal; no jogo, volta à seleção quando não houver tarefa em execução.
  No menu principal, Esc mantém a janela aberta; use **Sair** para fechar.
- Caixa de passos/s e botões −1/+1: velocidade; automático: próxima partida
  sem intervenção. No modo normal o resultado aparece entre as runs.
- Treinar fica desabilitado, previsto para v0.2.

## Testes sem modelo ou GPU

```powershell
python -m pytest -m 'not slow'
python -m pytest -m slow --qa-partidas 10
python -m pytest -m slow
python scripts/qa_algoritmo.py  # padrão: 200 por nível, exige 100%
```

Os testes configuram SDL de vídeo/áudio dummy. Para desenvolver sem instalar
modelo/torch, crie um venv e instale apenas `pytest pygame-ce==2.5.8 numpy==2.5.4`.
Não há download nem import de torch nos testes com mocks.
