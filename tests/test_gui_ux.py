"""Retoque de UX da tela de seleção (hover, cliques, teclado, campos, status)."""
import pygame
import pytest
from jogos.snake import ux
from jogos.snake.__main__ import argumentos
from jogos.snake.gui import Aplicativo
from test_sessao import MockLaya


@pytest.fixture
def app(tmp_path):
    a = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    a.destino = pygame.Rect(0, 0, 1280, 860)
    a.desenhar()
    yield a
    a.fechar()


def tecla(app, key, unicode="", mod=0):
    app.evento(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode, mod=mod))


def pos_janela(app, ponto):
    """Ponto do canvas lógico -> pixel da janela (inverso de mouse_para_logico)."""
    d = app.destino
    return d.left + ponto[0] * d.width / 1280, d.top + ponto[1] * d.height / 860


def clicar(app, acao, botao=1):
    app.desenhar()
    rect = next(r for r, a, _ in app.botoes if a == acao)
    app.evento(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=botao, pos=pos_janela(app, rect.center)))


def clicar_campo(app, nome):
    app.desenhar()
    app.evento(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos_janela(app, app.campos[nome].center)))


def test_alternadores_no_formato_com_setas(app, monkeypatch):
    vistos = []
    monkeypatch.setattr(app, "alternador", lambda nome, valor, *a: vistos.append(ux.rotulo_alternador(nome, valor)))
    app.desenhar_selecao()
    assert "<  Nível: 15x15  >" in vistos
    assert "<  Automático: não  >" in vistos


def test_clique_esquerdo_avanca_e_direito_volta(app):
    clicar(app, "nivel")
    assert app.nivel == 20
    clicar(app, "nivel", botao=3)
    assert app.nivel == 15
    clicar(app, "nivel", botao=3)
    assert app.nivel == 25
    clicar(app, "versao", botao=3)
    assert app.versao == app.versoes[-1] or len(app.versoes) == 1


def test_clique_direito_em_botao_comum_nao_age(app):
    clicar(app, "menos", botao=3)
    assert app.velocidade == "1"
    clicar(app, "start", botao=3)
    assert app.estado == "selecao"


def test_setas_mudam_opcao_em_foco(app):
    tecla(app, pygame.K_TAB, "\t")
    assert app.foco == "nivel"
    tecla(app, pygame.K_RIGHT)
    assert app.nivel == 20
    tecla(app, pygame.K_LEFT)
    tecla(app, pygame.K_LEFT)
    assert app.nivel == 25
    tecla(app, pygame.K_TAB, "\t")
    tecla(app, pygame.K_TAB, "\t")
    assert app.foco == "modo"
    tecla(app, pygame.K_RIGHT)
    assert app.modo == "rapido" and app.velocidade == "5"


def test_tab_percorre_controles_e_shift_tab_volta(app):
    visitados = []
    for _ in range(len(ux.ORDEM_FOCO)):
        tecla(app, pygame.K_TAB, "\t")
        visitados.append(app.foco)
    assert tuple(visitados) == ux.ORDEM_FOCO
    tecla(app, pygame.K_TAB, "\t")
    assert app.foco == "nivel"
    tecla(app, pygame.K_TAB, "\t", mod=pygame.KMOD_SHIFT)
    assert app.foco == "start"
    assert app.painel  # Tab na seleção não alterna o painel


def test_tab_fora_da_selecao_continua_alternando_painel(app):
    app.estado = "resultado"
    tecla(app, pygame.K_TAB, "\t")
    assert not app.painel


def test_enter_inicia_com_status_de_gpu(app):
    tecla(app, pygame.K_RETURN, "\r")
    assert app.estado == "carregando"
    assert app.status == "Carregando o Laya na GPU..."


def test_status_de_cpu_quando_solicitado(tmp_path):
    a = Aplicativo(argumentos(["--cpu"]), MockLaya(), tmp_path)
    try:
        a.iniciar()
        assert a.status == "Carregando o Laya na CPU..."
    finally:
        a.fechar()


def test_campo_foco_rejeita_letras_e_limite(app):
    clicar_campo(app, "partidas")
    assert app.editando
    tecla(app, pygame.K_BACKSPACE)
    for ch in "ab5":
        tecla(app, ord(ch), ch)
    assert app.partidas == "5"
    for _ in range(6):
        tecla(app, pygame.K_0, "0")
    assert app.partidas == "5000"  # 50000 passaria do limite 9999
    tecla(app, pygame.K_ESCAPE)
    assert app.foco is None and app.estado == "selecao"


