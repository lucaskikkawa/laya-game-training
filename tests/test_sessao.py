import gzip
import json
from nucleo.contratos import Decisao
from jogos.snake.sessao import Sessao


def ler_run(pasta, nome):
    dados = json.loads((pasta / nome).read_text(encoding="utf-8"))
    if isinstance(dados.get("passos"), str):
        with gzip.open(pasta / dados["passos"], "rt", encoding="utf-8") as arquivo:
            dados["passos"] = [json.loads(linha) for linha in arquivo]
    return dados


class MockLaya:
    def decidir(self, estado, opcoes):
        return Decisao({"straight": .8, "left": .1, "right": .1}, "straight", .7, 2.5)


def executar(s):
    s.iniciar_run()
    while not s.jogo.fim:
        s.passo()
    return s.finalizar_run()


def test_runs_json_pareados_e_comparacao(tmp_path):
    # O algoritmo vence rapidamente com todas as recompensas na mesma região;
    # o modelo mockado segue reto e morre na parede.
    comidas = [(x, y) for y in range(15) for x in range(15)] * 20
    s = Sessao(MockLaya(), comidas=comidas, pasta=tmp_path, partidas=2)
    resultado = executar(s)
    assert resultado["comparacao"]["geral"]["laya"]["morte"] == "parede"
    documento = json.loads((s.pasta / "sessao.json").read_text())
    assert documento["comidas"] == [list(p) for p in comidas]
    run = ler_run(s.pasta, "run_0001_laya.json")
    algo = ler_run(s.pasta, "run_0001_algoritmo.json")
    assert run["inicio_lista"] == algo["inicio_lista"] == 0
    assert run["passos"][0]["corpo"] == algo["passos"][0]["corpo"]
    assert run["passos"][0]["latencia_ms"] == 2.5
    assert run["passos"][0]["jogada_ideal"] in ("straight", "left", "right")
    assert run["passos_por_segundo"] > 0
    assert s.cursor > 0
    executar(s)
    assert s.concluida and s.nivel == 15
    assert json.loads((s.pasta / "sessao.json").read_text())["status"] == "concluida"
    assert not list(s.pasta.glob("*.jsonl"))
    assert not list(s.pasta.glob("*.tmp"))


def test_pastas_nao_sobrescrevem_e_interrupcao(tmp_path):
    s = Sessao(MockLaya(), pasta=tmp_path)
    outra = Sessao(MockLaya(), pasta=tmp_path)
    assert s.pasta != outra.pasta
    s.iniciar_run()
    s.passo()
    s.interromper("teste")
    assert (s.pasta / "run_0001_laya_parcial.json").is_file()
    assert json.loads((s.pasta / "sessao.json").read_text())["status"] == "erro"


def test_interrupcao_nao_apaga_erro(tmp_path):
    s = Sessao(MockLaya(), pasta=tmp_path)
    s.iniciar_run()
    s.passo()
    s.interromper("inferência indisponível")
    s.interromper()
    dados = json.loads((s.pasta / "sessao.json").read_text())
    assert dados["status"] == "erro" and dados["erro"] == "inferência indisponível"


def test_resultado_interrompido_nao_duplica_run(tmp_path):
    import pytest
    s = Sessao(MockLaya(), pasta=tmp_path, partidas=2)
    executar(s)
    with pytest.raises(RuntimeError):
        s.finalizar_run()
    s.interromper()
    assert not (s.pasta / "run_0002_laya_parcial.json").exists()


