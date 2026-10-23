import pytest
from nucleo import usuario


def test_ausente_e_roundtrip(tmp_path):
    caminho = tmp_path / "config" / "usuario.json"
    assert usuario.carregar(caminho) == usuario.DEFAULTS
    assert not caminho.exists()
    config = dict(usuario.DEFAULTS, resolucao=[1280, 720], fps=144,
                  tela_cheia=True, vsync=True, painel=False, som=False)
    usuario.salvar(config, caminho)
    assert usuario.carregar(caminho) == config


@pytest.mark.parametrize("conteudo", ['{quebrado', 'null', '[]', '"texto"', '\xff'])
def test_corrompido(tmp_path, conteudo):
    caminho = tmp_path / "usuario.json"
    caminho.write_bytes(conteudo.encode("latin1"))
    assert usuario.carregar(caminho) == usuario.DEFAULTS


@pytest.mark.parametrize("resolucao", [False, "1280x720", [0, 720], [True, 720], [1280], [999999, 720]])
def test_valores_invalidos(tmp_path, resolucao):
    import json
    caminho = tmp_path / "usuario.json"
    caminho.write_text(json.dumps(dict(resolucao=resolucao, fps=True,
                                      tela_cheia=1, vsync="sim", painel=None, som=[])))
    assert usuario.carregar(caminho) == usuario.DEFAULTS
