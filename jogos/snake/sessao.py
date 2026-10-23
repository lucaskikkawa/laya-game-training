"""Runs pareadas e auditoria JSON; nenhuma dependência de modelo ou interface."""
from datetime import datetime
from concurrent.futures import CancelledError
import gzip
import json
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import perf_counter
from nucleo.config import raiz
from .algoritmo import Algoritmo
from .regras import Jogo, OPCOES, lista_comidas, NIVEIS, metricas_espaco


def salvar_json(caminho: Path, dados):
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(caminho)


def commit_codigo():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2],
                              capture_output=True, text=True, check=True, timeout=2).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def versao_pacote_laya():
    try:
        return version("laya")
    except PackageNotFoundError:
        return None


def escrever_passo(arquivo, registro):
    arquivo.write(json.dumps({k: v for k, v in registro.items() if k != "estado"},
                             ensure_ascii=False, separators=(",", ":")) + "\n")


def snapshot(jogo, inicio_lista):
    return {"passo": jogo.passos, "cabeca": jogo.corpo[0], "corpo": list(jogo.corpo),
            "direcao": jogo.direcao, "comida": jogo.comida,
            "indice_comida": inicio_lista + jogo.indice_comida - 1 if jogo.comida is not None else None,
            "passos_sem_comer": jogo.sem_comer,
            "restante_limite": max(0, jogo.nivel.limite - jogo.sem_comer)}


def termino(jogo):
    if jogo.vitoria:
        return "vitoria"
    return "fome" if jogo.morte == "limite_sem_comer" else jogo.morte