def test_conteudo_completo_placar_e_comparacao(tmp_path):
    comidas = [(x, y) for y in range(15) for x in range(15)] * 20
    s = Sessao(MockLaya(), pasta=tmp_path, comidas=comidas)
    executar(s)
    ler = lambda nome: ler_run(s.pasta, nome)
    run = ler("run_0001_laya.json")
    algo = ler("run_0001_algoritmo.json")
    comparacao = ler("run_0001_comparacao.json")
    for registro in run["passos"]:
        assert registro["cabeca"] == registro["corpo"][0]
        assert registro["probabilidades"] == {"straight": .8, "left": .1, "right": .1}
        assert registro["escolha"] == "straight" and registro["confianca"] == .7
        assert registro["jogada_ideal"] in registro["probabilidades"]
        assert registro["latencia_ms"] == 2.5
    assert comparacao["geral"]["laya"] == run["resumo"]
    assert comparacao["geral"]["algoritmo"] == algo["resumo"]
    assert comparacao["passo_a_passo"] == {
        "laya": "run_0001_laya.jsonl.gz", "algoritmo": "run_0001_algoritmo.jsonl.gz"}
    assert all(r["concorda"] == (r["escolha"] == r["jogada_ideal"]) for r in run["passos"])
    placar = ler(s.documento["placar"] + ".json")
    assert placar["nome"].startswith("Laya_") and len(placar["runs"]) == 1
    assert placar["runs"][0]["pontos"] == run["resumo"]["pontos"]
    assert placar["runs"][0]["passos"] == run["resumo"]["passos"]
    assert placar["runs"][0]["morte"] == run["resumo"]["morte"]


def test_comparacao_divergencia_e_prefixo():
    from jogos.snake.sessao import comparar
    resumo = {"pontos": 0, "passos": 0}
    a = [{"indice": 3, "posicao": (0, 0)}, {"indice": 4, "posicao": (1, 0)}]
    b = [a[0], {"indice": 5, "posicao": (2, 0)}]
    pulo = {"indice": 4, "posicao": (1, 0), "motivo": "ocupada", "passo": 12}
    c = comparar([], resumo, resumo, comidas_laya=a, comidas_algoritmo=b,
                 pulos_algoritmo=[pulo])
    assert c["divergencia_comidas"] == 1 and "índice 1" in c["aviso"]
    assert c["pulos"] == {"laya": [], "algoritmo": [pulo]}
    assert comparar([], resumo, resumo, comidas_laya=a, comidas_algoritmo=a)["aviso"] is None
    assert comparar([], resumo, resumo, comidas_laya=a, comidas_algoritmo=a[:1])["divergencia_comidas"] == 1


def test_auditoria_runs_indices_absolutos(tmp_path):
    comidas = [(7, 7), (6, 7), (8, 7)] + [(x, y) for y in range(15) for x in range(15)] * 20
    s = Sessao(MockLaya(), pasta=tmp_path, comidas=comidas)
    s.cursor = 1
    executar(s)
    ler = lambda nome: ler_run(s.pasta, nome)
    laya = ler("run_0001_laya.json")
    algoritmo = ler("run_0001_algoritmo.json")
    comparacao = ler("run_0001_comparacao.json")
    for nome, run in (("laya", laya), ("algoritmo", algoritmo)):
        assert run["pulos"][0] == {"indice": 1, "posicao": [6, 7], "motivo": "ocupada", "passo": 0, "area_alcancavel": 222}
        assert comparacao["pulos"][nome] == run["pulos"]
        assert comparacao["comidas_efetivas"][nome] == run["comidas_efetivas"]
    assert comparacao["aviso"] and comparacao["divergencia_comidas"] is not None


def test_interrupcao_antes_do_primeiro_movimento_preserva_pulos(tmp_path):
    s = Sessao(MockLaya(), pasta=tmp_path, comidas=[(7, 7), (8, 7)])
    s.iniciar_run()
    s.interromper()
    parcial = ler_run(s.pasta, "run_0001_laya_parcial.json")
    assert parcial["passos"] == []
    assert parcial["pulos"] == [
        {"indice": 0, "posicao": [7, 7], "motivo": "ocupada", "passo": 0, "area_alcancavel": 222}]


def test_arquivo_preserva_pulo_inalcancavel_e_passo(tmp_path):
    from jogos.snake.regras import Nivel
    s = Sessao(MockLaya(), pasta=tmp_path, comidas=[(8, 7)])
    g = s.iniciar_run()
    g.corpo = [(0, 0), (1, 0), (1, 1), (0, 1)]
    g.nivel = Nivel(15, 50, 2)
    g.comidas = [(0, 1), (0, 3), (0, 2)]
    g.indice_comida = 0
    g.passos = 17
    g._nova_comida()
    s.interromper()
    parcial = ler_run(s.pasta, "run_0001_laya_parcial.json")
    assert parcial["pulos"] == [
        {"indice": 0, "posicao": [0, 1], "motivo": "ocupada", "passo": 17, "area_alcancavel": 0},
        {"indice": 1, "posicao": [0, 3], "motivo": "inalcancavel", "passo": 17, "area_alcancavel": 0}]


