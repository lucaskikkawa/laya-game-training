"""QA sem Pygame/modelo. Nenhuma derrota é descartada ou ressorteada."""
import argparse
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import json
import os
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


def diagnosticar(tarefa):
    nivel, indice = tarefa
    comidas = lista_comidas(nivel, max(2000, NIVEIS[nivel].meta * 8))
    jogo = Jogo(nivel, comidas)
    algoritmo = Algoritmo()
    historico = deque(maxlen=jogo.nivel.limite + 1)
    while not jogo.fim:
        acao = algoritmo.escolher(jogo)
        historico.append({"cabeca": jogo.corpo[0], "comida": jogo.comida,
                          "sem_comer": jogo.sem_comer, "acao": acao,
                          "estrategia": algoritmo.estrategia})
        jogo.passo(acao)
    falha = None
    if not jogo.vitoria:
        falha = {"partida": indice, "resumo": jogo.resumo(), "comidas": comidas,
                 "corpo": jogo.corpo, "comida": jogo.comida,
                 "sem_comer": jogo.sem_comer, "direcao": jogo.direcao,
                 "indice_comida": jogo.indice_comida, "historico": list(historico)}
    return nivel, falha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partidas", type=int, default=1000)
    parser.add_argument("--nivel", type=int, choices=NIVEIS, nargs="+", default=list(NIVEIS))
    parser.add_argument("--processos", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--saida", type=Path, default=Path("/tmp/qa_algoritmo.json"))
    args = parser.parse_args()
    if args.partidas < 1 or args.processos < 1:
        parser.error("--partidas e --processos devem ser positivos")
    inicio = perf_counter()
    resultados = {n: {"nivel": n, "partidas": args.partidas, "vitorias": 0, "falhas": []}
                  for n in args.nivel}
    concluidas = dict.fromkeys(args.nivel, 0)
    tarefas = ((n, i) for n in args.nivel for i in range(args.partidas))
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.processos) as pool:
        for nivel, falha in pool.map(diagnosticar, tarefas, chunksize=1):
            resultado = resultados[nivel]
            concluidas[nivel] += 1
            resultado["vitorias"] += falha is None
            if falha is not None:
                resultado["falhas"].append(falha)
            if concluidas[nivel] % 10 == 0 or concluidas[nivel] == args.partidas:
                print(f'{nivel}x{nivel}: {resultado["vitorias"]}/{concluidas[nivel]} vitórias', flush=True)
                args.saida.write_text(json.dumps({"resultados": list(resultados.values()),
                    "segundos": perf_counter() - inicio}), encoding="utf-8")
    return 0 if all(r["vitorias"] == args.partidas for r in resultados.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
