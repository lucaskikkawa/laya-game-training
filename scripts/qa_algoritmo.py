"""QA sem Pygame/modelo. Nenhuma derrota é descartada ou ressorteada."""
import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jogos.snake.algoritmo import Algoritmo
from jogos.snake.regras import Jogo, NIVEIS, lista_comidas


def partida(nivel, comidas=None):
    jogo = Jogo(nivel, comidas)
    algoritmo = Algoritmo()
    while not jogo.fim:
        jogo.passo(algoritmo.escolher(jogo))
    return jogo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partidas", type=int, default=1000)
    parser.add_argument("--nivel", type=int, choices=NIVEIS, nargs="+", default=list(NIVEIS))
    parser.add_argument("--saida", type=Path, default=Path("runs/qa_algoritmo.json"))
    args = parser.parse_args()
    if args.partidas < 1:
        parser.error("--partidas deve ser positivo")
    inicio = perf_counter()
    resultados = []
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    for nivel in args.nivel:
        vitorias = 0
        falhas = []
        for indice in range(args.partidas):
            comidas = lista_comidas(nivel)
            jogo = partida(nivel, comidas)
            vitorias += jogo.vitoria
            if not jogo.vitoria:
                falhas.append({"partida": indice, "resumo": jogo.resumo(), "comidas": comidas})
            if (indice + 1) % 10 == 0 or indice == args.partidas - 1:
                print(f"{nivel}x{nivel}: {vitorias}/{indice + 1} vitórias", flush=True)
        resultados.append({"nivel": nivel, "partidas": args.partidas, "vitorias": vitorias, "falhas": falhas})
        args.saida.write_text(json.dumps({"resultados": resultados, "segundos": perf_counter() - inicio}), encoding="utf-8")
    return 0 if all(r["vitorias"] == args.partidas for r in resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
