import time
import pygame
import pytest
from jogos.snake.__main__ import argumentos
from jogos.snake.gui import Aplicativo, mouse_para_logico, tamanho_inicial_janela
from test_sessao import MockLaya


@pytest.mark.parametrize("desktop", [(1920, 1080), (1366, 768), (3840, 2160)])
def test_tamanho_inicial_cabe_e_preserva_proporcao(desktop):
    largura, altura = tamanho_inicial_janela(desktop)
    assert 640 <= largura <= desktop[0] * .9
    assert 430 <= altura <= (desktop[1] - 120) * .9
    assert largura / altura == pytest.approx(1280 / 860, abs=.003)
    if desktop == (3840, 2160):
        assert largura > 1280 and altura > 860


@pytest.mark.parametrize("desktop", [(640, 430), (500, 300), (320, 600)])
def test_tamanho_inicial_desktop_pequeno(desktop):
    largura, altura = tamanho_inicial_janela(desktop)
    assert 0 < largura <= desktop[0]
    assert 0 < altura <= desktop[1]
    assert largura / altura == pytest.approx(1280 / 860, abs=.01)
    if desktop == (640, 430):
        assert (largura, altura) == (640, 430)


@pytest.mark.parametrize("pos,destino,esperado", [
    ((640, 430), (0, 0, 1280, 860), (640, 430)),
    ((320, 215), (0, 0, 640, 430), (640, 430)),
    ((740, 480), (100, 50, 1280, 860), (640, 430)),
    ((100, 50), (100, 50, 640, 430), (0, 0)),
    ((740, 480), (100, 50, 640, 430), (1280, 860)),
    ((50, 25), (100, 50, 640, 430), (-100, -50)),
])
def test_mouse_para_logico(pos, destino, esperado):
    assert mouse_para_logico(pos, destino) == pytest.approx(esperado)


def test_janela_inicial_e_retorno_do_f11(tmp_path, monkeypatch):
    monkeypatch.setattr(pygame.display, "get_desktop_sizes", lambda: [(1366, 768)])
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        inicial = tamanho_inicial_janela((1366, 768))
        assert app.tela.get_size() == inicial
        chamadas = []
        def set_mode(tamanho, flags):
            chamadas.append((tamanho, flags))
            return app.tela
        monkeypatch.setattr(pygame.display, "set_mode", set_mode)
        for _ in range(2):
            app.evento(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11))
        assert chamadas == [((0, 0), pygame.FULLSCREEN), (inicial, pygame.RESIZABLE)]
        assert not app.cheia
    finally:
        app.fechar()


def test_desktop_indisponivel_usa_fallback(tmp_path, monkeypatch):
    def indisponivel():
        raise pygame.error("desktop indisponível")
    monkeypatch.setattr(pygame.display, "get_desktop_sizes", indisponivel)
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        assert app.tela.get_size() == tamanho_inicial_janela((1280, 860))
    finally:
        app.fechar()


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
    assert app.estado == "principal"
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


@pytest.fixture(autouse=True)
def config_isolada(tmp_path, monkeypatch):
    from nucleo import usuario
    monkeypatch.setattr(usuario, "caminho_config", lambda: tmp_path / "config" / "usuario.json")


def clicar(app, acao):
    app.desenhar()
    rect = next(r for r, a, ativo in app.botoes if a == acao and ativo)
    d = app.destino
    pos = (int(d.x + rect.centerx * d.width / 1280),
           int(d.y + rect.centery * d.height / 860))
    app.evento(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))


def test_navegacao_principal_setup_esc_e_sair(tmp_path):
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        assert app.estado == "principal"
        clicar(app, "selecao")
        assert app.estado == "selecao" and app.sessao is None
        clicar(app, "principal")
        assert app.estado == "principal"
        clicar(app, "selecao")
        app.foco = "partidas"
        app.evento(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        assert app.estado == "principal" and app.foco is None
        app.evento(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        assert app.rodando
        clicar(app, "sair")
        assert not app.rodando
    finally:
        app.fechar()


def test_config_aplicar_voltar_e_carregar(tmp_path, monkeypatch):
    from nucleo import usuario
    monkeypatch.setattr(pygame.display, "list_modes", lambda: [(1024, 768), (800, 600)])
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        clicar(app, "config")
        assert app.resolucoes == [None, [1024, 768], [800, 600]]
        for chave in ("resolucao", "fps", "painel", "som"):
            clicar(app, "config_" + chave)
        clicar(app, "aplicar")
        assert app.estado == "config"
        assert app.tela.get_size() == (1024, 768)
        assert app.config["fps"] == 120
        assert not app.painel and not app.config["som"]
        assert usuario.carregar() == app.config
        clicar(app, "config_som")
        clicar(app, "principal")
        clicar(app, "config")
        assert not app.edicao_config["som"]
        app.evento(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        assert app.estado == "principal"
    finally:
        app.fechar()
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        assert app.tela.get_size() == (1024, 768)
        assert not app.painel and not app.config["som"]
    finally:
        app.fechar()


@pytest.mark.parametrize("falha", [pygame.error, TypeError])
def test_vsync_fallback_e_tela_cheia(tmp_path, monkeypatch, falha):
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        chamadas = []
        def set_mode(tamanho, flags, **kwargs):
            chamadas.append((tamanho, flags, kwargs))
            if kwargs:
                raise falha("vsync indisponível")
            return app.tela
        monkeypatch.setattr(pygame.display, "set_mode", set_mode)
        app.acionar("config")
        app.acionar("config_vsync")
        app.acionar("config_tela_cheia")
        app.acionar("aplicar")
        assert app.cheia and app.config["vsync"]
        assert chamadas == [((0, 0), pygame.FULLSCREEN, {"vsync": 1}),
                            ((0, 0), pygame.FULLSCREEN, {})]
    finally:
        app.fechar()


def test_esc_jogo_retorna_selecao(tmp_path):
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        app.iniciar()
        app.futuro.result(timeout=5)
        app._coletar()
        assert app.estado == "jogando"
        app.evento(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        assert app.estado == "selecao"
        assert app.sessao.documento["status"] == "interrompida"
    finally:
        app.fechar()


def test_aplicar_restaura_modo_apos_f11(tmp_path):
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        app.evento(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11))
        assert app.cheia
        app.acionar("config")
        app.acionar("aplicar")
        assert not app.cheia
        assert app.tela.get_size() == app.tamanho_inicial
    finally:
        app.fechar()


@pytest.mark.parametrize("modos", [-1, []])
def test_resolucao_indisponivel_usa_automatica(tmp_path, monkeypatch, modos):
    from nucleo import usuario
    usuario.salvar(dict(usuario.DEFAULTS, resolucao=[800, 600]))
    monkeypatch.setattr(pygame.display, "list_modes", lambda: modos)
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        assert app.config["resolucao"] is None
        assert app.resolucoes == [None]
        assert app.tela.get_size() == app.tamanho_inicial
    finally:
        app.fechar()
