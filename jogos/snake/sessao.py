"""Runs pareadas e auditoria JSON; nenhuma dependência de modelo ou interface."""
from datetime import datetime
import json
from pathlib import Path
from time import perf_counter
from nucleo.config import raiz
from .algoritmo import Algoritmo
from .regras import Jogo, OPCOES, lista_comidas, NIVEIS


def salvar_json(caminho: Path, dados):
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(caminho)


def comparar(registros, laya, algoritmo):
    acordos = [r["escolha"] == r["jogada_ideal"] for r in registros]
    return {"geral": {"laya": laya, "algoritmo": algoritmo,
                      "diferenca_pontos": laya["pontos"] - algoritmo["pontos"],
                      "diferenca_passos": laya["passos"] - algoritmo["passos"]},
            "passo_a_passo": [{"passo": i + 1, "concorda": c} for i, c in enumerate(acordos)],
            "concordancia": sum(acordos) / len(acordos) if acordos else 0.0}


class Sessao:
    def __init__(self, decisor, nivel=15, partidas=1, versao="v000", pasta=None, comidas=None, modo="normal"):
        if partidas < 1:
            raise ValueError("Partidas deve ser positivo")
        if nivel not in NIVEIS:
            raise ValueError("Nível inválido")
        self.decisor = decisor
        self.nivel, self.partidas, self.versao = nivel, partidas, versao
        data = datetime.now().strftime("%Y-%m-%d_%H-%M")
        base = Path(pasta) if pasta else raiz() / "runs"
        base.mkdir(parents=True, exist_ok=True)
        self.pasta = base / f"Laya_{data}"
        sufixo = 1
        while True:
            try:
                self.pasta.mkdir()
                break
            except FileExistsError:
                self.pasta = base / f"Laya_{data}_{sufixo:02d}"
                sufixo += 1
        self.comidas = list(comidas) if comidas is not None else lista_comidas(
            nivel, max(20000, partidas * NIVEIS[nivel].meta * 6))
        self.cursor = 0
        self.indice = 0
        self.resultados = []
        self.jogo = None
        self._run_ativa = False
        self.registros = []
        self._oraculo = Algoritmo()
        self.inicio = perf_counter()
        self.documento = {"schema": "snake-v0.1", "gabarito_certificado": False, "criada_em": datetime.now().isoformat(),
                          "placar": "Laya_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                          "nivel": nivel, "versao": versao, "modo": modo, "partidas_pedidas": partidas,
                          "comidas": self.comidas, "resultados": self.resultados, "status": "em_andamento"}
        self._salvar()

    def _salvar(self):
        self.documento["segundos"] = perf_counter() - self.inicio
        if hasattr(self.decisor, "telemetria"):
            self.documento["hardware"] = self.decisor.telemetria()
        salvar_json(self.pasta / "sessao.json", self.documento)
        salvar_json(self.pasta / f"{self.documento['placar']}.json", {
            "nome": self.documento["placar"], "nivel": self.nivel, "versao": self.versao,
            "runs": [{"run": r["run"], **r["comparacao"]["geral"]["laya"],
                      "concordancia": r["comparacao"]["concordancia"]} for r in self.resultados]})

    @property
    def concluida(self):
        return self.indice >= self.partidas

    def iniciar_run(self):
        if self.concluida:
            raise RuntimeError("Sessão concluída")
        if self._run_ativa:
            raise RuntimeError("Finalize a run atual antes de iniciar outra")
        self.jogo = Jogo(self.nivel, self.comidas[self.cursor:])
        self.registros = []
        self._oraculo = Algoritmo()
        self.inicio_run = perf_counter()
        self._run_ativa = True
        return self.jogo

    def passo(self):
        if self.jogo is None or self.jogo.fim:
            raise RuntimeError("Inicie uma run antes de jogar")
        jogo = self.jogo
        estado = jogo.estado()
        ideal = self._oraculo.escolher(jogo)
        decisao = self.decisor.decidir(estado, OPCOES)
        registro = {"passo": jogo.passos + 1, "estado": estado,
                    "direcao": jogo.direcao, "corpo": list(jogo.corpo), "comida": jogo.comida,
                    "indice_comida": self.cursor + jogo.indice_comida - 1,
                    "ideal_bfs_ao_aparecer": jogo.ideal_comida, "passos_sem_comer": jogo.sem_comer,
                    "probabilidades": decisao.probabilidades, "escolha": decisao.escolha,
                    "confianca": decisao.confianca, "jogada_ideal": ideal,
                    "latencia_ms": decisao.latencia_ms}
        registro["pontos_ganhos"] = jogo.passo(decisao.escolha)
        registro["pontos"] = jogo.pontos
        self.registros.append(registro)
        return registro

    def _dados_laya(self, status="concluida"):
        segundos = perf_counter() - self.inicio_run
        return {"status": status, "inicio_lista": self.cursor, "passos": self.registros,
                "resumo": self.jogo.resumo(), "segundos": segundos,
                "passos_por_segundo": self.jogo.passos / segundos if segundos else 0,
                "latencia_media_ms": sum(r["latencia_ms"] for r in self.registros) / max(1, len(self.registros))}

    def finalizar_run(self):
        if not self._run_ativa or self.jogo is None or not self.jogo.fim:
            raise RuntimeError("Não há run terminada para finalizar")
        identificador = f"run_{self.indice + 1:04d}"
        laya = self._dados_laya()
        salvar_json(self.pasta / f"{identificador}_laya.json", laya)
        # Run independente: mesmas regras, mesma posição inicial e mesmo início da lista.
        gabarito = Jogo(self.nivel, self.comidas[self.cursor:])
        algoritmo = Algoritmo()
        passos = []
        inicio = perf_counter()
        while not gabarito.fim:
            acao = algoritmo.escolher(gabarito)
            passos.append({"passo": gabarito.passos + 1, "estado": gabarito.estado(), "escolha": acao,
                           "estrategia": algoritmo.estrategia})
            gabarito.passo(acao)
        tempo = perf_counter() - inicio
        salvar_json(self.pasta / f"{identificador}_algoritmo.json", {
            "inicio_lista": self.cursor, "passos": passos, "resumo": gabarito.resumo(),
            "segundos": tempo, "passos_por_segundo": gabarito.passos / max(tempo, 1e-9)})
        comparacao = comparar(self.registros, self.jogo.resumo(), gabarito.resumo())
        salvar_json(self.pasta / f"{identificador}_comparacao.json", comparacao)
        resultado = {"run": self.indice + 1, "inicio_lista": self.cursor,
                     "comparacao": comparacao, "passos_por_segundo": laya["passos_por_segundo"],
                     "latencia_media_ms": laya["latencia_media_ms"]}
        self.resultados.append(resultado)
        self.cursor += max(self.jogo.indice_comida, gabarito.indice_comida)
        self.indice += 1
        self._run_ativa = False
        if self.concluida:
            self.documento["status"] = "concluida"
        self._salvar()
        return resultado

    def interromper(self, erro=None):
        if self.concluida:
            return
        if self._run_ativa and self.registros:
            salvar_json(self.pasta / f"run_{self.indice + 1:04d}_laya_parcial.json", self._dados_laya("interrompida"))
        self._run_ativa = False
        # Fechar a janela depois de um erro não deve apagar a causa original.
        if erro is not None or self.documento["status"] != "erro":
            self.documento["status"] = "erro" if erro is not None else "interrompida"
            self.documento["erro"] = str(erro) if erro is not None else None
        self._salvar()
