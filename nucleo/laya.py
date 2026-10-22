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
        self.agent = laya.load(origem, device=device)
        self.dispositivo = str(self.agent.device)
        if self.dispositivo.startswith("cuda"):
            # Agent usa autocast; preservar pesos fp32 é necessário ao fallback CPU.
            self.agent.dtype = torch.float16
            self.agent.amp_enabled = True
            self.gpu = torch.cuda.get_device_name(self.agent.device)
        self.carregamento_ms = (perf_counter() - inicio) * 1000

    def telemetria(self) -> dict:
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
        self.carregar()
        perguntas = {"move": {"type": "choice", "instructions":
            "Choose the effect that keeps self alive and reaches reward efficiently.",
            "criteria": {o.id: o.efeito for o in opcoes}}}
        inicio = perf_counter()
        resposta = self.agent.system_one(estado, questions=perguntas, lang="en")
        latencia = (perf_counter() - inicio) * 1000
        if resposta.get("usage", {}).get("truncated"):
            raise RuntimeError("O estado foi truncado pelo Laya; a run não pode continuar com mapa incompleto.")
        resposta = resposta["answers"]["move"]
        probs = {o.id: float(resposta["probabilities"][o.id]) for o in opcoes}
        if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probs.values()):
            raise ValueError("Probabilidades inválidas recebidas do Laya")
        total = sum(probs.values())
        if total <= 0 or resposta["choice"] not in probs:
            raise ValueError("Resposta choice inválida recebida do Laya")
        # A biblioteca arredonda quatro casas; normalizar a soma para o registro/painel.
        probs = {k: v / total for k, v in probs.items()}
        confianca = float(resposta["confidence"])
        if not math.isfinite(confianca) or not 0 <= confianca <= 1:
            raise ValueError("Confiança inválida recebida do Laya")
        return Decisao(probs, resposta["choice"], confianca, latencia)