def comparar(registros, laya, algoritmo, passos_algoritmo=(), *,
             pulos_laya=(), pulos_algoritmo=(), comidas_laya=(), comidas_algoritmo=(), arquivos_passos=None):
    acordos = [r["escolha"] == r["jogada_ideal"] for r in registros]
    sequencias = [[(c["indice"], tuple(c["posicao"])) for c in comidas]
                  for comidas in (comidas_laya, comidas_algoritmo)]
    divergencia = next((i for i in range(max(map(len, sequencias)))
                       if i >= len(sequencias[0]) or i >= len(sequencias[1])
                       or sequencias[0][i] != sequencias[1][i]), None)
    return {"pulos": {"laya": list(pulos_laya), "algoritmo": list(pulos_algoritmo)},
            "comidas_efetivas": {"laya": list(comidas_laya), "algoritmo": list(comidas_algoritmo)},
            "divergencia_comidas": divergencia,
            "aviso": (f"Sequências de comidas efetivas divergem a partir do índice {divergencia} (base zero)."
                      if divergencia is not None else None),
            "geral": {"laya": laya, "algoritmo": algoritmo,
                      "diferenca_pontos": laya["pontos"] - algoritmo["pontos"],
                      "diferenca_passos": laya["passos"] - algoritmo["passos"]},
            # O gabarito local avalia o estado do Laya. A partida independente
            # pode divergir e durar mais; conservar as duas linhas até o fim.
            "passo_a_passo": arquivos_passos if arquivos_passos is not None else [
                {"passo": i + 1,
                 "concorda": acordos[i] if i < len(acordos) else None,
                 "laya": registros[i] if i < len(registros) else None,
                 "algoritmo": passos_algoritmo[i] if i < len(passos_algoritmo) else None}
                for i in range(max(len(registros), len(passos_algoritmo)))],
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
        self.metadados = {"commit_codigo": commit_codigo(), "nivel": nivel, "versao_laya": versao,
                          "versao_pacote_laya": versao_pacote_laya(), "arquivo_comidas": "comidas.json"}
        salvar_json(self.pasta / "comidas.json", self.comidas)
        self._arquivo_laya = None
        self.documento = {"schema": "snake-v0.2", **self.metadados, "gabarito_certificado": False, "criada_em": datetime.now().isoformat(),
                          "valida_para_treino": True, "motivo": None,
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
        self._nome_passos_laya = f"run_{self.indice + 1:04d}_laya.jsonl.gz"
        self._arquivo_laya = gzip.open(self.pasta / self._nome_passos_laya, "wt", encoding="utf-8", compresslevel=1)
        return self.jogo

    def passo(self):
        if not self._run_ativa or self.jogo is None or self.jogo.fim:
            raise RuntimeError("Inicie uma run antes de jogar")
        try:
            return self._passo()
        except CancelledError:
            self.interromper()
            raise
        except Exception as exc:
            self.interromper(exc)
            raise

    def _passo(self):
        jogo = self.jogo
        estado = jogo.estado()
        ideal = self._oraculo.escolher(jogo)
        decisao = self.decisor.decidir(estado, OPCOES)
        registro = self._registro(jogo)
        registro.update({"estado": estado, "probabilidades": dict(decisao.probabilidades),
                         "escolha": decisao.escolha, "confianca": decisao.confianca,
                         "jogada_ideal": ideal, "concorda": decisao.escolha == ideal,
                         "estrategia": "decisao_modelo", "motivo": "Escolha do Laya a partir do estado e das opções",
                         "estrategia_ideal": self._oraculo.estrategia,
                         "latencia_ms": decisao.latencia_ms})
        registro["pontos_ganhos"] = jogo.passo(decisao.escolha)
        registro["pontos"] = jogo.pontos
        escrever_passo(self._arquivo_laya, registro)
        self.registros.append({k: registro[k] for k in ("escolha", "jogada_ideal", "latencia_ms")})
        return registro

    def _registro(self, jogo):
        return {**snapshot(jogo, self.cursor), "passo": jogo.passos + 1,
                "ideal_bfs_ao_aparecer": jogo.ideal_comida,
                **metricas_espaco(jogo.corpo, jogo.nivel.tamanho, jogo.comida)}

    def _fechar_passos_laya(self):
        if self._arquivo_laya is not None:
            self._arquivo_laya.close()
            self._arquivo_laya = None

    def _fim_run(self, jogo, motivo=None):
        return {"schema": "snake-v0.2", **self.metadados,
                "motivo_termino": motivo or termino(jogo),
                "snapshot_final": {**snapshot(jogo, self.cursor), "estado": jogo.estado()},
                "resumo": jogo.resumo()}

    def _auditoria_comidas(self, jogo):
        # Jogo usa índices locais; arquivos usam a lista completa da sessão.
        return {campo: [{**r, "indice": self.cursor + r["indice"]} for r in getattr(jogo, campo)]
                for campo in ("pulos", "comidas_efetivas")}

    def _dados_laya(self, status="concluida"):
        segundos = perf_counter() - self.inicio_run
        return {**self._auditoria_comidas(self.jogo), "status": status, "inicio_lista": self.cursor, "passos": self._nome_passos_laya,
                **self._fim_run(self.jogo, "erro" if status == "interrompida" else None), "segundos": segundos,
                "passos_por_segundo": self.jogo.passos / segundos if segundos else 0,
                "latencia_media_ms": sum(r["latencia_ms"] for r in self.registros) / max(1, len(self.registros))}

    def finalizar_run(self):
        if not self._run_ativa or self.jogo is None or not self.jogo.fim:
            raise RuntimeError("Não há run terminada para finalizar")
        identificador = f"run_{self.indice + 1:04d}"
        self._fechar_passos_laya()
        laya = self._dados_laya()
        salvar_json(self.pasta / f"{identificador}_laya.json", laya)
        # O Laya já terminou: uma falha do gabarito não deve reclassificá-lo
        # como interrompido nem criar uma segunda versão parcial desta run.
        self._run_ativa = False
        # Run independente: mesmas regras, mesma posição inicial e mesmo início da lista.
        gabarito = Jogo(self.nivel, self.comidas[self.cursor:])
        inicio = perf_counter()
        nome_passos_algoritmo = f"{identificador}_algoritmo.jsonl.gz"
        try:
            with gzip.open(self.pasta / nome_passos_algoritmo, "wt", encoding="utf-8", compresslevel=1) as arquivo:
                algoritmo = Algoritmo()
                while not gabarito.fim:
                    inicio_passo = perf_counter()
                    acao = algoritmo.escolher(gabarito)
                    latencia = (perf_counter() - inicio_passo) * 1000
                    registro = {**self._registro(gabarito), "escolha": acao,
                                "estrategia": algoritmo.estrategia, "motivo": algoritmo.estrategia,
                                "latencia_ms": latencia}
                    registro["pontos_ganhos"] = gabarito.passo(acao)
                    registro["pontos"] = gabarito.pontos
                    escrever_passo(arquivo, registro)
        except Exception as exc:
            self.documento["erro"] = f"{type(exc).__name__}: {exc}"
            self.documento["valida_para_treino"] = False
            self.documento["motivo"] = "algoritmo_perdeu"
            self.documento["status"] = "erro"
            self._salvar()
            salvar_json(self.pasta / f"{identificador}_algoritmo.json", {
                **self._fim_run(gabarito, "erro"), **self._auditoria_comidas(gabarito),
                "status": "erro", "erro": self.documento["erro"],
                "inicio_lista": self.cursor, "passos": nome_passos_algoritmo})
            raise
        tempo = perf_counter() - inicio
        # A invalidação é da sessão inteira e persiste nas próximas runs.
        if not gabarito.vitoria:
            self.documento["valida_para_treino"] = False
            self.documento["motivo"] = "algoritmo_perdeu"
            self._salvar()
        salvar_json(self.pasta / f"{identificador}_algoritmo.json", {
            **self._auditoria_comidas(gabarito),
            "inicio_lista": self.cursor, "passos": nome_passos_algoritmo,
            "status": "concluida", **self._fim_run(gabarito),
            "segundos": tempo, "passos_por_segundo": gabarito.passos / max(tempo, 1e-9)})
        auditoria_algoritmo = self._auditoria_comidas(gabarito)
        comparacao = comparar(self.registros, self.jogo.resumo(), gabarito.resumo(),
                             pulos_laya=laya["pulos"], pulos_algoritmo=auditoria_algoritmo["pulos"],
                             comidas_laya=laya["comidas_efetivas"],
                             comidas_algoritmo=auditoria_algoritmo["comidas_efetivas"],
                             arquivos_passos={"laya": self._nome_passos_laya,
                                              "algoritmo": nome_passos_algoritmo})
        comparacao["valida_para_treino"] = self.documento["valida_para_treino"]
        comparacao["motivo"] = self.documento["motivo"]
        salvar_json(self.pasta / f"{identificador}_comparacao.json", comparacao)
        resultado = {"run": self.indice + 1, "inicio_lista": self.cursor,
                     "comparacao": comparacao, "passos_por_segundo": laya["passos_por_segundo"],
                     "latencia_media_ms": laya["latencia_media_ms"]}
        # Falhas de infraestrutura/lista também nunca alimentam o treino.
        if any(termino(g) in {"lista_esgotada", "sem_comida_valida", "erro"} for g in (self.jogo, gabarito)):
            self.documento["valida_para_treino"] = False
            self.documento["motivo"] = self.documento["motivo"] or termino(self.jogo)
            comparacao["valida_para_treino"] = False
            comparacao["motivo"] = self.documento["motivo"]
            salvar_json(self.pasta / f"{identificador}_comparacao.json", comparacao)
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
        if self._run_ativa and self.jogo is not None:
            self._fechar_passos_laya()
            salvar_json(self.pasta / f"run_{self.indice + 1:04d}_laya_parcial.json", {**self._dados_laya("interrompida"),
                "erro": f"{type(erro).__name__}: {erro}" if erro is not None else None})
        self._run_ativa = False
        # Fechar a janela depois de um erro não deve apagar a causa original.
        if erro is not None or self.documento["status"] != "erro":
            self.documento["status"] = "erro" if erro is not None else "interrompida"
            self.documento["erro"] = str(erro) if erro is not None else None
        self._salvar()
