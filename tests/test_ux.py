"""Lógica do retoque de UX (v0.1.2) sem Pygame."""
import pytest
from jogos.snake import ux
from jogos.snake.ux import CampoNumerico


def test_rotulo_alternador():
    assert ux.rotulo_alternador("Nível", "15x15") == "<  Nível: 15x15  >"


def test_ciclar_da_a_volta_nos_dois_sentidos():
    assert ux.ciclar([15, 20, 25], 25) == 15
    assert ux.ciclar([15, 20, 25], 15, -1) == 25
    assert ux.ciclar([15, 20, 25], 20, -1) == 15


def test_proximo_foco():
    ordem = ["a", "b", "c"]
    assert ux.proximo_foco(ordem, None) == "a"
    assert ux.proximo_foco(ordem, None, -1) == "c"
    assert ux.proximo_foco(ordem, "c") == "a"
    assert ux.proximo_foco(ordem, "a", -1) == "c"


def test_cores_do_botao():
    base = (76, 155, 234)
    normal = ux.cor_botao(base)
    assert normal == base
    assert sum(ux.cor_botao(base, hover=True)) > sum(normal)
    assert sum(ux.cor_botao(base, hover=True, pressionado=True)) < sum(normal)
    assert ux.cor_botao(base, ativo=False, hover=True) == (43, 53, 68)


def test_pressao_dura_100ms():
    p = ux.Pressao()
    p.pressionar("nivel", 10.0)
    assert p.ativa("nivel", 10.05)
    assert not p.ativa("nivel", 10.11)
    assert not p.ativa("modo", 10.05)


def test_campo_rejeita_letras():
    c = CampoNumerico("3", 1, 9999, inteiro=True)
    for letra in "abc-+ e.":
        assert not c.digitar(letra)
    assert c.texto == "3"
    assert c.digitar("4") and c.texto == "34"


def test_campo_inteiro_rejeita_acima_do_maximo():
    c = CampoNumerico("999", 1, 9999, inteiro=True)
    assert c.digitar("9") and c.texto == "9999"
    assert not c.digitar("9") and c.texto == "9999"


def test_campo_decimal_um_ponto_e_maximo():
    c = CampoNumerico("1", .1, 1000, casas=2)
    assert c.digitar(".") and c.digitar("5") and c.texto == "1.5"
    assert not c.digitar(".")
    assert c.digitar("2") and not c.digitar("3") and c.texto == "1.52"
    c = CampoNumerico("100", .1, 1000)
    assert c.digitar("0") and c.texto == "1000"
    assert not c.digitar("1") and not c.digitar(".") or c.texto.startswith("1000")


def test_campo_vazio_ou_zero_volta_ao_ultimo_valido():
    c = CampoNumerico("7", 1, 9999, inteiro=True)
    c.apagar()
    assert c.texto == "" and c.confirmar() == "7"
    c.apagar()
    assert c.digitar("0") and c.texto == "0"
    assert c.confirmar() == "7"


def test_campo_confirmar_normaliza():
    c = CampoNumerico("1", 1, 9999, inteiro=True)
    c.apagar()
    c.digitar("0"); c.digitar("0"); c.digitar("8")
    assert c.confirmar() == "8" and c.valor == 8
    d = CampoNumerico("1", .1, 1000)
    d.apagar(); d.digitar("0"); d.digitar("."); d.digitar("5")
    assert d.confirmar() == "0.5"


def test_campo_decimal_zero_volta():
    c = CampoNumerico("2", .1, 1000)
    c.apagar(); c.digitar("0"); c.digitar("."); c.digitar("0")
    assert c.confirmar() == "2"


def test_campo_inicial_da_linha_de_comando_nao_e_alterado():
    assert CampoNumerico(20000, 1, 9999, inteiro=True).confirmar() == "20000"
    assert CampoNumerico(1000.0, .1, 1000).texto == "1000"
    assert CampoNumerico("lixo", 1, 9, inteiro=True).texto == "1"


def test_campo_mudar_respeita_limites():
    c = CampoNumerico("9998", 1, 9999, inteiro=True)
    c.mudar(1); c.mudar(1)
    assert c.texto == "9999"
    c = CampoNumerico("1", 1, 9999, inteiro=True)
    c.mudar(-1)
    assert c.texto == "1"


def test_velocidade_menos_nao_cai_abaixo_de_1_mas_aceita_decimal():
    v = CampoNumerico("1", .1, 1000, piso_passo=1)
    v.mudar(-1)
    assert v.texto == "1"
    w = CampoNumerico("0.5", .1, 1000, piso_passo=1)
    w.mudar(-1)
    assert w.texto == "0.5"
    w.mudar(1)
    assert w.texto == "1.5"


def test_cursor_pisca_e_reinicia_ao_digitar():
    c = CampoNumerico("1", 1, 9, inteiro=True)
    assert c.cursor_visivel(0.0)
    assert not c.cursor_visivel(.6)
    assert c.cursor_visivel(1.1)
    c.apagar(agora=2.0)
    assert c.cursor_visivel(2.3) and not c.cursor_visivel(2.6)


def test_grade_com_espacamento_igual():
    ys = [ux.linha_grade(i) for i in range(7)]
    assert len({b - a for a, b in zip(ys, ys[1:])}) == 1
