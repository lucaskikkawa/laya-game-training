"""QA sem Pygame/modelo. Nenhuma derrota é descartada ou ressorteada."""
import argparse
from collections import deque
from concurrent.futures import ProcessPoolExecutor, as_completed
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
    nivel, indice, *listas = tarefa
    comidas = listas[0] if listas else lista_comidas(nivel)
    jogo = None
    algoritmo = Algoritmo()
    historico = deque(maxlen=NIVEIS[nivel].limite + 1)
    erro = None
    try:
        jogo = Jogo(nivel, comidas)
        while not jogo.fim:
            acao = algoritmo.escolher(jogo)
            historico.append({"cabeca": jogo.corpo[0], "comida": jogo.comida,
                              "sem_comer": jogo.sem_comer, "acao": acao,
                              "estrategia": algoritmo.estrategia})
            jogo.passo(acao)
    except RuntimeError as exc:
        erro = str(exc)
    falha = None
    if erro or not jogo.vitoria:
        falha = {"partida": indice, "resumo": jogo.resumo() if jogo else None, "comidas": comidas,
                 "corpo": jogo.corpo if jogo else None, "comida": jogo.comida if jogo else None,
                 "sem_comer": jogo.sem_comer if jogo else None, "direcao": jogo.direcao if jogo else None,
                 "indice_comida": jogo.indice_comida if jogo else None, "historico": list(historico),
                 "erro": erro, "pulos": jogo.pulos if jogo else []}
    return nivel, falha


def carregar_falhas(arquivo):
    """Aceita fixtures ou o relatório completo, sem sortear novas candidatas."""
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    if isinstance(dados, dict):
        dados = [{**f, "nivel": r["nivel"]} for r in dados["resultados"]
                 for f in r["falhas"]]
    if not dados:
        raise ValueError("Arquivo sem falhas para repetir")
    tarefas = []
    for falha in dados:
        nivel = falha["nivel"]
        if nivel not in NIVEIS:
            raise ValueError(f"Nível {nivel} não é jogável na v0.1")
        tarefas.append((nivel, falha["partida"], falha["comidas"]))
    return tarefas


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partidas", type=int, default=200)
    parser.add_argument("--repetir-falhas", type=Path,
                        help="Repete apenas as falhas do JSON, com as mesmas listas completas")
    parser.add_argument("--nivel", type=int, choices=NIVEIS, nargs="+", default=list(NIVEIS))
    parser.add_argument("--processos", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--saida", type=Path, default=Path("/tmp/qa_algoritmo.json"))
    args = parser.parse_args(argv)
    if args.partidas < 1 or args.processos < 1:
        parser.error("--partidas e --processos devem ser positivos")
    inicio = perf_counter()
    if args.repetir_falhas:
        if args.saida.resolve() == args.repetir_falhas.resolve():
            parser.error("--saida deve ser diferente do arquivo de falhas original")
        try:
            tarefas = carregar_falhas(args.repetir_falhas)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            parser.error(f"Arquivo de falhas inválido: {exc}")
    else:
        tarefas = [(n, i) for n in args.nivel for i in range(args.partidas)]
    resultados = {}
    for n, *_ in tarefas:
        resultado = resultados.setdefault(n, {"nivel": n, "partidas": 0, "vitorias": 0, "falhas": []})
        resultado["partidas"] += 1
    concluidas = dict.fromkeys(resultados, 0)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.processos) as pool:
        pendentes = {pool.submit(diagnosticar, tarefa): tarefa for tarefa in tarefas}
        for futuro in as_completed(pendentes):
            nivel, falha = futuro.result()
            resultado = resultados[nivel]
            concluidas[nivel] += 1
            resultado["vitorias"] += falha is None
            if falha is not None:
                resultado["falhas"].append(falha)
            if args.repetir_falhas:
                motivo = (falha["erro"] or falha["resumo"]["morte"]) if falha else None
                print(f'{nivel}x{nivel} partida {pendentes[futuro][1]}: '
                      + (f'FALHA ({motivo})' if falha else 'VITÓRIA'), flush=True)
            if concluidas[nivel] % 10 == 0 or concluidas[nivel] == resultado["partidas"]:
                print(f'{nivel}x{nivel}: {resultado["vitorias"]}/{concluidas[nivel]} vitórias', flush=True)
                args.saida.write_text(json.dumps({"resultados": list(resultados.values()),
                    "segundos": perf_counter() - inicio}), encoding="utf-8")
    vitorias = sum(r["vitorias"] for r in resultados.values())
    aprovado = vitorias == len(tarefas)
    print(f'RESULTADO FINAL: {vitorias}/{len(tarefas)} vitórias — '
          f'{"APROVADO (100%)" if aprovado else "REPROVADO (exigido 100%)"}. '
          f'Relatório: {args.saida}', flush=True)
    return 0 if aprovado else 1


if __name__ == "__main__":
    raise SystemExit(main())
