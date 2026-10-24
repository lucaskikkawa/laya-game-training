# Regras de modelos e cota (seção 3B/3C, aprovado 23/10/2026)
- Nunca chame Codex/agy direto: `scripts/tarefa.sh TIPO "prompt"`. Tipos e cadeia de backup em `config/modelos.yaml`.
- Flash high (`pequena`): testes, funções pequenas, constantes, config, scripts auxiliares, mensagens/logs, refatoração mecânica, docstrings.
- Sol médio (`logica`, `treino-gpu`, `instalador`, `revisao-final`): lógica central, algoritmo, Laya/GPU, subprocesso/threads/loop, instalador, mudanças em vários arquivos.
- Sonnet high (`ui`): telas e visual. Argon/Opus high (`bug-dificil`): só bug difícil ou reprovado no QA.
- Cota: o script lê antes de cada tarefa (agy /usage + rate_limits do Codex, "restante", pode estar defasado). >=50%: aviso em `logs/avisos-cota.log` (uma vez por janela) -> mande ao Boss. >=80%: o script pula pro backup sozinho.
- Sem modelo disponível: o script para; avise o Boss.
- `scripts/tarefa.sh --cota` mostra a cota; `--dry-run TIPO` mostra o modelo escolhido.
