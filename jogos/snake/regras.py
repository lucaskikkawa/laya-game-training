"""Regras puras, coordenadas (x, y), corpo da cabeça ao rabo."""
from collections import deque
from dataclasses import dataclass
from secrets import randbelow
from typing import Iterable
from nucleo.contratos import Opcao, VOCABULARIO

Celula = tuple[int, int]
ACOES = ("straight", "left", "right")
DIRECOES = ((0, -1), (1, 0), (0, 1), (-1, 0))
NOMES_DIRECAO = ("north", "east", "south", "west")
OPCOES = (Opcao("straight", "Move self one cell forward."),
          Opcao("left", "Turn self left and move one cell."),
          Opcao("right", "Turn self right and move one cell."))


@dataclass(frozen=True)
class Nivel:
    tamanho: int
    meta: int
    limite: int


NIVEIS = {n: Nivel(n, meta, limite) for n, meta, limite in
          ((15, 50, 60), (20, 90, 80), (25, 140, 100))}
NIVEIS_ADIADOS = {30: Nivel(30, 200, 120)}


def adjacentes(p: Celula, n: int):
    x, y = p
    for dx, dy in DIRECOES:
        q = x + dx, y + dy
        if 0 <= q[0] < n and 0 <= q[1] < n:
            yield q


def caminho_bfs(inicio: Celula, fim: Celula, bloqueados: Iterable[Celula], n: int):
    """Retorna os destinos (sem início), None se inalcançável."""
    fila = deque([inicio])
    pais = {inicio: None}
    ocupadas = set(bloqueados) - {inicio}
    while fila:
        p = fila.popleft()
        if p == fim:
            rota = []
            while pais[p] is not None:
                rota.append(p)
                p = pais[p]
            return rota[::-1]
        for q in adjacentes(p, n):
            if q not in pais and q not in ocupadas:
                pais[q] = p
                fila.append(q)
    return None


