import pytest
from jogos.snake.algoritmo import Algoritmo, alcanca_rabo, simular
from jogos.snake.regras import Jogo, ACOES, NIVEIS, lista_comidas
from scripts.qa_algoritmo import partida


def test_menor_caminho_seguro():
    g = Jogo(15, [(10, 7), (0, 0)])
    algoritmo = Algoritmo()
    for _ in range(3):
        assert algoritmo.escolher(g) == "straight"
        g.passo("straight")
    assert g.pontos == 100


def test_simular_comida_e_teste_rabo():
    corpo = [(2, 2), (1, 2), (0, 2)]
    futuro = simular(corpo, [(3, 2)], (3, 2))
    assert len(futuro) == 4
    assert alcanca_rabo(futuro, 15)
    assert simular(corpo, [(1, 2)], (10, 10)) is None


def test_acao_segura_quando_sobrevive():
    g = Jogo(15, [(0, 0), (0, 14), (14, 14), (14, 0), (5, 5)] * 40)
    algoritmo = Algoritmo()
    for _ in range(100):
        if g.fim:
            break
        acao = algoritmo.escolher(g)
        assert acao in ACOES
        if any(g.segura(a) for a in ACOES):
            assert g.segura(acao)
        g.passo(acao)


@pytest.mark.slow
@pytest.mark.parametrize("nivel", NIVEIS)
def test_mil_partidas_por_nivel(nivel, request, tmp_path):
    """QA de aceitação: não aceita perdas, rerolls, xfail ou descarte de casos."""
    import json
    quantidade = request.config.getoption("--qa-partidas")
    assert quantidade > 0
    falhas = []
    for indice in range(quantidade):
        comidas = lista_comidas(nivel, max(2000, NIVEIS[nivel].meta * 8))
        jogo = partida(nivel, comidas)
        if not jogo.vitoria:
            falhas.append({"partida": indice, "resumo": jogo.resumo(), "comidas": comidas})
    if falhas:
        arquivo = tmp_path / f"falhas_{nivel}.json"
        arquivo.write_text(json.dumps(falhas), encoding="utf-8")
    assert not falhas, f"{len(falhas)}/{quantidade} derrotas no nível {nivel}; reprodução em {arquivo}"
