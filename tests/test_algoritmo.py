import pytest
from jogos.snake.algoritmo import Algoritmo, alcanca_rabo, simular
from jogos.snake.regras import Jogo, ACOES, NIVEIS, lista_comidas
from scripts.qa_algoritmo import partida


@pytest.mark.slow
@pytest.mark.parametrize("indice", (62, 128), ids=("partida-62-corpo", "partida-128-lista"))
def test_derrotas_25x25_vencem_com_listas_originais(indice, monkeypatch):
    import json
    from pathlib import Path
    from jogos.snake import regras

    casos = json.loads((Path(__file__).parent / "fixtures" / "derrotas_25x25.json")
                       .read_text(encoding="utf-8"))
    caso = next(c for c in casos if c["partida"] == indice)
    comidas = caso["comidas"]
    original = [p[:] for p in comidas]

    def sorteio_proibido(*args, **kwargs):
        pytest.fail("Regressão deve usar exclusivamente a lista original")

    monkeypatch.setattr(regras, "lista_comidas", sorteio_proibido)
    g = partida(caso["nivel"], comidas)
    assert g.vitoria and g.fim and g.morte is None, g.resumo()
    assert len(g.corpo) == g.nivel.meta
    assert g.comidas_consumidas == g.nivel.meta - 3
    assert comidas == original
    assert g.comidas == [tuple(p) for p in original]
    assert g.indice_comida <= len(original)


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


def test_rota_preserva_espaco_livre_ao_sair_da_borda():
    # Regressão: a rota direta comia, mas deixava um beco junto à borda.
    g = Jogo(20, [(6, 19), (0, 0)])
    g.corpo = ([(x, 0) for x in range(17, 6, -1)]
               + [(7, y) for y in range(1, 7)]
               + [(6, y) for y in range(6, 17)] + [(5, 16), (4, 16)])
    g.direcao = 1
    algoritmo = Algoritmo()
    while g.comidas_consumidas == 0 and not g.fim:
        g.passo(algoritmo.escolher(g))
    assert not g.fim and g.comidas_consumidas == 1
    assert g.passos <= g.nivel.limite
    livres = {(x, y) for y in range(20) for x in range(20)} - set(g.corpo)
    from jogos.snake.regras import adjacentes, caminho_bfs
    assert all(sum(q in livres for q in adjacentes(p, 20)) >= 2 for p in livres)
    assert all(caminho_bfs(next(iter(livres)), p, g.corpo, 20) is not None for p in livres)


def test_qa_preserva_erro_de_lista_como_falha(monkeypatch):
    from scripts import qa_algoritmo
    comidas = [(8, 7), (8, 7)]
    monkeypatch.setattr(qa_algoritmo, "lista_comidas", lambda n: comidas)
    # Ao comer a primeira, a única candidata restante está ocupada.
    monkeypatch.setattr(Algoritmo, "escolher", lambda self, jogo: "straight")
    nivel, falha = qa_algoritmo.diagnosticar((15, 9))
    assert nivel == 15 and falha["partida"] == 9
    assert falha["erro"] is None
    assert falha["resumo"]["morte"] == "lista_esgotada"
    assert falha["comidas"] == comidas
    assert falha["pulos"] == [
        {"indice": 1, "posicao": (8, 7), "motivo": "ocupada", "passo": 1,
         "area_alcancavel": 221}]


def test_gargalo_detectado_mesmo_sem_becos():
    from jogos.snake.regras import adjacentes
    algoritmo = Algoritmo()
    algoritmo.configurar(15)
    # Duas salas 2x2 ligadas por uma casa: nenhum beco, mas ocupar a ponte
    # separa as salas e pode prender a cabeça durante o crescimento.
    livres = {(0, 0), (1, 0), (0, 1), (1, 1), (2, 0),
              (3, 0), (4, 0), (3, 1), (4, 1)}
    assert all(sum(q in livres for q in adjacentes(p, 15)) >= 2 for p in livres)
    mascara = sum(algoritmo._bits[p] for p in livres)
    assert algoritmo.gargalos(mascara) == 3
    assert algoritmo.gargalos(sum(algoritmo._bits[p] for p in livres if p[0] < 2)) == 0


