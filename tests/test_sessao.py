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
