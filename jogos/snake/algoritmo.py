"""BFS com simulação do corpo e teste do rabo; desvios sem colisão."""
from collections import deque
from heapq import heappop, heappush
from itertools import count
from random import Random
from .regras import ACOES, Jogo, adjacentes, caminho_bfs


def simular(corpo, rota, comida):
    corpo = list(corpo)
    for p in rota:
        cresce = p == comida
        if p in (corpo if cresce else corpo[:-1]):
            return None
        corpo.insert(0, p)
        if not cresce:
            corpo.pop()
    return corpo


def alcanca_rabo(corpo, n):
    return caminho_bfs(corpo[0], corpo[-1], corpo[1:-1], n) is not None


def avaliar_espaco(corpo, n):
    bloqueadas = set(corpo[1:-1])
    fila = deque([(corpo[0], 0)])
    vistos = {corpo[0]}
    maior = 0
    while fila:
        p, d = fila.popleft()
        maior = d
        for q in adjacentes(p, n):
            if q not in vistos and q not in bloqueadas:
                vistos.add(q)
                fila.append((q, d + 1))
    return n * n - len(bloqueadas) - len(vistos), maior


def rotas_curtas(corpo, comida, n, amostras=24):
    bloqueadas = set(corpo[1:])
    distancias = {comida: 0}
    fila = deque([comida])
    while fila:
        p = fila.popleft()
        for q in adjacentes(p, n):
            if q not in distancias and q not in bloqueadas:
                distancias[q] = distancias[p] + 1
                fila.append(q)
    if corpo[0] not in distancias:
        return
    sorteio = Random(sum((i + 1) * (x + n * y) for i, (x, y) in enumerate(corpo)) + comida[0] + n * comida[1])
    vistas = set()
    for i in range(amostras):
        p = corpo[0]
        rota = []
        while p != comida:
            opcoes = [q for q in adjacentes(p, n) if distancias.get(q) == distancias[p] - 1]
            p = opcoes[0] if i == 0 else sorteio.choice(opcoes)
            rota.append(p)
        chave = tuple(rota)
        if chave not in vistas:
            vistas.add(chave)
            yield rota


def alongar(rota, bloqueadas, n, limite=None):
    """Substitui arestas por desvios de três arestas, sem repetir casas."""
    rota = list(rota)
    usadas = set(rota) | set(bloqueadas)
    i = 0
    while i < len(rota) - 1 and (limite is None or len(rota) < limite):
        a, b = rota[i:i + 2]
        dx, dy = b[0] - a[0], b[1] - a[1]
        for sx, sy in ((-dy, dx), (dy, -dx)):
            c, d = (a[0] + sx, a[1] + sy), (b[0] + sx, b[1] + sy)
            if (0 <= c[0] < n and 0 <= c[1] < n and 0 <= d[0] < n and 0 <= d[1] < n
                    and c not in usadas and d not in usadas):
                rota[i + 1:i + 1] = [c, d]
                usadas.update((c, d))
                break
        else:
            i += 1
    return rota[1:]


