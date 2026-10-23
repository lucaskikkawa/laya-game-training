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
    g = Jogo(15, [(7, 7)])
    assert g.fim and g.morte == "lista_esgotada"


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
        {"indice": 0, "posicao": (0, 1), "motivo": "ocupada", "passo": 17, "area_alcancavel": 0},
        {"indice": 1, "posicao": (0, 3), "motivo": "inalcancavel", "passo": 17, "area_alcancavel": 0}]
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


def test_sem_saida_antes_do_limite_termina_sem_consultar_candidatas():
    g = jogo()
    g.corpo = [(x, y) for y in range(8)
               for x in (range(15) if y % 2 == 0 else range(14, -1, -1))]
    # Ambos os vizinhos da cabeça só liberam depois do limite real de 60.
    g.comidas = [(14, 14), (0, 0)]
    g.indice_comida = 0
    g.passos = 42
    g._nova_comida()
    assert g.fim and g.morte == "sem_comida_valida"
    assert g.indice_comida == 0 and g.pulos == []


def test_metricas_espaco_conferem_com_bfs_independente():
    from jogos.snake.regras import metricas_espaco
    for corpo in ([(2, 2), (1, 2), (0, 2)],
                  [(0, 0), (1, 0), (1, 1), (0, 1)]):
        for comida in ((3, 3), (0, 3)):
            livres = {(x, y) for x in range(4) for y in range(4)} - set(corpo)
            area = sum(caminho_bfs(corpo[0], p, corpo[1:], 4) is not None for p in livres)
            rota = caminho_bfs(corpo[0], comida, corpo[1:], 4)
            assert metricas_espaco(corpo, 4, comida) == {
                'area_alcancavel': area,
                'distancia_bfs_comida': len(rota) if rota is not None else None,
                'rabo_alcancavel': caminho_bfs(corpo[0], corpo[-1], corpo[1:-1], 4) is not None}


def test_bolsao_rabo_alcancavel_mas_livre_so_depois_do_prazo():
    from jogos.snake.regras import alcanca_livre_no_prazo, alcancaveis_no_prazo
    from jogos.snake.algoritmo import alcanca_rabo
    corpo = [(0, 0), (1, 0), (1, 1), (0, 1)]
    assert alcanca_rabo(corpo, 4)
    assert not alcanca_livre_no_prazo(corpo, 4, 1)
    assert alcanca_livre_no_prazo(corpo, 4, 2)
    for prazo in range(5):
        assert alcanca_livre_no_prazo(corpo, 4, prazo) == bool(
            alcancaveis_no_prazo(corpo, 4, prazo) - set(corpo))


def test_sem_comida_valida_nao_consulta_milhares_de_itens():
    class ListaAuditada(list):
        def __getitem__(self, indice):
            pytest.fail('Não deve consultar candidatas quando nenhuma casa livre é válida')
    g = jogo()
    g.corpo = [(x, y) for y in range(8)
               for x in (range(15) if y % 2 == 0 else range(14, -1, -1))]
    g.comidas = ListaAuditada([(14, 14)] * 20000)
    g.indice_comida = 0
    g._nova_comida()
    assert g.morte == 'sem_comida_valida' and g.indice_comida == 0


@pytest.mark.parametrize("quantidade", [0, 20000])
def test_sem_comida_valida_apos_comer_preserva_indice_e_auditoria(
        preparar_comida_sem_saida, quantidade):
    class ListaAuditada(list):
        def __getitem__(self, indice):
            pytest.fail("Nenhuma candidata deve ser consultada após comer sem saída")

    g = preparar_comida_sem_saida([(1, 0), (0, 0)] + [(24, 24)] * quantidade)
    indice = g.indice_comida
    pulos = list(g.pulos)
    efetivas = list(g.comidas_efetivas)
    assert indice == 2 and len(pulos) == len(efetivas) == 1
    g.comidas = ListaAuditada(g.comidas)

    assert g.passo("straight") == 100

    assert g.fim and not g.vitoria and g.morte == "sem_comida_valida"
    assert len(g.corpo) < g.nivel.meta and g.nivel == NIVEIS[25]
    assert g.comida is None and g.indice_comida == indice
    assert g.pulos == pulos and g.comidas_efetivas == efetivas
    assert g.passos == g.comidas_consumidas == 1 and g.sem_comer == 0
    with pytest.raises(RuntimeError, match="já terminou"):
        g.passo("straight")
