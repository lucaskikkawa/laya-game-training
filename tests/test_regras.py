import pytest
from jogos.snake.regras import ACOES, Jogo, NIVEIS, caminho_bfs


def jogo(comida=(10, 7)):
    return Jogo(15, [comida, (14, 14), (0, 0)])


def test_niveis():
    assert [(n.tamanho, n.meta, n.limite) for n in NIVEIS.values()] == [
        (15, 50, 60), (20, 90, 80), (25, 140, 100), (30, 200, 120)]


def test_acoes_relativas():
    g = jogo()
    assert g.destino("straight") == ((8, 7), 1)
    assert g.destino("left") == ((7, 6), 0)
    assert g.destino("right") == ((7, 8), 2)
    with pytest.raises(ValueError):
        g.passo("up")


def test_parede():
    g = jogo((0, 0))
    for _ in range(8):
        g.passo("straight")
    assert g.fim and g.morte == "parede"
    with pytest.raises(RuntimeError):
        g.passo("straight")


def test_corpo_e_rabo_que_sai():
    g = jogo()
    g.corpo = [(3, 3), (3, 4), (4, 4), (4, 3)]
    g.direcao = 1
    assert g.segura("straight")  # antiga posição do rabo sai ao mesmo tempo
    g.passo("straight")
    assert not g.fim
    g.corpo = [(3, 3), (4, 3), (4, 4), (3, 4)]
    g.direcao = 1
    g.passo("straight")
    assert g.morte == "corpo"


@pytest.mark.parametrize("acoes,pontos", [(["straight"] * 3, 100),
    (["left", "right", "straight", "straight", "right"], 80)])
def test_pontos_bfs_original(acoes, pontos):
    g = jogo()
    assert g.ideal_comida == 3
    for acao in acoes:
        ganhos = g.passo(acao)
    assert ganhos == pontos
    assert g.pontos == pontos
    assert len(g.corpo) == 4 and g.sem_comer == 0


def test_pontos_minimos():
    g = jogo((8, 7))
    g.sem_comer = 30
    assert g.passo("straight") == 10


def test_limite_e_comer_no_ultimo_passo():
    g = jogo((0, 0))
    g.sem_comer = 59
    g.passo("straight")
    assert g.morte == "limite_sem_comer"
    g = jogo((8, 7))
    g.sem_comer = 59
    g.passo("straight")
    assert not g.fim and g.sem_comer == 0


def test_vitoria_sem_subir_nivel():
    g = jogo((8, 7))
    # Configuração longa só para verificar a condição de término da regra.
    g.corpo = [(7, 7), (6, 7)] + [(x, y) for y in range(3) for x in range(15)] + [(0, 3), (1, 3)]
    assert len(g.corpo) == 49
    g.passo("straight")
    assert g.vitoria and g.fim and g.nivel.tamanho == 15


def test_comidas_ocupadas_puladas():
    g = Jogo(15, [(7, 7), (6, 7), (8, 7), (0, 0)])
    assert g.comida == (8, 7) and g.indice_comida == 3
    g.passo("straight")
    assert g.comida == (0, 0)


def test_lista_esgotada_nao_ressorteia():
    with pytest.raises(RuntimeError, match="esgotada"):
        Jogo(15, [(7, 7)])


@pytest.mark.parametrize("nivel", NIVEIS)
def test_estado_mapa_inteiro_em_ingles(nivel):
    g = Jogo(nivel, [(0, 0)])
    texto = g.estado()
    linhas = texto.splitlines()
    mapa = linhas[3:]
    assert len(mapa) == nivel and all(len(linha) == nivel for linha in mapa)
    assert set("".join(mapa)) == set(".HBTF")
    assert "Direction: east" in texto and "self" in texto and "reward" in texto and "danger" in texto


def test_bfs():
    assert caminho_bfs((0, 0), (1, 1), [], 15) in [[(1, 0), (1, 1)], [(0, 1), (1, 1)]]
    assert caminho_bfs((0, 0), (2, 2), [(1, 0), (0, 1)], 15) is None
