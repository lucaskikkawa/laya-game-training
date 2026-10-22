"""BFS com simulação do corpo e teste do rabo; desvios sem colisão."""
from collections import deque
from heapq import heappop, heappush
from itertools import count
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
        self.estrategia = "BFS e conectividade do espaço livre"
        self._n = None

    def configurar(self, n):
        self._n = n
        self._todas = (1 << (n*n)) - 1
        self._esquerda = sum(1 << (y*n) for y in range(n))
        self._direita = self._esquerda << (n-1)
        self._nao_esquerda = self._todas ^ self._esquerda
        self._nao_direita = self._todas ^ self._direita
        self._bits = {(x,y): 1 << (y*n+x) for y in range(n) for x in range(n)}
        self._linhas = [((1 << n)-1) << (y*n) for y in range(n)]
        self._colunas = [self._esquerda << x for x in range(n)]
        self._vizinhos = [tuple(y * n + x for x, y in adjacentes((i % n, i // n), n))
                          for i in range(n * n)]
        self._visitadas = {}
        self._comida = None
        self._rota = deque()
        self._esperado = None

    def expandir(self, bits):
        return (((bits & self._nao_direita) << 1) |
                ((bits & self._nao_esquerda) >> 1) |
                (bits << self._n) | (bits >> self._n)) & self._todas

    def avaliar(self, inicio, livres, comida):
        vistos = fronteira = inicio
        distancia = 0 if inicio == comida else None
        profundidade = 0
        while fronteira:
            profundidade += 1
            fronteira = self.expandir(fronteira) & livres & ~vistos
            if distancia is None and fronteira & comida:
                distancia = profundidade
            vistos |= fronteira
        return vistos, distancia, profundidade - 1

    def caminho(self, corpo, alvo, prazo):
        ocupadas = 0
        for p in corpo:
            ocupadas |= self._bits[p]
        liberadas = [self._bits[p] for p in reversed(corpo)]
        inicio = self._bits[corpo[0]]
        alvo_bit = self._bits[alvo]
        vistos = fronteira = inicio
        camadas = [inicio]
        for t in range(1, prazo + 1):
            if t <= len(corpo):
                ocupadas &= ~liberadas[t-1]
            fronteira = self.expandir(fronteira) & ~ocupadas & ~vistos
            if not fronteira:
                return None
            camadas.append(fronteira)
            vistos |= fronteira
            if fronteira & alvo_bit:
                p = alvo_bit
                rota = [alvo]
                for camada in reversed(camadas[:-1]):
                    opcoes = self.expandir(p) & camada
                    p = opcoes & -opcoes
                    i = p.bit_length() - 1
                    rota.append((i % self._n, i // self._n))
                return rota[-2::-1]
        return None

    def concavidade(self, ocupadas):
        total = 0
        for mascara in self._linhas:
            bits = ocupadas & mascara
            if bits:
                total += bits.bit_length() - (bits & -bits).bit_length() + 1 - bits.bit_count()
        for mascara in self._colunas:
            bits = ocupadas & mascara
            if bits:
                total += (bits.bit_length() - (bits & -bits).bit_length()) // self._n + 1 - bits.bit_count()
        return total

    def concavidade_apos_passo(self, antes, depois, rabo, cabeca, valor):
        """Só as linhas/colunas do rabo e da nova cabeça podem mudar."""
        def lacunas(bits, passo):
            if not bits:
                return 0
            return (bits.bit_length() - (bits & -bits).bit_length()) // passo + 1 - bits.bit_count()

        for y in {rabo[1], cabeca[1]}:
            mascara = self._linhas[y]
            valor += lacunas(depois & mascara, 1) - lacunas(antes & mascara, 1)
        for x in {rabo[0], cabeca[0]}:
            mascara = self._colunas[x]
            valor += lacunas(depois & mascara, self._n) - lacunas(antes & mascara, self._n)
        return valor

    def gargalos(self, livres):
        """Conta articulações: casas cuja ocupação separaria o espaço livre."""
        ordem = [-1] * (self._n * self._n)
        baixo = [0] * len(ordem)
        relogio = count()
        cortes = set()

        def visitar(p, pai):
            ordem[p] = baixo[p] = next(relogio)
            filhos = 0
            for q in self._vizinhos[p]:
                if not livres & (1 << q):
                    continue
                if ordem[q] == -1:
                    filhos += 1
                    visitar(q, p)
                    baixo[p] = min(baixo[p], baixo[q])
                    if pai != -1 and baixo[q] >= ordem[p]:
                        cortes.add(p)
                elif q != pai:
                    baixo[p] = min(baixo[p], ordem[q])
            if pai == -1 and filhos > 1:
                cortes.add(p)

        if livres:
            visitar((livres & -livres).bit_length() - 1, -1)
        return len(cortes)

    def pontuar(self, corpo, rota, comida, meta, limite):
        futuro = simular(corpo, rota, comida)
        if futuro is None:
            return None
        if len(futuro) >= meta:
            return (True, 0, -len(rota))
        ocupadas = 0
        for p in futuro:
            ocupadas |= self._bits[p]
        livres = self._todas & ~ocupadas
        adj = self.expandir(self._bits[futuro[0]]) & livres
        if not adj:
            return None
        inicio = adj & -adj
        vistos, _, _ = self.avaliar(inicio, livres, 0)
        if not self.expandir(vistos) & self._bits[futuro[-1]]:
            return None
        risco = livres.bit_count() - vistos.bit_count()
        a = (livres & self._nao_direita) << 1
        b = (livres & self._nao_esquerda) >> 1
        c = livres << self._n
        d = livres >> self._n
        dois = (a & b) | (a & c) | (a & d) | (b & c) | (b & d) | (c & d)
        becos = (livres & ~dois).bit_count()
        gargalos = self.gargalos(livres) if risco == 0 and becos == 0 else 0
        return (risco == 0 and becos == 0 and gargalos == 0,
                -(risco + becos + gargalos) * self._n*self._n,
                -len(rota) - 2 * self.concavidade(ocupadas))

    def reparar(self, corpo, rota, comida, meta, limite, prazo):
        valor = self.pontuar(corpo, rota, comida, meta, limite)
        if valor is None:
            return None
        valor_inicial = valor
        ocupadas = set(corpo[1:]) | set(rota) | {corpo[0]}
        while len(rota) + 2 <= prazo:
            pontos = [corpo[0]] + rota
            melhor = None
            for i, (a, b) in enumerate(zip(pontos, pontos[1:])):
                dx, dy = b[0]-a[0], b[1]-a[1]
                for sx, sy in ((-dy,dx),(dy,-dx)):
                    c,d = (a[0]+sx,a[1]+sy),(b[0]+sx,b[1]+sy)
                    if c in ocupadas or d in ocupadas or c not in self._bits or d not in self._bits:
                        continue
                    nova = rota[:i] + [c,d] + rota[i:]
                    v = self.pontuar(corpo,nova,comida,meta,limite)
                    if v and (v[0] or v[1] >= valor[1]) and (melhor is None or v > melhor[0]):
                        melhor = v,nova,c,d
            if melhor is None:
                break
            valor,rota,c,d = melhor
            ocupadas.update((c,d))
            if valor[0]:
                return rota
        return rota if valor > valor_inicial else None

    def defeitos(self, ocupadas):
        livres = self._todas & ~ocupadas
        a = (livres & self._nao_direita) << 1
        b = (livres & self._nao_esquerda) >> 1
        c = livres << self._n
        d = livres >> self._n
        dois = (a & b) | (a & c) | (a & d) | (b & c) | (b & d) | (c & d)
        return (livres & ~dois).bit_count()

    def busca(self, jogo, largura=1024):
        corpo = tuple(jogo.corpo)
        prazo = jogo.nivel.limite - jogo.sem_comer
        comida = jogo.comida
        ocupadas = sum(self._bits[p] for p in corpo)
        fila = [(corpo, ocupadas, (), self.concavidade(ocupadas))]
        melhor = None
        for tempo in range(1, prazo + 1):
            candidatas = []
            formas = set()
            for corpo, ocupadas, rota, concavidade_atual in fila:
                livres = ocupadas & ~self._bits[corpo[-1]]
                for p in adjacentes(corpo[0], self._n):
                    bit = self._bits[p]
                    if livres & bit:
                        continue
                    distancia = abs(p[0]-comida[0]) + abs(p[1]-comida[1])
                    if tempo + distancia > prazo:
                        continue
                    nova = rota + (p,)
                    if p == comida:
                        valor = self.pontuar(jogo.corpo, list(nova), comida,
                                             jogo.nivel.meta, jogo.nivel.limite)
                        if valor and (melhor is None or valor > melhor[0]):
                            melhor = valor, nova
                            if valor[0]:
                                return list(nova)
                        continue
                    futuro = (p,) + corpo[:-1]
                    mascara = livres | bit
                    # A ordem define a liberação de cada casa: ocupação igual
                    # não implica o mesmo futuro nem as mesmas rotas possíveis.
                    forma = futuro
                    if forma in formas:
                        continue
                    formas.add(forma)
                    defeitos = self.defeitos(mascara)
                    concavidade = self.concavidade_apos_passo(
                        ocupadas, mascara, corpo[-1], p, concavidade_atual)
                    candidatas.append((distancia + defeitos * 5 + concavidade * 0.5,
                                       distancia, futuro, mascara, nova, concavidade))
            candidatas.sort(key=lambda c: c[:2])
            fila = []
            por_cabeca = {}
            for _, _, corpo, mascara, rota, concavidade in candidatas:
                quant = por_cabeca.get(corpo[0], 0)
                if quant >= 16:
                    continue
                por_cabeca[corpo[0]] = quant + 1
                fila.append((corpo, mascara, rota, concavidade))
                if len(fila) >= largura:
                    break
            if not fila:
                break
        return list(melhor[1]) if melhor else []

    def busca_corpo(self, jogo, orcamento=50000):
        """A* sobre o corpo inteiro para atravessar liberações tardias do rabo."""
        inicio = tuple(jogo.corpo)
        comida = jogo.comida
        prazo = jogo.nivel.limite - jogo.sem_comer
        # Distâncias temporais até a comida, ignorando apenas o corpo novo.
        # Manhattan não enxerga portas que abrem tarde: a busca pode gastar
        # todo o orçamento em aproximações que nunca chegam dentro do prazo.
        tamanho = self._n * self._n
        libera = [0] * tamanho
        for i, (x, y) in enumerate(inicio):
            libera[y * self._n + x] = len(inicio) - i
        alvo = comida[1] * self._n + comida[0]
        distancias = [[prazo + 1] * tamanho for _ in range(prazo + 1)]
        for t in range(prazo, -1, -1):
            distancias[t][alvo] = 0
            if t == prazo:
                continue
            for p, vizinhos in enumerate(self._vizinhos):
                if p != alvo and (libera[p] <= t or (t == 0 and p == inicio[0][1] * self._n + inicio[0][0])):
                    distancias[t][p] = 1 + min(distancias[t + 1][q] for q in vizinhos)
        serial = count()
        fila = [(0, 0, next(serial), inicio, ())]
        vistos = {inicio: 0}
        alternativa = []
        melhor = None
        for _ in range(orcamento):
            if not fila:
                break
            _, negativo_tempo, _, corpo, rota = heappop(fila)
            tempo = -negativo_tempo
            if corpo[0] == comida:
                valor = self.pontuar(inicio, rota, comida, jogo.nivel.meta, jogo.nivel.limite)
                if valor and (melhor is None or valor > melhor[0]):
                    melhor = valor, list(rota)
                    if valor[0]:
                        return list(rota)
                alternativa = alternativa or list(rota)
                continue
            if tempo >= prazo:
                continue
            ocupadas = set(corpo[:-1])
            for p in adjacentes(corpo[0], self._n):
                if p in ocupadas:
                    continue
                t = tempo + 1
                distancia = distancias[t][p[1] * self._n + p[0]]
                if t + distancia > prazo:
                    continue
                futuro = (p,) + (corpo if p == comida else corpo[:-1])
                if vistos.get(futuro, prazo + 1) <= t:
                    continue
                vistos[futuro] = t
                heappush(fila, (t + distancia, -t, next(serial), futuro, rota + (p,)))
        return melhor[1] if melhor else alternativa

    def desviar_pelo_rabo(self, jogo):
        """Libera corpo antes de se aproximar da comida, sem passar do prazo."""
        corpo, comida = jogo.corpo, jogo.comida
        prazo = jogo.nivel.limite - jogo.sem_comer
        rabo = caminho_bfs(corpo[0], corpo[-1], corpo[1:-1] + [comida], self._n)
        if not rabo:
            return None
        desvios = [rabo, alongar([corpo[0]] + rabo, corpo[1:-1] + [comida], self._n, prazo)]
        melhor = None
        for desvio in desvios:
            futuro = list(corpo)
            prefixo = []
            for p in desvio[:prazo - 1]:
                futuro = simular(futuro, [p], comida)
                if futuro is None or p == comida:
                    break
                prefixo.append(p)
                rota = self.caminho(futuro, comida, prazo - len(prefixo))
                if not rota:
                    continue
                candidata = prefixo + rota
                valor = self.pontuar(corpo, candidata, comida, jogo.nivel.meta, jogo.nivel.limite)
                if valor and (melhor is None or valor > melhor[0]):
                    melhor = valor, candidata
                    if valor[0]:
                        return melhor
        return melhor

    def ponderado(self, corpo, comida, peso, contato, prazo):
        bloqueadas = set(corpo[1:-1])
        livres = self._todas
        for p in bloqueadas:
            livres &= ~self._bits[p]
        grupos = {}
        custos = {}
        for p, bit in self._bits.items():
            if p in bloqueadas:
                continue
            contatos = lacunas = 0
            x,y = p
            for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)):
                q = x+dx,y+dy
                r = x+2*dx,y+2*dy
                if q in bloqueadas or q not in self._bits:
                    contatos += 1
                elif r in bloqueadas or r not in self._bits:
                    lacunas += 1
            custo = max(1, 10 + peso*lacunas - contato*contatos)
            custos[p] = custo
            grupos[custo] = grupos.get(custo,0) | bit
        inicio = self._bits[corpo[0]]
        alvo = self._bits[comida]
        buckets = {0:inicio}
        fila = [0]
        camadas = {}
        vistos = 0
        while fila:
            t = heappop(fila)
            fronteira = buckets.pop(t,0) & ~vistos
            if not fronteira:
                continue
            vistos |= fronteira
            camadas[t] = fronteira
            if fronteira & alvo:
                p = comida
                rota = []
                while p != corpo[0]:
                    rota.append(p)
                    t -= custos[p]
                    vizinhos = self.expandir(self._bits[p]) & camadas[t]
                    bit = vizinhos & -vizinhos
                    i = bit.bit_length()-1
                    p = i%self._n,i//self._n
                rota.reverse()
                return rota if len(rota) <= prazo else None
            proximas = self.expandir(fronteira) & livres & ~vistos
            for custo, mascara in grupos.items():
                novas = proximas & mascara
                if novas:
                    proximo = t+custo
                    if proximo not in buckets:
                        buckets[proximo] = novas
                        heappush(fila,proximo)
                    else:
                        buckets[proximo] |= novas
        return None

    def planejar(self, jogo):
        corpo, comida = jogo.corpo, jogo.comida
        prazo = jogo.nivel.limite - jogo.sem_comer
        rota = self.caminho(corpo, comida, prazo)
        melhor = None
        if rota:
            valor = self.pontuar(corpo, rota, comida, jogo.nivel.meta, jogo.nivel.limite)
            if valor:
                melhor = valor,rota
        for peso,contato in ((4,3),(16,3),(40,3),(16,0),(4,0),(40,0)):
            candidata = self.ponderado(corpo, comida, peso, contato, prazo)
            if candidata:
                valor = self.pontuar(corpo,candidata,comida,jogo.nivel.meta,jogo.nivel.limite)
                if valor and (melhor is None or valor > melhor[0]):
                    melhor = valor,candidata
        if melhor and melhor[0][0]:
            return melhor[1]
        if melhor:
            reparada = self.reparar(corpo, melhor[1], comida, jogo.nivel.meta,
                                    jogo.nivel.limite, prazo)
            if reparada:
                valor = self.pontuar(corpo, reparada, comida, jogo.nivel.meta, jogo.nivel.limite)
                melhor = valor, reparada
                if valor[0]:
                    return reparada
        alternativa = self.busca(jogo)
        if alternativa:
            valor = self.pontuar(corpo, alternativa, comida, jogo.nivel.meta, jogo.nivel.limite)
            if valor and (melhor is None or valor > melhor[0]):
                melhor = valor, alternativa
        if melhor and melhor[0][0]:
            return melhor[1]
        desvio = self.desviar_pelo_rabo(jogo)
        if desvio and (melhor is None or desvio[0] > melhor[0]):
            melhor = desvio
            if melhor[0][0]:
                return melhor[1]
        alternativa = self.busca_corpo(jogo)
        if alternativa:
            valor = self.pontuar(corpo, alternativa, comida, jogo.nivel.meta, jogo.nivel.limite)
            if melhor is None or (valor and valor > melhor[0]):
                return alternativa
        return melhor[1] if melhor else alternativa

    def escolher(self, jogo: Jogo) -> str:
        n = jogo.nivel.tamanho
        if self._n != n:
            self.configurar(n)
        assinatura = (tuple(jogo.corpo), jogo.comida, jogo.direcao)
        if assinatura != self._esperado:
            self._rota.clear()
        if not self._rota:
            self._rota.extend(self.planejar(jogo))
        if self._rota:
            destino = self._rota.popleft()
            for acao in ACOES:
                if jogo.destino(acao)[0] == destino and jogo.segura(acao):
                    futuro = simular(jogo.corpo, [destino], jogo.comida)
                    self._esperado = (tuple(futuro), jogo.comida, jogo.destino(acao)[1])
                    return acao
        self._esperado = None
        return self.emergencia(jogo)

    def emergencia(self, jogo: Jogo) -> str:
        n = jogo.nivel.tamanho
        if self._n != n:
            self.configurar(n)
        if self._comida != jogo.comida:
            self._visitadas.clear()
            self._comida = jogo.comida
        corpo = jogo.corpo
        ocupadas = 0
        for p in corpo:
            ocupadas |= self._bits[p]
        comida = self._bits[jogo.comida]
        prazo = jogo.nivel.limite - jogo.sem_comer
        candidatas = []
        for acao in ACOES:
            if not jogo.segura(acao):
                continue
            p, _ = jogo.destino(acao)
            bit = self._bits[p]
            cresce = p == jogo.comida
            if cresce and len(corpo) + 1 >= jogo.nivel.meta:
                return acao
            # Cabeça e rabo virtuais podem participar da busca de escape.
            bloqueadas = ocupadas & ~self._bits[corpo[-1]]
            if not cresce:
                bloqueadas &= ~self._bits[corpo[-2]]
            livres = self._todas & ~bloqueadas | bit
            vistos, distancia, raio = self.avaliar(bit, livres, comida)
            tamanho = vistos.bit_count()
            rabo = self._bits[corpo[-1] if cresce else corpo[-2]]
            escapa = bool(vistos & rabo)
            total = livres.bit_count()
            visitas = self._visitadas.get(p, 0)
            chega = distancia is not None and distancia + 1 <= prazo
            valor = (escapa, tamanho == total, chega, -(distancia if distancia is not None else n*n),
                     -visitas, -raio, tamanho)
            candidatas.append((valor, acao, p))
        if not candidatas:
            return "straight"
        _, acao, p = max(candidatas, key=lambda c: c[0])
        self._visitadas[p] = self._visitadas.get(p, 0) + 1
        return acao