def test_derrota_algoritmo_invalida_sessao_e_vitoria_posterior_nao_reabilita(tmp_path, monkeypatch):
    from jogos.snake.algoritmo import Algoritmo
    from jogos.snake.regras import NIVEIS, Nivel
    from treino.selecao import selecionar_sessoes
    monkeypatch.setitem(NIVEIS, 15, Nivel(15, 4, 60))
    escolher = Algoritmo.escolher
    # Primeira run: algoritmo vai à parede; segunda: come e alcança a meta.
    monkeypatch.setattr(Algoritmo, 'escolher', lambda self, jogo: 'straight')
    s = Sessao(MockLaya(), pasta=tmp_path, comidas=[(0, 0), (8, 7)], partidas=2)
    assert s.documento['valida_para_treino'] is True
    assert s.documento['motivo'] is None
    primeira = executar(s)
    assert not primeira['comparacao']['geral']['algoritmo']['vitoria']
    dados = json.loads((s.pasta / 'sessao.json').read_text())
    assert dados['valida_para_treino'] is False and dados['motivo'] == 'algoritmo_perdeu'
    monkeypatch.setattr(Algoritmo, 'escolher', escolher)
    segunda = executar(s)
    assert segunda['comparacao']['geral']['algoritmo']['vitoria']
    dados = json.loads((s.pasta / 'sessao.json').read_text())
    assert dados['status'] == 'concluida'
    assert dados['valida_para_treino'] is False and dados['motivo'] == 'algoritmo_perdeu'
    assert segunda['comparacao']['valida_para_treino'] is False
    assert selecionar_sessoes(tmp_path) == []


def test_vitoria_algoritmo_mantem_sessao_valida(tmp_path, monkeypatch):
    from jogos.snake.regras import NIVEIS, Nivel
    from treino.selecao import selecionar_sessoes
    monkeypatch.setitem(NIVEIS, 15, Nivel(15, 4, 60))
    s = Sessao(MockLaya(), pasta=tmp_path, comidas=[(8, 7)])
    executar(s)
    dados = json.loads((s.pasta / 'sessao.json').read_text())
    assert dados['valida_para_treino'] is True and dados['motivo'] is None
    assert selecionar_sessoes(tmp_path) == [s.pasta / 'sessao.json']


def test_jsonl_gzip_metricas_metadados_e_snapshot_reconstituivel(tmp_path, monkeypatch):
    from jogos.snake.regras import NIVEIS, Nivel, Jogo, metricas_espaco
    monkeypatch.setitem(NIVEIS, 15, Nivel(15, 4, 60))
    s = Sessao(MockLaya(), pasta=tmp_path, comidas=[(7, 7), (8, 7)], versao='v012')
    executar(s)
    for agente in ('laya', 'algoritmo'):
        nome = f'run_0001_{agente}'
        dados = json.loads((s.pasta / (nome + '.json')).read_text())
        assert dados['passos'] == nome + '.jsonl.gz'
        assert dados['nivel'] == 15 and dados['versao_laya'] == 'v012'
        assert dados['arquivo_comidas'] == 'comidas.json'
        assert {'commit_codigo', 'versao_pacote_laya'} <= dados.keys()
        assert dados['motivo_termino'] == 'vitoria'
        assert dados['snapshot_final']['passo'] == dados['resumo']['passos'] == 1
        assert len(dados['snapshot_final']['corpo']) == 4
        assert len(dados['snapshot_final']['estado'].splitlines()[3:]) == 15
        with gzip.open(s.pasta / dados['passos'], 'rt') as f:
            linhas = [json.loads(linha) for linha in f]
        assert len(linhas) == 1
        r = linhas[0]
        assert r['passo'] == 1 and r['cabeca'] == r['corpo'][0] == [7, 7]
        assert r['comida'] == [8, 7] and r['indice_comida'] == 1
        assert r['direcao'] == 1 and r['passos_sem_comer'] == 0 and r['restante_limite'] == 60
        assert r['escolha'] == 'straight' and r['estrategia'] and r['motivo']
        corpo = [tuple(p) for p in r['corpo']]
        assert all(r[k] == v for k,v in metricas_espaco(corpo, 15, (8, 7)).items())
        g = Jogo(15, [(8, 7)])
        g.corpo = corpo
        g.direcao = r['direcao']
        g.passo(r['escolha'])
        assert [list(p) for p in g.corpo] == dados['snapshot_final']['corpo']
        campos_modelo = {'probabilidades', 'confianca', 'jogada_ideal', 'concorda'}
        assert campos_modelo <= r.keys() if agente == 'laya' else not campos_modelo & r.keys()


