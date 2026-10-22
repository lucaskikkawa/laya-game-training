from types import SimpleNamespace
import sys
import pytest
from nucleo.laya import Laya
from nucleo.config import modelo, versoes
from jogos.snake.regras import OPCOES


def test_lazy_sem_dependencias():
    antes = set(sys.modules)
    Laya()
    assert not ({"torch", "laya"} & (set(sys.modules) - antes))


def test_config(tmp_path, monkeypatch):
    monkeypatch.setenv("LAYA_HOME", str(tmp_path))
    assert modelo("v000") == "convaiinnovations/laya"
    pasta = tmp_path / "modelos" / "laya_v001"
    pasta.mkdir(parents=True)
    assert versoes() == ["v000", "v001"]
    assert modelo("v001") == str(pasta)
    with pytest.raises(ValueError):
        modelo("../../oops")
    with pytest.raises(FileNotFoundError):
        modelo("v002")


@pytest.mark.parametrize("cuda,force_cpu", [(True, False), (False, False), (True, True)])
def test_api_choice_e_dispositivo(monkeypatch, cuda, force_cpu):
    chamadas = []
    def system_one(state, questions, lang):
        chamadas.append((state, questions, lang))
        return {"answers": {"move": {"probabilities": {"straight": .8, "left": .1, "right": .1},
                                       "choice": "straight", "confidence": .72}}}
    agente = SimpleNamespace(system_one=system_one, dtype="fp32")
    def load(model, device):
        chamadas.append((model, device))
        agente.device = device
        return agente
    fake_cuda = SimpleNamespace(is_available=lambda: cuda, get_device_name=lambda d: "GPU teste")
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=fake_cuda, float16="fp16"))
    monkeypatch.setitem(sys.modules, "laya", SimpleNamespace(load=load))
    laya = Laya(cpu=force_cpu)
    d = laya.decidir("state", OPCOES)
    assert chamadas[0][1] == ("cuda" if cuda and not force_cpu else "cpu")
    assert chamadas[1][1]["move"]["type"] == "choice"
    assert len(chamadas[1][1]) == 1 and len(chamadas[1][1]["move"]["criteria"]) == 3
    assert chamadas[1][2] == "en"
    assert d.escolha == "straight" and sum(d.probabilidades.values()) == 1
    assert d.confianca == .72 and d.latencia_ms >= 0
    laya.decidir("state2", OPCOES)
    assert len([c for c in chamadas if len(c) == 2]) == 1
    if cuda and not force_cpu:
        assert agente.dtype == "fp16" and agente.amp_enabled


@pytest.mark.parametrize("alteracao,erro", [
    ({"usage": {"truncated": True}}, RuntimeError),
    ({"probabilities": {"straight": float("nan"), "left": .1, "right": .1}}, ValueError),
    ({"choice": "up"}, ValueError), ({"confidence": 1.5}, ValueError),
])
def test_respostas_invalidas_ou_truncadas(alteracao, erro):
    resposta = {"answers": {"move": {"probabilities": {"straight": .8, "left": .1, "right": .1},
                                      "choice": "straight", "confidence": .7}}}
    if "usage" in alteracao:
        resposta.update(alteracao)
    else:
        resposta["answers"]["move"].update(alteracao)
    laya = Laya()
    laya.agent = SimpleNamespace(system_one=lambda *a, **kw: resposta)
    with pytest.raises(erro):
        laya.decidir("state", OPCOES)
