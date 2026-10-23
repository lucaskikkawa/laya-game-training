"""Isola extensões nativas do modelo do processo SDL (sempre via spawn)."""
import multiprocessing
from concurrent.futures import CancelledError
from threading import Lock

from .laya import Laya


def _servir(conexao, versao, cpu):
    # Executado na thread principal de um Python novo, sem inicializar SDL.
    decisor = Laya(versao, cpu)
    try:
        while True:
            metodo, argumentos = conexao.recv()
            try:
                valor = getattr(decisor, metodo)(*argumentos)
                conexao.send((True, valor, decisor.telemetria()))
            except Exception as exc:
                conexao.send((False, f"{type(exc).__name__}: {exc}", None))
    except (EOFError, OSError):
        pass
    finally:
        conexao.close()


class LayaProcesso:
    """Proxy serial usado pelo worker da GUI; telemetria é apenas um snapshot.

    fechar() pode rodar na thread gráfica durante recv(): terminar o filho
    desbloqueia o worker sem esperar por downloads ou imports nativos.
    """

    def __init__(self, versao="v000", cpu=False):
        self.versao, self.cpu = versao, cpu
        self._lock = Lock()
        self._processo = None
        self._conexao = None
        self._fechado = False
        self._dados = {"dispositivo": "não carregado", "gpu": "", "carregamento_ms": 0.0}

    def _chamar(self, metodo, *argumentos):
        with self._lock:
            if self._fechado:
                raise CancelledError("Laya encerrado")
            if self._processo is None:
                contexto = multiprocessing.get_context("spawn")
                conexao, filho = contexto.Pipe()
                processo = contexto.Process(target=_servir, args=(filho, self.versao, self.cpu),
                                             name="laya-modelo", daemon=True)
                try:
                    processo.start()
                except BaseException:
                    conexao.close()
                    raise
                finally:
                    filho.close()
                self._conexao, self._processo = conexao, processo
            conexao = self._conexao
            conexao.send((metodo, argumentos))
        try:
            sucesso, valor, dados = conexao.recv()
        except (EOFError, OSError, ValueError) as exc:
            if self._fechado:
                raise CancelledError("Laya encerrado pela janela") from exc
            raise RuntimeError("O processo Laya foi encerrado durante a operação") from exc
        if not sucesso:
            raise RuntimeError(valor)
        self._dados = dados
        return valor

    def carregar(self):
        self._chamar("carregar")

    def decidir(self, estado, opcoes):
        return self._chamar("decidir", estado, opcoes)

    def telemetria(self):
        return dict(self._dados)

    def fechar(self):
        with self._lock:
            if self._fechado:
                return
            self._fechado = True
            if self._processo is not None:
                if self._processo.is_alive():
                    self._processo.terminate()
                self._processo.join(timeout=1)
                if self._processo.is_alive():
                    self._processo.kill()
                    self._processo.join(timeout=1)
                self._conexao.close()
