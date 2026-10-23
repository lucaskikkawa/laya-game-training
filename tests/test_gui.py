import time
import pygame
from jogos.snake.__main__ import argumentos
from jogos.snake.gui import Aplicativo
from test_sessao import MockLaya


def test_cli_padroes():
    assert argumentos([]).passos_por_segundo == 1
    assert argumentos(["--modo", "rapido"]).passos_por_segundo == 5
    assert argumentos(["--cpu", "--partidas", "3"]).cpu


def test_gui_selecao_e_frames(tmp_path):
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    app.executar(max_frames=5)


def test_gui_run_mockada_e_controles(tmp_path):
    app = Aplicativo(argumentos(["--passos-por-segundo", "1000"]), MockLaya(), tmp_path)
    try:
        app.desenhar()
        app.acionar("start")
        prazo = time.perf_counter() + 20
        while app.estado not in ("resultado", "erro") and time.perf_counter() < prazo:
            app.atualizar(.016)
            app.desenhar()
            time.sleep(.001)
        assert app.estado == "resultado", app.erro
        assert app.sessao.concluida
        app.evento(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, unicode="\t"))
        assert not app.painel
        app.acionar("selecao")
        app.acionar("nivel")
        assert app.nivel == 20
    finally:
        app.fechar()


def test_cli_rejeita_velocidade_invalida():
    import pytest
    for valor in ("0", "-1", "nan", "inf"):
        with pytest.raises(SystemExit):
            argumentos(["--passos-por-segundo", valor])


def test_gui_modo_rapido_sem_tabuleiro(tmp_path):
    app = Aplicativo(argumentos(["--modo", "rapido", "--partidas", "2", "--passos-por-segundo", "1000"]), MockLaya(), tmp_path)
    app.desenhar_tabuleiro = lambda: (_ for _ in ()).throw(AssertionError("Modo rápido não deve desenhar tabuleiro"))
    app.desenhar_painel = lambda: (_ for _ in ()).throw(AssertionError("Modo rápido não deve desenhar painel"))
    try:
        app.iniciar()
        prazo = time.perf_counter() + 20
        while not (app.estado == "resultado" and app.sessao.concluida) and time.perf_counter() < prazo:
            app.atualizar(.016)
            app.desenhar()
            time.sleep(.001)
        assert app.estado == "resultado" and app.sessao.concluida, app.erro
        assert app.sessao.indice == 2 and len(app.sessao.resultados) == 2
    finally:
        app.fechar()


def test_normal_120_frames_redimensiona_e_alterna_painel(tmp_path, monkeypatch):
    app = Aplicativo(argumentos(["--modo", "normal", "--nivel", "15"]), MockLaya(), tmp_path)
    atualizar = app.atualizar
    frames = []
    tamanhos = []
    def frame(dt):
        if len(frames) == 30:
            pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE, w=960, h=640))
        if len(frames) == 60:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, unicode="\t"))
        atualizar(dt)
        frames.append(app.estado)
        tamanhos.append(app.tela.get_size())
    monkeypatch.setattr(app, "atualizar", frame)
    app.acionar("start")
    app.executar(max_frames=120)
    assert len(frames) == 120 and frames.count("jogando") >= 110
    assert app.jogo.passos >= 1 and not app.erro
    assert tamanhos[-1] == (960, 640)
    assert not app.painel


def test_cli_e_menu_excluem_nivel_adiado(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        argumentos(['--nivel', '30'])
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        niveis = []
        for _ in range(4):
            niveis.append(app.nivel)
            app.acionar('nivel')
        assert niveis == [15, 20, 25, 15]
    finally:
        app.fechar()


def test_resultado_avisa_exclusao_do_treino(tmp_path):
    from types import SimpleNamespace
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        app.sessao = SimpleNamespace(
            documento={'valida_para_treino': False}, resultados=[], registros=[],
            indice=1, concluida=True, pasta=tmp_path, decisor=MockLaya())
        textos = []
        app.texto = lambda texto, *args, **kwargs: textos.append(texto)
        app.desenhar_resultado()
        assert any('Sessão excluída do treino' in t for t in textos)
    finally:
        app.fechar()