def alcancaveis_no_prazo(corpo: list[Celula], n: int, limite: int) -> set[Celula]:
    """Busca (casa, tempo); segmento i libera no passo len(corpo)-i.

    Sem espera parada. Uma chegada posterior pode encontrar o rabo já livre,
    por isso não se eliminam casas visitadas em tempos anteriores.
    """
    bits = [1 << (y * n + x) for x, y in corpo]
    ocupadas = sum(bits)
    todas = (1 << (n * n)) - 1
    esquerda = sum(1 << (y * n) for y in range(n))
    direita = esquerda << (n - 1)
    fronteira = alcancadas = bits[0]
    for tempo in range(1, limite + 1):
        if tempo <= len(bits):
            ocupadas &= ~bits[-tempo]
        fronteira = (((fronteira & ~direita) << 1)
                     | ((fronteira & ~esquerda) >> 1)
                     | (fronteira << n) | (fronteira >> n)) & todas & ~ocupadas
        alcancadas |= fronteira
        if not fronteira:
            break
    return {(i % n, i // n) for i in range(n * n) if alcancadas & (1 << i)}


def metricas_espaco(corpo, n, comida=None):
    """Flood fill estático por bits; cabeça é origem, corpo inteiro bloqueia.

    Área conta só casas livres. Rabo é um destino permitido, sem atravessá-lo.
    """
    todas = (1 << (n * n)) - 1
    esquerda = sum(1 << (y * n) for y in range(n))
    direita = esquerda << (n - 1)

    def expandir(bits):
        return (((bits & ~direita) << 1) | ((bits & ~esquerda) >> 1)
                | (bits << n) | (bits >> n)) & todas

    ocupadas = sum(1 << (y * n + x) for x, y in corpo[1:])
    fronteira = vistos = 1 << (corpo[0][1] * n + corpo[0][0])
    alvo = 1 << (comida[1] * n + comida[0]) if comida is not None else 0
    distancia = 0 if fronteira & alvo else None
    profundidade = 0
    while fronteira:
        profundidade += 1
        fronteira = expandir(fronteira) & ~ocupadas & ~vistos
        if distancia is None and fronteira & alvo:
            distancia = profundidade
        vistos |= fronteira
    rabo = 1 << (corpo[-1][1] * n + corpo[-1][0])
    return {"area_alcancavel": vistos.bit_count() - 1,
            "distancia_bfs_comida": distancia,
            "rabo_alcancavel": bool((expandir(vistos) | vistos) & rabo)}


def alcanca_livre_no_prazo(corpo, n, prazo):
    """Há uma casa atualmente livre alcançável antes da fome?

    Entrar apenas no rabo não basta: o corpo pode fechar toda a região.
    A fronteira temporal permite revisitas e encerra na primeira casa livre.
    """
    bits = [1 << (y * n + x) for x, y in corpo]
    ocupadas = bloqueadas = sum(bits)
    todas = (1 << (n * n)) - 1
    esquerda = sum(1 << (y * n) for y in range(n))
    direita = esquerda << (n - 1)
    fronteira = bits[0]
    for tempo in range(1, prazo + 1):
        if tempo <= len(bits):
            bloqueadas &= ~bits[-tempo]
        fronteira = (((fronteira & ~direita) << 1)
                     | ((fronteira & ~esquerda) >> 1)
                     | (fronteira << n) | (fronteira >> n)) & todas & ~bloqueadas
        if fronteira & ~ocupadas:
            return True
        if not fronteira:
            break
    return False


def lista_comidas(n: int, quantidade: int = 20000) -> list[Celula]:
    return [(randbelow(n), randbelow(n)) for _ in range(quantidade)]


class Jogo:
    def __init__(self, nivel: int = 15, comidas: Iterable[Celula] | None = None):
        self.nivel = NIVEIS[nivel]
        meio = nivel // 2
        self.corpo = [(meio, meio), (meio - 1, meio), (meio - 2, meio)]
        self.direcao = 1
        self.comidas = list(comidas) if comidas is not None else lista_comidas(nivel)
        if any(len(p) != 2 or not all(isinstance(v, int) for v in p)
               or not all(0 <= v < nivel for v in p) for p in self.comidas):
            raise ValueError("Lista de comidas contém coordenadas inválidas")
        self.comidas = [tuple(p) for p in self.comidas]
        self.indice_comida = 0
        self.comida = None
        self.pulos = []
        self.comidas_efetivas = []
        self.pontos = self.passos = self.sem_comer = self.comidas_consumidas = 0
        self.ideal_comida = None
        self.fim = False
        self.vitoria = False
        self.morte = None
        self._nova_comida()

    def _nova_comida(self):
        self.comida = None
        ocupadas = set(self.corpo)
        alcancaveis = alcancaveis_no_prazo(self.corpo, self.nivel.tamanho, self.nivel.limite)
        # Verificar o estado uma vez, antes de consumir índices da lista salva.
        if not alcancaveis - ocupadas:
            self.fim = True
            self.morte = "sem_comida_valida"
            return
        area = None
        while self.indice_comida < len(self.comidas):
            p = self.comidas[self.indice_comida]
            self.indice_comida += 1
            motivo = "ocupada" if p in ocupadas else "inalcancavel" if p not in alcancaveis else None
            if motivo:
                if area is None:
                    area = metricas_espaco(self.corpo, self.nivel.tamanho)["area_alcancavel"]
                self.pulos.append({"indice": self.indice_comida - 1, "posicao": p,
                                   "motivo": motivo, "passo": self.passos, "area_alcancavel": area})
            else:
                self.comida = p
                self.comidas_efetivas.append({"indice": self.indice_comida - 1,
                                             "posicao": p, "passo": self.passos})
                rota = caminho_bfs(self.corpo[0], p, self.corpo[1:], self.nivel.tamanho)
                self.ideal_comida = len(rota) if rota is not None else None
                return
        # Nunca sortear fora da lista registrada.
        self.fim = True
        self.morte = "lista_esgotada"

    def destino(self, acao: str):
        if acao not in ACOES:
            raise ValueError(f"Ação inválida: {acao}")
        direcao = (self.direcao + {"straight": 0, "left": -1, "right": 1}[acao]) % 4
        dx, dy = DIRECOES[direcao]
        x, y = self.corpo[0]
        return (x + dx, y + dy), direcao

    def segura(self, acao: str) -> bool:
        p, _ = self.destino(acao)
        n = self.nivel.tamanho
        # O rabo sai neste mesmo passo, salvo quando se come.
        corpo = self.corpo if p == self.comida else self.corpo[:-1]
        return 0 <= p[0] < n and 0 <= p[1] < n and p not in corpo

    def passo(self, acao: str) -> int:
        if self.fim:
            raise RuntimeError("A partida já terminou")
        p, direcao = self.destino(acao)
        segura = self.segura(acao)
        self.passos += 1
        self.sem_comer += 1
        self.direcao = direcao
        if not segura:
            self.fim = True
            n = self.nivel.tamanho
            self.morte = "parede" if not (0 <= p[0] < n and 0 <= p[1] < n) else "corpo"
            return 0
        self.corpo.insert(0, p)
        pontos = 0
        if p == self.comida:
            # BFS impossível ao aparecer: não há excesso mensurável; registrar None.
            excesso = max(0, self.sem_comer - self.ideal_comida) if self.ideal_comida is not None else 0
            pontos = max(10, 100 - 10 * excesso)
            self.pontos += pontos
            self.comidas_consumidas += 1
            self.sem_comer = 0
            if len(self.corpo) >= self.nivel.meta:
                self.fim = self.vitoria = True
                self.comida = None
            else:
                self._nova_comida()
        else:
            self.corpo.pop()
            if self.sem_comer >= self.nivel.limite:
                self.fim = True
                self.morte = "limite_sem_comer"
        return pontos

    def estado(self) -> str:
        n = self.nivel.tamanho
        mapa = [["."] * n for _ in range(n)]
        for x, y in self.corpo[1:-1]:
            mapa[y][x] = "B"
        x, y = self.corpo[-1]
        mapa[y][x] = "T"
        x, y = self.corpo[0]
        mapa[y][x] = "H"
        if self.comida is not None:
            x, y = self.comida
            mapa[y][x] = "F"
        return (f"Direction: {NOMES_DIRECAO[self.direcao]}.\n"
                "H=self head; B=body danger; T=tail; F=reward; .=free space; walls=danger.\n"
                f"{VOCABULARIO}\n" + "\n".join("".join(linha) for linha in mapa))

    def resumo(self) -> dict:
        return {"pontos": self.pontos, "passos": self.passos, "gomos": len(self.corpo),
                "vitoria": self.vitoria, "morte": self.morte, "comidas": self.comidas_consumidas}
