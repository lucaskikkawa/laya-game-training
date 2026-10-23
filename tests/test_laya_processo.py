import json
import os
from pathlib import Path
import threading
import time
from concurrent.futures import CancelledError

import pytest

from nucleo import laya_processo
from jogos.snake.__main__ import argumentos
from jogos.snake.gui import Aplicativo
from jogos.snake.regras import OPCOES
from test_sessao import MockLaya


class ModeloTeste(MockLaya):
    def __init__(self, versao, cpu):
        self.cpu = cpu

    def carregar(self):
        import sys
        assert threading.current_thread() is threading.main_thread()
        assert "pygame" not in sys.modules or not sys.modules["pygame"].get_init()

    def telemetria(self):
        return {"dispositivo": "cpu", "pid": os.getpid()}


def servir_modelo_teste(conexao, versao, cpu):
    laya_processo.Laya = ModeloTeste
    laya_processo._servir(conexao, versao, cpu)


def servir_carga_pendente(conexao, versao, cpu):
    conexao.recv()
    Path(versao).write_text(str(os.getpid()))
    # Simula download/import bloqueado, sem sleep nem acesso à rede.
    conexao.recv()


def servir_falha_nativa(conexao, versao, cpu):
    conexao.recv()
    os._exit(42)


def servir_inferencia_pendente(conexao, versao, cpu):
    conexao.recv()
    conexao.send((True, None, {"dispositivo": "cpu"}))
    servir_carga_pendente(conexao, versao, cpu)


def test_modelo_isolado_na_thread_principal(monkeypatch):
    monkeypatch.setattr(laya_processo, "_servir", servir_modelo_teste)
    decisor = laya_processo.LayaProcesso(cpu=True)
    try:
        decisor.carregar()
        assert decisor.telemetria()["pid"] != os.getpid()
        assert decisor.decidir("mapa", OPCOES).escolha in {o.id for o in OPCOES}
    finally:
        decisor.fechar()
    assert not decisor._processo.is_alive()
    with pytest.raises(CancelledError, match="encerrado"):
        decisor.carregar()


@pytest.mark.parametrize("alvo", [servir_carga_pendente, servir_inferencia_pendente])
def test_fechar_gui_durante_operacao_pendente(tmp_path, monkeypatch, alvo):
    import pygame
    monkeypatch.setattr(laya_processo, "_servir", alvo)
    marcador = tmp_path / "carga-iniciada"
    app = Aplicativo(argumentos(["--cpu", "--modo", "rapido"]), pasta_runs=tmp_path)
    app.versao = str(marcador)
    try:
        app.iniciar()
        prazo = time.monotonic() + 10
        while not marcador.exists() and time.monotonic() < prazo:
            app.atualizar(.016)
            time.sleep(.01)
        assert marcador.exists(), "O subprocesso não iniciou a carga"
        futuro = app.futuro
        assert not futuro.done()
        inicio = time.monotonic()
        app.fechar()
        assert time.monotonic() - inicio < 3
        app.fechar()
        app.atualizar(.016)
        assert futuro.done()
        assert not pygame.get_init()
        assert not app.sessao.decisor._processo.is_alive()
        if alvo is servir_inferencia_pendente:
            assert (app.sessao.pasta / "run_0001_laya_parcial.json").exists()
        else:
            assert not app.jogo
        documento = json.loads((app.sessao.pasta / "sessao.json").read_text())
        assert documento["status"] == "interrompida"
    finally:
        app.fechar()


def test_falha_nativa_vira_erro_python(monkeypatch):
    monkeypatch.setattr(laya_processo, "_servir", servir_falha_nativa)
    decisor = laya_processo.LayaProcesso(cpu=True)
    try:
        with pytest.raises(RuntimeError, match="encerrado durante"):
            decisor.carregar()
    finally:
        decisor.fechar()
