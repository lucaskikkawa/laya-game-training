import pygame
import pytest

from jogos.snake.__main__ import argumentos
from jogos.snake.gui import Aplicativo
from jogos.snake.controles import Pausa
from test_sessao import MockLaya


def test_pausa_so_durante_jogo():
    p = Pausa()
    for estado in ('selecao', 'carregando', 'apurando', 'resultado', 'erro'):
        assert not p.alternar(estado)
    assert p.alternar('jogando')
    assert not p.alternar('jogando')


@pytest.mark.parametrize('tecla', [pygame.K_p, pygame.K_SPACE])
def test_pausa_impede_novos_passos_e_mostra_texto(tmp_path, monkeypatch, tecla):
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        app.iniciar()
        app.futuro.result(timeout=5)
        app._coletar()
        app.evento(pygame.event.Event(pygame.KEYDOWN, key=tecla, unicode=''))
        assert app.pausa.ativa
        for _ in range(3):
            app.atualizar(.1)
        assert app.jogo.passos == 0 and app.futuro is None
        textos = []
        monkeypatch.setattr(app, 'texto', lambda texto, *a, **kw: textos.append(texto))
        app.desenhar()
        assert 'PAUSADO' in textos
        app.evento(pygame.event.Event(pygame.KEYDOWN, key=tecla, unicode=''))
        app.atualizar(.1)
        assert not app.pausa.ativa and app.futuro is not None
    finally:
        app.fechar()


def test_pausa_com_decisao_pendente_preserva_historico(tmp_path):
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        app.iniciar()
        app.futuro.result(timeout=5)
        app._coletar()
        app.atualizar(.1)
        app.pausa.alternar(app.estado)
        app.futuro.result(timeout=5)
        app.atualizar(.1)
        assert not app.historico
        app.pausa.alternar(app.estado)
        app.atualizar(.1)
        assert len(app.historico) == app.jogo.passos == 1
        assert app.historico[0]['confianca'] == .7
    finally:
        app.fechar()


def test_falha_gui_aparece_antes_do_resumo(tmp_path):
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        app.erro = 'Falha: modelo indisponível'
        texto = app.resumo_terminal()
        assert texto.index(app.erro) < texto.index('Resumo da sessão') < texto.index('Totais:')
    finally:
        app.fechar()


def test_voltar_a_selecao_limpa_pausa(tmp_path):
    app = Aplicativo(argumentos([]), MockLaya(), tmp_path)
    try:
        app.estado = 'jogando'
        app.pausa.alternar(app.estado)
        app.acionar('selecao')
        assert app.estado == 'selecao' and not app.pausa.ativa
    finally:
        app.fechar()
