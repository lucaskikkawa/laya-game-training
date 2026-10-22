import json
from nucleo.contratos import Decisao
from jogos.snake.sessao import Sessao


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
    run = json.loads((s.pasta / "run_0001_laya.json").read_text())
    algo = json.loads((s.pasta / "run_0001_algoritmo.json").read_text())
    assert run["inicio_lista"] == algo["inicio_lista"] == 0
    assert run["passos"][0]["estado"] == algo["passos"][0]["estado"]
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
