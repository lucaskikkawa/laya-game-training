import pytest
from jogos.snake.gui import tamanho_inicial_janela, mouse_para_logico


@pytest.mark.parametrize("desktop", [(1280, 720), (1366, 768), (1536, 864), (1920, 1080), (2560, 1440)])
def test_tamanho_inicial_cabe_e_preserva_proporcao(desktop):
    w, h = tamanho_inicial_janela(desktop)
    assert w <= desktop[0] and h <= desktop[1] - 100
    assert abs(w / h - 1280 / 860) < .01


def test_mouse_para_logico():
    assert mouse_para_logico((320, 215), (0, 0, 640, 430)) == (640, 430)
