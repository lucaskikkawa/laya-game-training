"""Preferências locais da interface; arquivos antigos ou inválidos são tolerados."""
import json
from pathlib import Path
from .config import raiz

DEFAULTS = {
    "resolucao": None, "tela_cheia": False, "fps": 60,
    "vsync": False, "painel": True, "som": True,
}
LIMITES_FPS = (30, 60, 120, 144, 240, 0)


def caminho_config():
    return raiz() / "config" / "usuario.json"


def validar(dados):
    config = DEFAULTS.copy()
    if not isinstance(dados, dict):
        return config
    for chave in ("tela_cheia", "vsync", "painel", "som"):
        if type(dados.get(chave)) is bool:
            config[chave] = dados[chave]
    if type(dados.get("fps")) is int and dados["fps"] in LIMITES_FPS:
        config["fps"] = dados["fps"]
    resolucao = dados.get("resolucao")
    if (isinstance(resolucao, (list, tuple)) and len(resolucao) == 2
            and all(type(v) is int and 0 < v <= 16384 for v in resolucao)):
        config["resolucao"] = list(resolucao)
    return config


def carregar(caminho=None):
    try:
        return validar(json.loads(Path(caminho or caminho_config()).read_text(encoding="utf-8")))
    except (OSError, ValueError, UnicodeError):
        return DEFAULTS.copy()


def salvar(dados, caminho=None):
    caminho = Path(caminho or caminho_config())
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".json.tmp")
    temporario.write_text(json.dumps(validar(dados), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporario.replace(caminho)