def test_busca_nao_substitui_rota_melhor_por_rota_que_isola_regiao():
    import json
    from pathlib import Path
    from jogos.snake.regras import caminho_bfs
    # Estado reproduzido de uma derrota no QA de 200 partidas do nível 25.
    estado = json.loads((Path(__file__).parent / "fixtures" / "rota_25.json").read_text())
    g = Jogo(25, [estado["comida"], (0, 0)])
    g.corpo = [tuple(p) for p in estado["corpo"]]
    g.direcao = estado["direcao"]
    g.sem_comer = estado["sem_comer"]
    algoritmo = Algoritmo()
    algoritmo.configurar(25)
    rota = algoritmo.planejar(g)
    futuro = simular(g.corpo, rota, g.comida)
    assert futuro is not None and futuro[0] == g.comida
    assert len(rota) <= g.nivel.limite - g.sem_comer
    livres = set(algoritmo._bits) - set(futuro)
    assert all(caminho_bfs(next(iter(livres)), p, futuro, 25) is not None for p in livres)


def test_busca_corpo_atravessa_liberacao_tardia_dentro_do_prazo():
    import json
    from pathlib import Path
    estado = json.loads((Path(__file__).parent / "fixtures" / "liberacao_25.json").read_text())
    g = Jogo(25, [estado["comida"], (0, 0)])
    g.corpo = [tuple(p) for p in estado["corpo"]]
    g.direcao = estado["direcao"]
    g.sem_comer = estado["sem_comer"]
    algoritmo = Algoritmo()
    algoritmo.configurar(25)
    rota = algoritmo.busca_corpo(g)
    assert rota and len(rota) <= g.nivel.limite - g.sem_comer
    futuro = simular(g.corpo, rota, g.comida)
    assert futuro is not None and futuro[0] == g.comida


@pytest.mark.parametrize("nivel", NIVEIS)
def test_concavidade_incremental_equivale_ao_calculo_completo(nivel):
    from jogos.snake.regras import adjacentes
    algoritmo = Algoritmo()
    algoritmo.configurar(nivel)
    serpentina = [(x, y) for y in range(nivel)
                  for x in (range(nivel) if y % 2 == 0 else range(nivel - 1, -1, -1))]
    for tamanho in (3, NIVEIS[nivel].meta // 2, NIVEIS[nivel].meta - 1):
        corpo = serpentina[nivel + 3:nivel + 3 + tamanho]
        antes = sum(algoritmo._bits[p] for p in corpo)
        for p in adjacentes(corpo[0], nivel):
            depois = (antes & ~algoritmo._bits[corpo[-1]]) | algoritmo._bits[p]
            valor = algoritmo.concavidade_apos_passo(
                antes, depois, corpo[-1], p, algoritmo.concavidade(antes))
            assert valor == algoritmo.concavidade(depois)


def test_desvio_pelo_rabo_antes_de_comer_e_simulado_no_prazo():
    g = Jogo(15, [(8, 7), (0, 0)])
    algoritmo = Algoritmo()
    algoritmo.configurar(15)
    valor, rota = algoritmo.desviar_pelo_rabo(g)
    assert valor[0] and rota[0] != g.comida
    assert len(rota) <= g.nivel.limite
    futuro = simular(g.corpo, rota, g.comida)
    assert futuro is not None and futuro[0] == g.comida
    assert len(futuro) == len(g.corpo) + 1


def test_pontuar_rejeita_bolsao_mesmo_com_rabo_alcancavel():
    algoritmo = Algoritmo()
    algoritmo.configurar(4)
    # Comer fecha o quadrado no canto; o rabo é vizinho, mas não há casa
    # livre disponível no prazo de um passo depois do crescimento.
    corpo = [(1, 0), (1, 1), (0, 1)]
    futuro = simular(corpo, [(0, 0)], (0, 0))
    assert alcanca_rabo(futuro, 4)
    assert algoritmo.pontuar(corpo, [(0, 0)], (0, 0), 10, 1) is None
    # A vitória encerra antes de precisar de outra comida.
    assert algoritmo.pontuar(corpo, [(0, 0)], (0, 0), 4, 1)[0]


def test_emergencia_recusa_bolsao_com_prazo_insuficiente():
    g = Jogo(15, [(8, 7)])
    g.corpo = [(1, 0), (1, 1), (0, 1), (0, 2)]
    g.direcao = 0
    g.sem_comer = 58
    algoritmo = Algoritmo()
    assert g.segura('left')  # (0,0): único passo seguinte seria corpo bloqueado
    assert algoritmo.emergencia(g) == 'right'


@pytest.mark.parametrize('nivel', (15, 20, 25))
def test_ciclo_precalculado_cobre_tabuleiro_e_fecha(nivel):
    from jogos.snake.algoritmo import ciclo_por_nivel
    ciclo = ciclo_por_nivel(nivel)
    assert ciclo_por_nivel(nivel) is ciclo
    assert len(ciclo) == len(set(ciclo)) == nivel * nivel - nivel % 2
    tabuleiro = {(x, y) for x in range(nivel) for y in range(nivel)}
    assert tabuleiro - set(ciclo) == ({(nivel - 1, 0)} if nivel % 2 else set())
    assert set(ciclo) <= tabuleiro
    assert all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
               for a, b in zip(ciclo, ciclo[1:] + ciclo[:1]))


