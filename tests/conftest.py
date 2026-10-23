import os
import sys
from pathlib import Path
import pytest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def preparar_comida_sem_saida():
    """Corpo contíguo abaixo da meta real; comer fecha a saída por mais de 100 passos."""
    from jogos.snake.regras import Jogo

    def preparar(comidas):
        g = Jogo(25, comidas)
        g.corpo = [(1, 0), (1, 1), (0, 1)] + [
            (x, y) for y in range(2, 7)
            for x in (range(25) if y % 2 == 0 else range(24, -1, -1))]
        g.direcao = 3
        g.indice_comida = 0
        g.pulos.clear()
        g.comidas_efetivas.clear()
        g._nova_comida()
        assert not g.fim and g.comida == (0, 0)
        return g

    return preparar


def pytest_addoption(parser):
    parser.addoption("--qa-partidas", type=int, default=1000, help="Partidas por nível no teste slow (padrão: 1000)")
