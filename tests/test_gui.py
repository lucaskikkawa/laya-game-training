import time
import pygame
from jogos.snake.__main__ import argumentos
from jogos.snake.gui import Aplicativo
from test_sessao import MockLaya


def test_cli_padroes():
    assert argumentos([]).partidas == 1
    assert not argumentos([]).auto_iniciar
    assert argumentos(["--partidas", "1"]).auto_iniciar
    assert argumentos([]).passos_por_segundo == 1
    assert argumentos(["--modo", "rapido"]).passos_por_segundo == 5
    assert argumentos(["--cpu", "--partidas", "3"]).cpu


def test_gui_selecao_e_frames(tmp_path):
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    app.executar(max_frames=5)
    assert app.estado == "selecao"
    assert app.sessao is None


def test_gui_auto_inicia_e_encerra_com_resumo(tmp_path, capsys, monkeypatch):
    app = Aplicativo(argumentos(["--modo", "rapido", "--partidas", "2",
                                "--passos-por-segundo", "1000"]), MockLaya(), tmp_path)
    frames = []
    atualizar = app.atualizar

    def frame(dt):
        frames.append(app.estado)
        atualizar(dt)

    monkeypatch.setattr(app, "atualizar", frame)
    app.executar(max_frames=1200)
    assert frames[0] == "carregando"
    assert len(frames) < 1200
    assert app.estado == "resultado" and app.sessao.concluida, app.erro
    assert len(app.sessao.resultados) == 2
    linhas = ["Resumo da sessão"]
    totais = {"laya": 0, "algoritmo": 0}
    for i, resultado in enumerate(app.sessao.resultados, 1):
        geral = resultado["comparacao"]["geral"]
        linhas.append(f"Partida {i}: Laya: {geral['laya']['pontos']} pontos · "
                      f"Algoritmo: {geral['algoritmo']['pontos']} pontos")
        for agente in totais:
            totais[agente] += geral[agente]["pontos"]
    linhas.append(f"Totais: Laya: {totais['laya']} pontos · Algoritmo: {totais['algoritmo']} pontos")
    assert app.resumo_terminal() == "\n".join(linhas)
    assert capsys.readouterr().out == app.resumo_terminal() + "\n"


def test_gui_auto_avanca_no_modo_normal(tmp_path):
    app = Aplicativo(argumentos(["--partidas", "2"]), MockLaya(), tmp_path)
    try:
        app.iniciar()
        app.futuro.result(timeout=5)
        app.futuro = None
        app.sessao.indice = 1
        app.estado = "resultado"
        app.proximo_passo = time.perf_counter() + 2
        app.atualizar(.016)
        assert app.estado == "resultado"
        app.proximo_passo = time.perf_counter() - .01
        app.atualizar(.016)
        assert app.estado == "jogando"
    finally:
        app.fechar()


def test_gui_auto_erro_encerra_e_main_retorna_falha(tmp_path, monkeypatch, capsys):
    from jogos.snake import __main__, gui

    decisor = MockLaya()

    def falhar():
        raise RuntimeError("modelo indisponível")

    decisor.carregar = falhar
    app = Aplicativo(argumentos(["--partidas", "1"]), decisor, tmp_path)
    monkeypatch.setattr(gui, "Aplicativo", lambda args: app)
    monkeypatch.setattr(__main__, "argumentos", lambda: app.args)
    assert __main__.main() != 0
    assert app.estado == "erro" and not app.rodando
    assert "modelo indisponível" in capsys.readouterr().out


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