def test_gatilho_bfs_sem_rota_e_retorno_ao_bfs(monkeypatch):
    g = Jogo(20, [(12, 10), (0, 0)])
    a = Algoritmo()
    with monkeypatch.context() as patch:
        patch.setattr(a, 'planejar_rapido', lambda *args, **kwargs: [])
        acao = a.escolher(g)
    assert g.segura(acao)
    assert (a.modo, a.motivo_seguranca) == ('seguranca', 'bfs_sem_caminho_seguro')
    g.passo(acao)
    a.escolher(g)
    assert (a.modo, a.motivo_seguranca) == ('bfs', None)


@pytest.mark.parametrize('corpo,motivo', [
    ([(0, 0), (1, 0), (1, 1), (0, 1)], 'area_pequena'),
    ([(1, 1), (1, 0), (2, 0), (2, 1), (2, 2), (1, 2),
      (0, 2), (0, 1), (0, 0)], 'rabo_inalcancavel'),
])
def test_gatilhos_reais_de_area_e_rabo(corpo, motivo):
    g = Jogo(15, [(0, 3)])
    g.corpo, g.direcao = corpo, 2
    a = Algoritmo()
    acao = a.escolher(g)
    if any(g.segura(acao) for acao in ACOES):
        assert g.segura(acao)
    assert a.modo == 'seguranca' and a.motivo_seguranca == motivo


def jogo_no_ciclo(nivel=20, indice=100):
    from jogos.snake.regras import DIRECOES
    a = Algoritmo()
    a.configurar(nivel)
    g = Jogo(nivel, [a.ciclo[(indice + 60) % len(a.ciclo)], (0, 0)])
    tamanho = g.nivel.meta // 2
    g.corpo = [a.ciclo[(indice - i) % len(a.ciclo)] for i in range(tamanho)]
    g.direcao = DIRECOES.index((g.corpo[0][0] - g.corpo[1][0],
                               g.corpo[0][1] - g.corpo[1][1]))
    return g, a


@pytest.mark.parametrize('nivel', (15, 20, 25))
def test_bfs_grande_respeita_ordem_inclusive_ao_crescer(nivel):
    g, a = jogo_no_ciclo(nivel)
    for _ in range(g.nivel.limite):
        antes = list(g.corpo)
        comida = g.comida
        acao = a.escolher(g)
        assert g.segura(acao)
        assert a.passo_ordenado(antes, g.destino(acao)[0], comida)
        g.passo(acao)
        assert a.alinhado(g.corpo)
        if g.comidas_consumidas:
            break
    assert g.comidas_consumidas == 1 and not g.fim


def test_atalhos_nao_pulam_comida_nem_rabo_e_reservam_folga():
    g, a = jogo_no_ciclo()
    cabeca = g.corpo[0]
    from jogos.snake.regras import adjacentes
    atalho = next(p for p in adjacentes(cabeca, 20)
                  if 1 < (a.ordem[p] - a.ordem[cabeca]) % len(a.ciclo) < 100)
    sucessor = a.ciclo[(a.ordem[cabeca] + 1) % len(a.ciclo)]
    assert a.passo_ordenado(g.corpo, atalho, atalho)
    assert not a.passo_ordenado(g.corpo, atalho, sucessor)
    assert not a.passo_ordenado(g.corpo, g.corpo[-1], g.comida)
    # O rabo está duas posições além do atalho: sobra insuficiente para crescer.
    indice = a.ordem[atalho]
    apertado = [cabeca, a.ciclo[(indice + 2) % len(a.ciclo)]]
    assert a.alinhado(apertado)
    assert not a.passo_ordenado(apertado, atalho, atalho)