def test_metadados_toleram_git_e_laya_ausentes(monkeypatch):
    import subprocess
    from importlib.metadata import PackageNotFoundError
    from jogos.snake import sessao
    def falhar(*args, **kwargs):
        raise subprocess.CalledProcessError(128, 'git')
    monkeypatch.setattr(sessao.subprocess, 'run', falhar)
    assert sessao.commit_codigo() is None
    def ausente(*args):
        raise PackageNotFoundError('laya')
    monkeypatch.setattr(sessao, 'version', ausente)
    assert sessao.versao_pacote_laya() is None


def test_terminos_padronizados_e_falha_invalida_treino(tmp_path):
    from jogos.snake.sessao import termino
    from jogos.snake.regras import Jogo
    g = Jogo(15, [(8, 7)])
    for morte, esperado in [('corpo', 'corpo'), ('parede', 'parede'),
                            ('limite_sem_comer', 'fome'), ('lista_esgotada', 'lista_esgotada'),
                            ('sem_comida_valida', 'sem_comida_valida')]:
        g.morte = morte
        assert termino(g) == esperado
    s = Sessao(MockLaya(), pasta=tmp_path, comidas=[])
    executar(s)
    assert s.documento['valida_para_treino'] is False
    assert s.documento['motivo'] == 'algoritmo_perdeu'
    for agente in ('laya', 'algoritmo'):
        dados = ler_run(s.pasta, f'run_0001_{agente}.json')
        assert dados['motivo_termino'] == 'lista_esgotada' and dados['passos'] == []


def test_reconstroi_runs_inteiras_e_metricas_sem_consultar_o_algoritmo(tmp_path):
    from jogos.snake.regras import Jogo, caminho_bfs

    comidas = [(7, 7), (8, 7), (9, 7), (0, 0)]
    s = Sessao(MockLaya(), pasta=tmp_path, comidas=comidas)
    executar(s)
    for agente in ('laya', 'algoritmo'):
        dados = ler_run(s.pasta, f'run_0001_{agente}.json')
        replay = Jogo(15, comidas)
        for passo, r in enumerate(dados['passos'], 1):
            assert not replay.fim
            assert r['passo'] == passo
            assert r['corpo'] == [list(p) for p in replay.corpo]
            assert r['cabeca'] == list(replay.corpo[0])
            assert r['direcao'] == replay.direcao
            assert r['comida'] == list(replay.comida)
            assert r['indice_comida'] == replay.indice_comida - 1
            assert r['passos_sem_comer'] == replay.sem_comer
            assert r['restante_limite'] == replay.nivel.limite - replay.sem_comer
            livres = {(x, y) for y in range(15) for x in range(15)} - set(replay.corpo)
            assert r['area_alcancavel'] == sum(
                caminho_bfs(replay.corpo[0], p, replay.corpo[1:], 15) is not None for p in livres)
            rota = caminho_bfs(replay.corpo[0], replay.comida, replay.corpo[1:], 15)
            assert r['distancia_bfs_comida'] == (len(rota) if rota is not None else None)
            assert r['rabo_alcancavel'] == (caminho_bfs(
                replay.corpo[0], replay.corpo[-1], replay.corpo[1:-1], 15) is not None)
            assert r['estrategia'] and r['motivo']
            assert r['pontos_ganhos'] == replay.passo(r['escolha'])
            assert r['pontos'] == replay.pontos
        assert replay.fim
        assert dados['resumo'] == replay.resumo()
        assert dados['snapshot_final']['estado'] == replay.estado()
        assert dados['snapshot_final']['corpo'] == [list(p) for p in replay.corpo]
        assert dados['snapshot_final']['comida'] == (list(replay.comida) if replay.comida else None)
        assert dados['snapshot_final']['indice_comida'] == (
            replay.indice_comida - 1 if replay.comida else None)
        assert dados['comidas_efetivas'] == json.loads(json.dumps(replay.comidas_efetivas))
        assert dados['pulos'] == json.loads(json.dumps(replay.pulos))


