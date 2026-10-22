import pytest
from jogos.snake.regras import ACOES, Jogo, NIVEIS, caminho_bfs


def jogo(comida=(10, 7)):
    return Jogo(15, [comida, (14, 14), (0, 0)])


def test_niveis():
    assert [(n.tamanho, n.meta, n.limite) for n in NIVEIS.values()] == [
        (15, 50, 60), (20, 90, 80), (25, 140, 100)]
    from jogos.snake.regras import NIVEIS_ADIADOS, Nivel
    assert NIVEIS_ADIADOS == {30: Nivel(30, 200, 120)}
    with pytest.raises(KeyError):
        Jogo(30)


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


def test_alcance_temporal_libera_rabo_e_respeita_prazo():
    from jogos.snake.regras import alcancaveis_no_prazo
    corpo = [(0, 0), (1, 0), (1, 1), (0, 1)]
    # A única saída no primeiro passo é o rabo; BFS estático não chega.
    assert caminho_bfs(corpo[0], (0, 2), corpo[1:], 15) is None
    assert (0, 2) not in alcancaveis_no_prazo(corpo, 15, 1)
    assert (0, 2) in alcancaveis_no_prazo(corpo, 15, 2)
    # O pescoço só libera após três passos.
    assert (1, 0) not in alcancaveis_no_prazo(corpo, 15, 2)
    assert (1, 0) in alcancaveis_no_prazo(corpo, 15, 3)


def test_pulos_deterministas_motivos_passo_e_bfs_original():
    from jogos.snake.regras import Nivel

    def preparar():
        g = jogo()
        g.corpo = [(0, 0), (1, 0), (1, 1), (0, 1)]
        # Prazo curto para testar a fronteira exata, sem alterar NIVEIS.
        g.nivel = Nivel(15, 50, 2)
        g.comidas = [(0, 1), (0, 3), (0, 2)]
        g.indice_comida = 0
        g.passos = 17
        g._nova_comida()
        return g

    a, b = preparar(), preparar()
    assert a.pulos == b.pulos == [
        {"indice": 0, "posicao": (0, 1), "motivo": "ocupada", "passo": 17},
        {"indice": 1, "posicao": (0, 3), "motivo": "inalcancavel", "passo": 17}]
    assert a.comida == b.comida == (0, 2)
    assert a.indice_comida == b.indice_comida == 3
    assert a.ideal_comida is None  # Pontuação continua com o BFS estático.


def test_lista_json_produz_mesma_comida_e_pulos():
    lista = [(7, 7), (6, 7), (8, 7), (14, 14)]
    a = Jogo(15, lista)
    b = Jogo(15, [list(p) for p in lista])
    assert (a.comida, a.pulos, a.comidas_efetivas) == (b.comida, b.pulos, b.comidas_efetivas)


def test_alcance_revisita_casa_para_atravessar_liberacao_tardia():
    from jogos.snake.regras import alcancaveis_no_prazo
    corpo = [(1, 0), (2, 0), (3, 0), (3, 1), (2, 1), (1, 1),
             (1, 2), (0, 2), (0, 3), (1, 3), (2, 3)]
    # Sai pelo corredor esquerdo e precisa voltar por ele em outro instante.
    # Marcar cada casa como visitada uma única vez perde essa passagem.
    assert (3, 2) not in alcancaveis_no_prazo(corpo, 4, 7)
    assert (3, 2) in alcancaveis_no_prazo(corpo, 4, 8)


@pytest.mark.parametrize("alvo,rota", [
    ((0, 2), [(0, 1), (0, 2)]),
    ((1, 2), [(0, 1), (0, 2), (1, 2)]),
    ((2, 2), [(0, 1), (0, 2), (1, 2), (2, 2)]),
])
def test_pulos_nao_esgotam_lista_com_casa_alcancavel(alvo, rota, monkeypatch):
    from jogos.snake import regras
    from jogos.snake.algoritmo import simular

    g = jogo()
    g.corpo = [(0, 0), (1, 0), (1, 1), (0, 1)]
    g.nivel = regras.Nivel(15, 50, len(rota))
    # Testemunha independente: rota legal pelo rabo, com crescimento no alvo.
    futuro = simular(g.corpo, rota, alvo)
    assert futuro is not None and futuro[0] == alvo
    assert len(futuro) == len(g.corpo) + 1
    g.comidas = [(0, 1), (14, 14), alvo]
    g.indice_comida = 0
    g.pulos.clear()

    def sorteio_proibido(*args, **kwargs):
        pytest.fail("Pulos não podem sortear ou estender a lista")

    monkeypatch.setattr(regras, "lista_comidas", sorteio_proibido)
    g._nova_comida()
    assert g.comida == alvo and g.indice_comida == 3
    assert g.comidas == [(0, 1), (14, 14), alvo]
    assert [(p["indice"], p["motivo"]) for p in g.pulos] == [
        (0, "ocupada"), (1, "inalcancavel")]


def test_sem_saida_antes_do_limite_registra_inalcancavel_sem_ressortear():
    g = jogo()
    g.corpo = [(x, y) for y in range(8)
               for x in (range(15) if y % 2 == 0 else range(14, -1, -1))]
    # Ambos os vizinhos da cabeça só liberam depois do limite real de 60.
    g.comidas = [(14, 14), (0, 0)]
    g.indice_comida = 0
    g.passos = 42
    with pytest.raises(RuntimeError, match="esgotada"):
        g._nova_comida()
    assert g.pulos == [
        {"indice": 0, "posicao": (14, 14), "motivo": "inalcancavel", "passo": 42},
        {"indice": 1, "posicao": (0, 0), "motivo": "ocupada", "passo": 42}]