def test_seguranca_alinhada_segue_ciclo_quando_nao_ha_atalho(monkeypatch):
    g, a = jogo_no_ciclo()
    monkeypatch.setattr(a, 'planejar_rapido', lambda *args, **kwargs: [])
    acao = a.escolher(g)
    assert a.modo == 'seguranca' and a.estrategia == 'seguranca_ciclo'
    assert g.destino(acao)[0] == a.ciclo[101]


def test_transicao_desalinhada_segue_rabo_ate_alinhar():
    g = Jogo(20, [(15, 15)])
    g.corpo = ([(x, 0) for x in range(19, -1, -1)]
               + [(0, y) for y in range(1, 20)] + [(x, 19) for x in range(1, 12)])
    g.direcao = 1
    a = Algoritmo()
    a.configurar(20)
    assert not a.alinhado(g.corpo)
    for _ in range(12):
        from jogos.snake.regras import caminho_bfs
        rabo = caminho_bfs(g.corpo[0], g.corpo[-1], g.corpo[1:-1] + [g.comida], 20)
        acao = a.escolher(g)
        assert a.modo == 'seguranca'
        assert a.estrategia == 'seguranca_alinhar_seguindo_rabo'
        assert g.destino(acao)[0] == rabo[0]
        g.passo(acao)
        if a.alinhado(g.corpo):
            break
    assert not g.fim


@pytest.mark.parametrize('nivel', (15, 25))
def test_comida_na_casa_omitida_tem_escape_e_reentrada(nivel):
    g, a = jogo_no_ciclo(nivel)
    # Cabeça na borda superior, ao lado da casa omitida.
    indice = a.ordem[(nivel - 1, 1)]
    tamanho = g.nivel.meta // 2
    g.corpo = [a.ciclo[(indice - i) % len(a.ciclo)] for i in range(tamanho)]
    g.direcao = 0
    g.comida = (nivel - 1, 0)
    acao = a.escolher(g)
    assert g.segura(acao) and g.destino(acao)[0] == g.comida
    g.passo(acao)
    assert g.comidas_consumidas == 1
    if not g.fim:
        acao = a.escolher(g)
        assert g.segura(acao) and g.destino(acao)[0] in a.ordem


def test_transicao_solta_desalinho_no_rabo_e_preserva_ordem():
    from jogos.snake.regras import DIRECOES
    g, a = jogo_no_ciclo()
    g.corpo = list(reversed(a.ciclo[60:100])) + [
        (3, 18), (3, 19), (2, 19), (1, 19), (1, 18)]
    g.direcao = DIRECOES.index((g.corpo[0][0] - g.corpo[1][0],
                               g.corpo[0][1] - g.corpo[1][1]))
    g.comida = (15, 15)
    assert not a.alinhado(g.corpo)
    acao = a.escolher(g)
    assert a.estrategia == 'seguranca_alinhar_seguindo_rabo'
    assert a.modo == 'seguranca' and g.segura(acao)
    g.passo(acao)
    assert a.alinhado(g.corpo)
    antes = list(g.corpo)
    acao = a.escolher(g)
    assert a.passo_ordenado(antes, g.destino(acao)[0], g.comida)


@pytest.mark.parametrize('nivel', (15, 25))
def test_comida_omitida_nao_e_consumida_sem_saida(nivel):
    g, a = jogo_no_ciclo(nivel)
    indice = a.ordem[(nivel - 2, 0)]
    g.corpo = [a.ciclo[(indice - i) % len(a.ciclo)]
               for i in range(g.nivel.meta // 2)]
    g.direcao = 0
    g.comida = (nivel - 1, 0)
    # A outra saída da casa omitida está ocupada pelo corpo, longe do rabo.
    acao = a.escolher(g)
    assert g.segura(acao) and g.destino(acao)[0] != g.comida
    assert a.modo == 'seguranca'
