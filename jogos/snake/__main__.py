"""python -m jogos.snake"""
import argparse
import math
from .regras import NIVEIS


def argumentos(argv=None):
    parser = argparse.ArgumentParser(description="Snake Laya v0.1")
    parser.add_argument("--partidas", type=int, default=None)
    parser.add_argument("--nivel", type=int, choices=NIVEIS, default=15)
    parser.add_argument("--versao", default="v000")
    parser.add_argument("--modo", choices=("normal", "rapido"), default="normal")
    parser.add_argument("--passos-por-segundo", type=float)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--sem-janela", action="store_true")
    args = parser.parse_args(argv)
    if args.sem_janela and (args.modo != "rapido" or args.partidas is None):
        parser.error("--sem-janela exige --partidas N --modo rapido")
    args.auto_iniciar = args.partidas is not None
    if args.partidas is None:
        args.partidas = 1
    if args.partidas < 1 or (args.passos_por_segundo is not None and (not math.isfinite(args.passos_por_segundo) or args.passos_por_segundo <= 0)):
        parser.error("Partidas e passos por segundo devem ser positivos")
    if args.passos_por_segundo is None:
        args.passos_por_segundo = 5 if args.modo == "rapido" else 1
    return args


def main():
    args = argumentos()
    if args.sem_janela:
        from .terminal import executar
        return executar(args)
    from .gui import Aplicativo
    app = Aplicativo(args)
    app.executar()
    return 1 if app.erro else 0


if __name__ == "__main__":
    raise SystemExit(main())