def test_erro_laya_ou_oraculo_fecha_gzip_e_salva_parcial(tmp_path, monkeypatch):
    import pytest

    for origem in ('laya', 'oraculo'):
        for passos in (0, 1):
            s = Sessao(MockLaya(), pasta=tmp_path, comidas=[(0, 0)])
            s.iniciar_run()
            if passos:
                s.passo()
            arquivo = s._arquivo_laya

            def falhar(*args):
                raise RuntimeError('decisão indisponível')

            with monkeypatch.context() as patch:
                if origem == 'laya':
                    patch.setattr(s.decisor, 'decidir', falhar)
                else:
                    patch.setattr(s._oraculo, 'escolher', falhar)
                with pytest.raises(RuntimeError, match='decisão indisponível'):
                    s.passo()
            assert arquivo.closed
            parcial = ler_run(s.pasta, 'run_0001_laya_parcial.json')
            assert parcial['motivo_termino'] == 'erro'
            assert parcial['erro'] == 'RuntimeError: decisão indisponível'
            assert parcial['snapshot_final']['passo'] == parcial['resumo']['passos'] == passos
            assert len(parcial['passos']) == passos
            assert s.documento['status'] == 'erro'
            s.interromper()  # A GUI pode notificar a mesma interrupção novamente.
            assert ler_run(s.pasta, 'run_0001_laya_parcial.json') == parcial
            with pytest.raises(RuntimeError, match='Inicie uma run'):
                s.passo()


def test_erro_algoritmo_preserva_run_laya_concluida_e_passos_validos(tmp_path, monkeypatch):
    import pytest
    from jogos.snake.algoritmo import Algoritmo

    for passos in (0, 1):
        s = Sessao(MockLaya(), pasta=tmp_path, comidas=[(0, 0)])
        s.iniciar_run()
        while not s.jogo.fim:
            s.passo()

        def falhar(self, jogo):
            if jogo.passos == passos:
                raise RuntimeError('gabarito indisponível')
            return 'straight'

        with monkeypatch.context() as patch:
            patch.setattr(Algoritmo, 'escolher', falhar)
            with pytest.raises(RuntimeError, match='gabarito indisponível') as exc:
                s.finalizar_run()
        s.interromper(exc.value)
        algoritmo = ler_run(s.pasta, 'run_0001_algoritmo.json')
        assert algoritmo['motivo_termino'] == algoritmo['status'] == 'erro'
        assert algoritmo['erro'] == 'RuntimeError: gabarito indisponível'
        assert len(algoritmo['passos']) == algoritmo['resumo']['passos'] == passos
        assert algoritmo['snapshot_final']['passo'] == passos
        assert algoritmo['snapshot_final']['estado']
        laya = ler_run(s.pasta, 'run_0001_laya.json')
        assert laya['motivo_termino'] == 'parede' and laya['status'] == 'concluida'
        assert not (s.pasta / 'run_0001_laya_parcial.json').exists()
        assert s.documento['status'] == 'erro'
        assert not s.documento['valida_para_treino']
        assert s.documento['motivo'] == 'algoritmo_perdeu'


