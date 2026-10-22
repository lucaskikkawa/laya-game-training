"""LAYA_HOME é a raiz que contém modelos/ e runs/."""
import os
from pathlib import Path
import re


def raiz() -> Path:
    return Path(os.environ.get("LAYA_HOME", ".")).expanduser().resolve()


def pasta_modelos() -> Path:
    return raiz() / "modelos"


def versoes() -> list[str]:
    base = pasta_modelos()
    locais = {p.name.removeprefix("laya_") for p in base.glob("laya_v[0-9][0-9][0-9]") if p.is_dir()}
    return sorted(locais | {"v000"})


def modelo(versao: str) -> str:
    if not re.fullmatch(r"v\d{3}", versao):
        raise ValueError("Versão inválida; use v000, v001, ...")
    local = pasta_modelos() / f"laya_{versao}"
    if local.is_dir():
        return str(local)
    if versao == "v000":
        return "convaiinnovations/laya"
    raise FileNotFoundError(f"Modelo não encontrado: {local}")
