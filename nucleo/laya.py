"""Adaptador da API laya 0.4.13 (Agent/load/system_one). Imports preguiçosos."""
import math
from time import perf_counter
from .config import modelo
from .contratos import Decisao, Opcao


class Laya:
    def __init__(self, versao: str = "v000", cpu: bool = False):
        self.versao = versao
        self.cpu = cpu
        self.agent = None
        self.dispositivo = "não carregado"
        self.gpu = ""
        self.carregamento_ms = 0.0
        self._torch = None

    def carregar(self):
        if self.agent is not None:
            return
        inicio = perf_counter()
        origem = modelo(self.versao)
        import torch
        import laya
        self._torch = torch
        device = "cuda" if not self.cpu and torch.cuda.is_available() else "cpu"
        # load já trata falha de alocação CUDA com fallback CPU.
        # load retorna um Agent. Router faz seleção de idioma/checkpoint e não é
        # necessário aqui: cada run deve usar exatamente a versão selecionada.
        self.agent = laya.load(origem, device=device)
        self.dispositivo = str(self.agent.device)
        if self.dispositivo.startswith("cuda"):
            # Agent usa autocast; preservar pesos fp32 é necessário ao fallback CPU.
            self.agent.dtype = torch.float16
            self.agent.amp_enabled = True
            self.gpu = torch.cuda.get_device_name(self.agent.device)
        self.carregamento_ms = (perf_counter() - inicio) * 1000

    def telemetria(self) -> dict:
        # O Agent pode permanecer em CPU depois de um fallback durante inferência.
        if self.agent is not None:
            self.dispositivo = str(self.agent.device)
            if not self.dispositivo.startswith("cuda"):
                self.gpu = ""
        dados = {"dispositivo": self.dispositivo, "gpu": self.gpu,
                 "precisao": str(getattr(self.agent, "dtype", "")),
                 "carregamento_ms": self.carregamento_ms}
        if self.dispositivo.startswith("cuda"):
            cuda = self._torch.cuda
            dados["vram_alocada_mb"] = cuda.memory_allocated(self.agent.device) / 2**20
            dados["vram_reservada_mb"] = cuda.memory_reserved(self.agent.device) / 2**20
            dados["vram_total_mb"] = cuda.get_device_properties(self.agent.device).total_memory / 2**20
        return dados

    def decidir(self, estado: str, opcoes: tuple[Opcao, ...]) -> Decisao:
        if len(opcoes) != 3 or len({o.id for o in opcoes}) != 3:
            raise ValueError("São necessárias três opções distintas")
        self.carregar()
        perguntas = {"move": {"type": "choice", "instructions":
            "Choose the effect that keeps self alive and reaches reward efficiently.",
            "criteria": {o.id: o.efeito for o in opcoes}}}
        inicio = perf_counter()
        resposta = self.agent.system_one(estado, questions=perguntas, lang="en")
        latencia = (perf_counter() - inicio) * 1000
        if resposta.get("usage", {}).get("truncated"):
            raise RuntimeError("O estado foi truncado pelo Laya; a run não pode continuar com mapa incompleto.")
        try:
            resposta = resposta["answers"]["move"]
            if set(resposta["probabilities"]) != {o.id for o in opcoes}:
                raise ValueError("Probabilidades devem conter as três opções")
            probs = {o.id: float(resposta["probabilities"][o.id]) for o in opcoes}
            escolha = resposta["choice"]
            confianca = float(resposta["confidence"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Resposta choice inválida recebida do Laya") from exc
        if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probs.values()):
            raise ValueError("Probabilidades inválidas recebidas do Laya")
        total = sum(probs.values())
        if total <= 0 or not isinstance(escolha, str) or escolha not in probs:
            raise ValueError("Resposta choice inválida recebida do Laya")
        # A biblioteca arredonda quatro casas; normalizar a soma para o registro/painel.
        probs = {k: v / total for k, v in probs.items()}
        if not math.isfinite(confianca) or not 0 <= confianca <= 1:
            raise ValueError("Confiança inválida recebida do Laya")
        return Decisao(probs, escolha, confianca, latencia)