def test_campo_invalido_volta_ao_ultimo_valido_ao_sair(app):
    clicar_campo(app, "velocidade")
    tecla(app, pygame.K_BACKSPACE)
    assert app.velocidade == ""
    clicar(app, "nivel")  # sai do campo
    assert app.velocidade == "1"
    clicar_campo(app, "velocidade")
    tecla(app, pygame.K_BACKSPACE)
    tecla(app, pygame.K_0, "0")
    tecla(app, pygame.K_TAB, "\t")
    assert app.velocidade == "1"


def test_p_e_espaco_nao_pausam_nem_digitam_em_campo(app):
    clicar_campo(app, "partidas")
    tecla(app, pygame.K_SPACE, " ")
    tecla(app, pygame.K_p, "p")
    assert app.partidas == "1" and not app.pausa.ativa


def test_pausa_continua_com_p_e_espaco(app):
    app.estado = "jogando"
    tecla(app, pygame.K_p, "p")
    assert app.pausa.ativa
    tecla(app, pygame.K_SPACE, " ")
    assert not app.pausa.ativa


def test_enter_no_campo_confirma_e_inicia(app):
    clicar_campo(app, "partidas")
    tecla(app, pygame.K_BACKSPACE)
    tecla(app, pygame.K_3, "3")
    tecla(app, pygame.K_RETURN, "\r")
    assert app.estado == "carregando" and app.sessao.partidas == 3


def test_botao_afunda_apos_clique_e_volta(app, monkeypatch):
    clicar(app, "nivel")
    assert app.pressao.ativa("nivel", app.pressao.ate - .01)
    assert not app.pressao.ativa("nivel", app.pressao.ate + .01)


def test_hover_clareia_o_botao(app):
    desenhado = []
    original = pygame.draw.rect

    def rect(surface, cor, *a, **k):
        desenhado.append(cor)
        return original(surface, cor, *a, **k)

    app.mouse_logico = (-1, -1)
    app.desenhar_selecao()
    pygame.draw.rect = rect
    try:
        rect_botao = next(r for r, a, _ in app.botoes if a == "nivel")
        app.mouse_logico = rect_botao.center
        desenhado.clear()
        app.botao("x", rect_botao, "nivel")
        assert desenhado[0] == ux.cor_botao((76, 155, 234), hover=True)
    finally:
        pygame.draw.rect = original


def test_treinar_desativado_e_nao_responde(app):
    app.desenhar()
    rect, _, ativo = next(b for b in app.botoes if b[1] == "treinar")
    assert not ativo
    app.evento(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos_janela(app, rect.center)))
    assert app.estado == "selecao"


def test_texto_do_treinar(app, monkeypatch):
    rotulos = []
    original = app.botao
    monkeypatch.setattr(app, "botao", lambda titulo, *a, **k: (rotulos.append(titulo), original(titulo, *a, **k)))
    app.desenhar_selecao()
    assert "Treinar · disponível na v0.2" in rotulos


def test_grade_da_selecao_alinhada(app):
    app.desenhar()
    alternadores = [r for r, a, _ in app.botoes if a in ux.ALTERNADORES]
    assert {r.x for r in alternadores} == {ux.COLUNA_1} and {r.width for r in alternadores} == {ux.LARGURA_ALTERNADOR}
    assert {r.x for r in app.campos.values()} == {ux.COLUNA_2}
    ys = sorted([r.y for r in alternadores] + [r.y for r in app.campos.values()])
    assert len({b - a for a, b in zip(ys, ys[1:])}) == 1
    assert [r.x for r, a, _ in app.botoes if a == "treinar"] == [ux.COLUNA_2]


def test_mais_e_menos_usam_limites_do_campo(app):
    clicar(app, "mais")
    assert app.velocidade == "2"
    clicar(app, "menos")
    clicar(app, "menos")
    assert app.velocidade == "1"


def test_janela_inicial_cabe_na_tela(app):
    from jogos.snake.gui import tamanho_inicial_janela
    assert app.tamanho_inicial == tamanho_inicial_janela(pygame.display.get_desktop_sizes()[0])