class Algoritmo:
    def __init__(self):
        self._rota = deque()
        self._esperado = None
        self.estrategia = "BFS"

    def escolher(self, jogo: Jogo) -> str:
        assinatura = (tuple(jogo.corpo), jogo.comida, jogo.direcao)
        if assinatura != self._esperado:
            self._rota.clear()
        if not self._rota:
            self._rota.extend(self.planejar(jogo))
        if self._rota:
            destino = self._rota.popleft()
            for acao in ACOES:
                if jogo.destino(acao)[0] == destino and jogo.segura(acao):
                    corpo = simular(jogo.corpo, [destino], jogo.comida)
                    self._esperado = (tuple(corpo), jogo.comida, jogo.destino(acao)[1])
                    return acao
        self._esperado = None
        return next((a for a in ACOES if jogo.segura(a)), "straight")

    def busca_temporal(self, jogo, orcamento=600):
        """A* de configurações do corpo; respeita o prazo e testa a saída após comer."""
        corpo = tuple(jogo.corpo)
        comida, n = jogo.comida, jogo.nivel.tamanho
        prazo = jogo.nivel.limite - jogo.sem_comer
        distancia = lambda p: abs(p[0] - comida[0]) + abs(p[1] - comida[1])
        serial = count()
        fila = [(distancia(corpo[0]), 0, next(serial), corpo, ())]
        vistos = {corpo: 0}
        expandidos = 0
        while fila and expandidos < orcamento:
            _, tempo, _, corpo, rota = heappop(fila)
            expandidos += 1
            ocupadas = set(corpo[:-1])
            for p in adjacentes(corpo[0], n):
                if p in ocupadas or (p == corpo[-1] and p == comida):
                    continue
                passos = tempo + 1
                if passos + distancia(p) > prazo:
                    continue
                nova_rota = rota + (p,)
                if p == comida:
                    futuro = (p,) + corpo
                    if len(futuro) >= jogo.nivel.meta or alcanca_rabo(futuro, n):
                        return nova_rota
                    continue
                futuro = (p,) + corpo[:-1]
                if vistos.get(futuro, prazo + 1) <= passos:
                    continue
                vistos[futuro] = passos
                # Peso leve dá preferência a avançar sem explodir a fronteira.
                heappush(fila, (passos + 1.15 * distancia(p), passos, next(serial), futuro, nova_rota))
        return None

    def planejar(self, jogo):
        corpo, comida, n = jogo.corpo, jogo.comida, jogo.nivel.tamanho
        melhor = None
        def candidatas():
            yield from rotas_curtas(corpo, comida, n)
            for vizinho in adjacentes(comida, n):
                if vizinho in corpo[1:]:
                    continue
                if vizinho == corpo[0]:
                    continue
                for parcial in rotas_curtas(corpo + [comida], vizinho, n, amostras=8):
                    yield parcial + [comida]
        for rota in candidatas():
            if len(rota) > jogo.nivel.limite - jogo.sem_comer:
                continue
            futuro = simular(corpo, rota, comida)
            if futuro and (len(futuro) >= jogo.nivel.meta or alcanca_rabo(futuro, n)):
                risco, distancia = avaliar_espaco(futuro, n)
                valor = risco * n * n + max(0, distancia - jogo.nivel.limite) * n
                if melhor is None or valor < melhor[0]:
                    melhor = valor, rota
                if valor == 0:
                    self.estrategia = "BFS + teste do rabo e do espaço livre"
                    return rota
        if melhor is not None and melhor[0] > 0:
            # Desvios curtos liberam mais rabo antes de comer e evitam bolsões.
            inicial = melhor[1]
            prazo = jogo.nivel.limite - jogo.sem_comer
            for extra in range(2, min(prazo - len(inicial), 32) + 1, 2):
                variante = alongar([corpo[0]] + inicial, corpo[1:], n, len(inicial) + extra + 1)
                futuro = simular(corpo, variante, comida)
                if futuro and alcanca_rabo(futuro, n):
                    risco, distancia = avaliar_espaco(futuro, n)
                    valor = risco * n * n + max(0, distancia - jogo.nivel.limite) * n
                    if valor < melhor[0]:
                        melhor = valor, variante
                    if valor == 0:
                        self.estrategia = "BFS com desvio seguro antes de comer"
                        return variante
        if melhor is not None:
            self.estrategia = "BFS + teste do rabo"
            return melhor[1]
        temporal = self.busca_temporal(jogo)
        if temporal:
            self.estrategia = "busca temporal até a comida + teste do rabo"
            return temporal
        # O rabo se move; liberar sua casa permite acompanhar o corpo.
        rabo = caminho_bfs(corpo[0], corpo[-1], corpo[1:-1] + [comida], n)
        if rabo:
            self.estrategia = "caminho seguro até o rabo"
            longa = alongar([corpo[0]] + rabo, corpo[1:-1] + [comida], n)
            # Reavaliar a comida após cada passo de espera.
            if longa:
                return longa[:1]
        self.estrategia = "movimento seguro"
        candidatas = []
        for acao in ACOES:
            if jogo.segura(acao):
                p, _ = jogo.destino(acao)
                futuro = simular(corpo, [p], comida)
                distancia = abs(p[0] - comida[0]) + abs(p[1] - comida[1])
                candidatas.append((alcanca_rabo(futuro, n), -distancia, p))
        return [max(candidatas)[2]] if candidatas else []