def test_terminos_reais_persistidos_nas_duas_runs(tmp_path, monkeypatch):
    from jogos.snake import sessao
    from jogos.snake.regras import Jogo

    for motivo in ('corpo', 'parede', 'fome', 'lista_esgotada', 'sem_comida_valida'):
        def preparar(*args):
            g = Jogo(15, [] if motivo == 'lista_esgotada' else [(0, 0)])
            if motivo == 'corpo':
                g.corpo = [(7, 7), (7, 6), (8, 6), (8, 7), (9, 7)]
            elif motivo == 'fome':
                g.sem_comer = g.nivel.limite - 1
            elif motivo == 'sem_comida_valida':
                g.corpo = [(x, y) for y in range(8)
                           for x in (range(15) if y % 2 == 0 else range(14, -1, -1))]
                g._nova_comida()
            return g

        with monkeypatch.context() as patch:
            patch.setattr(sessao, 'Jogo', preparar)
            patch.setattr(sessao.Algoritmo, 'escolher', lambda self, jogo: 'straight')
            s = Sessao(MockLaya(), pasta=tmp_path, comidas=[(0, 0)])
            executar(s)
        for agente in ('laya', 'algoritmo'):
            run = ler_run(s.pasta, f'run_0001_{agente}.json')
            assert run['motivo_termino'] == motivo
            assert run['snapshot_final']['passo'] == len(run['passos']) == run['resumo']['passos']
            assert run['snapshot_final']['estado']
            assert run['snapshot_final']['cabeca'] == run['snapshot_final']['corpo'][0]
            if motivo == 'fome':
                assert run['snapshot_final']['restante_limite'] == 0
                assert run['resumo']['morte'] == 'limite_sem_comer'
            if motivo in ('sem_comida_valida', 'lista_esgotada'):
                assert run['snapshot_final']['comida'] is None
                assert run['snapshot_final']['indice_comida'] is None


def test_sem_comida_valida_apos_comer_persistido_nas_duas_runs(
        tmp_path, monkeypatch, preparar_comida_sem_saida):
    from jogos.snake import sessao

    monkeypatch.setattr(sessao, "Jogo", lambda nivel, comidas: preparar_comida_sem_saida(comidas))
    monkeypatch.setattr(sessao.Algoritmo, "escolher", lambda self, jogo: "straight")
    inicio = 7
    comidas = [(24, 24)] * inicio + [(1, 0), (0, 0)] + [(24, 24)] * 20000
    s = Sessao(MockLaya(), nivel=25, pasta=tmp_path, comidas=comidas)
    s.cursor = inicio
    executar(s)

    for agente in ("laya", "algoritmo"):
        run = ler_run(s.pasta, f"run_0001_{agente}.json")
        assert run["motivo_termino"] == run["resumo"]["morte"] == "sem_comida_valida"
        assert run["status"] == "concluida" and not run["resumo"]["vitoria"]
        assert run["resumo"]["passos"] == run["snapshot_final"]["passo"] == 1
        assert run["resumo"]["comidas"] == 1 and run["resumo"]["pontos"] == 100
        assert run["snapshot_final"]["comida"] is None
        assert run["snapshot_final"]["indice_comida"] is None
        assert run["snapshot_final"]["cabeca"] == [0, 0]
        assert run["pulos"] == [{"indice": inicio, "posicao": [1, 0],
                                 "motivo": "ocupada", "passo": 0, "area_alcancavel": 47}]
        assert run["comidas_efetivas"] == [
            {"indice": inicio + 1, "posicao": [0, 0], "passo": 0}]
        assert len(run["passos"]) == 1
        assert run["passos"][0]["indice_comida"] == inicio + 1
        assert run["passos"][0]["pontos_ganhos"] == 100
    assert s.cursor == inicio + 2
    assert not s.documento["valida_para_treino"]


def test_bfs_nulo_e_escape_pelo_rabo_persistidos(tmp_path, monkeypatch):
    from jogos.snake import sessao
    from jogos.snake.regras import Jogo

    def preparar(*args):
        g = Jogo(15, [(0, 2)])
        g.corpo = [(0, 0), (1, 0), (1, 1), (0, 1)]
        g.direcao = 2
        g.indice_comida = 0
        g.comidas_efetivas.clear()
        g._nova_comida()
        assert g.ideal_comida is None
        return g

    with monkeypatch.context() as patch:
        patch.setattr(sessao, 'Jogo', preparar)
        patch.setattr(sessao.Algoritmo, 'escolher', lambda self, jogo: 'straight')
        s = Sessao(MockLaya(), pasta=tmp_path, comidas=[(0, 2)])
        executar(s)
    for agente in ('laya', 'algoritmo'):
        run = ler_run(s.pasta, f'run_0001_{agente}.json')
        r = run['passos'][0]
        assert r['distancia_bfs_comida'] is None
        assert r['ideal_bfs_ao_aparecer'] is None
        assert r['area_alcancavel'] == 0 and r['rabo_alcancavel'] is True
        assert run['resumo']['pontos'] == 100
        assert run['motivo_termino'] == 'lista_esgotada'
