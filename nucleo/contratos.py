"""Vocabulário e interface genéricos: não dependem de Snake ou Pygame."""
from dataclasses import dataclass
from typing import Protocol

VOCABULARIO = "self = me; danger = things that end the game; reward = goal; free space = safe empty area."


@dataclass(frozen=True)
class Opcao:
    id: str
    efeito: str


@dataclass(frozen=True)
class Decisao:
    probabilidades: dict[str, float]
    escolha: str
    confianca: float
    latencia_ms: float


class Decisor(Protocol):
    def decidir(self, estado: str, opcoes: tuple[Opcao, ...]) -> Decisao: ...
