# Regras gerais da equipe Laya (3C)
- Spec da versão inteira: `docs/SPEC_v0.1.2.md`. Roteiro: `docs/ROTEIRO.md`.
- Dispare Codex/agy e encerre o turno; não espere acordado. Saída vai pra `logs/`; leia só o resumo.
- Testes devolvem 1 linha ("165 passaram, 0 falharam"); detalhe só se falhar.
- Responda ao Boss/Chefe só ao terminar sua parte ou se travar. Progresso em `/workspace/planejamento/laya-games-status.md`.
- Branch `feature/v0.1.2`; sem merge, sem push forçado. Não mexer no PC do Lucas nem no PR #5.
- PT-BR em textos da interface e commits curtos.

## Testes
- Sempre `.venv/bin/python` (na box não existe `python`).
- Rápido (padrão, ~35 s, 154 testes): `timeout 170 .venv/bin/python -m pytest -q -m "not slow" -p no:cacheprovider 2>&1 | tail -1`
- Lentos (5 testes `@pytest.mark.slow` em tests/test_algoritmo.py: 1000 partidas por nível + reproduções 25x25; passam de 13 min): só no QA final, de preferência reduzidos: `.venv/bin/python -m pytest -q -m slow --qa-partidas 50 > logs/pytest-slow.log 2>&1; tail -1 logs/pytest-slow.log`
- Teste novo acima de 10 s leva `@pytest.mark.slow`.
