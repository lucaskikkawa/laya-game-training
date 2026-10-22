"""Executa os blocos Python do instalador sem rede, Windows ou GPU."""
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import pytest

SCRIPT = (Path(__file__).resolve().parents[1] / "scripts" / "instalar.ps1").read_text(encoding="utf-8-sig")


def bloco(nome):
    return re.search(rf"\${nome} = @'\n(.*?)\n'@", SCRIPT, re.S)[1]


def test_download_snapshot_local_com_caminho_especial(tmp_path, monkeypatch):
    destino = tmp_path / "Lucas d'Ávila com espaços"
    monkeypatch.setenv("LAYA_HOME", str(destino))
    chamadas = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(
        snapshot_download=lambda **kw: chamadas.append(kw)))
    # Reexecutar usa a mesma pasta, sem criar destinos novos nem baixar variantes.
    exec(bloco("Download"), {})
    exec(bloco("Download"), {})
    assert chamadas[0] == chamadas[1]
    assert chamadas[0]["repo_id"] == "convaiinnovations/laya"
    assert chamadas[0]["local_dir"] == str(destino / "modelos" / "laya_v000")
    assert set(chamadas[0]["allow_patterns"]) == {
        "rl_agent_config.json", "model.safetensors", "encoder/*", "tokenizer/*"}


@pytest.mark.parametrize("disponivel", [True, False])
def test_checagem_cuda_executa_na_gpu_ou_informa_cpu(monkeypatch, capsys, disponivel):
    alocacoes = []
    cuda = SimpleNamespace(is_available=lambda: disponivel,
        get_device_name=lambda i: "GTX 1650",
        get_device_properties=lambda i: SimpleNamespace(total_memory=4 * 2**30),
        synchronize=lambda: alocacoes.append("sincronizada"))
    torch = SimpleNamespace(__version__="2.14.1+cu126", version=SimpleNamespace(cuda="12.6"),
        cuda=cuda, zeros=lambda n, device: alocacoes.append(device))
    monkeypatch.setitem(sys.modules, "torch", torch)
    exec(bloco("Verificar"), {})
    saida = capsys.readouterr().out
    if disponivel:
        assert alocacoes == ["cuda", "sincronizada"] and "GTX 1650" in saida
    else:
        assert not alocacoes and "CUDA indisponível" in saida


def test_rejeita_torch_sem_cuda126(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        __version__="2.14.1", version=SimpleNamespace(cuda=None)))
    with pytest.raises(SystemExit, match="Torch sem CUDA 12.6"):
        exec(bloco("Verificar"), {})


def test_venv_de_outra_versao_tem_erro_claro(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validar.py", "0.0"])
    with pytest.raises(SystemExit, match="venv existente usa outra versão"):
        exec(bloco("ValidarPython"), {})
