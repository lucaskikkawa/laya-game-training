"""Uma janela a 60 fps. Inferência e gabarito trabalham fora da thread gráfica."""
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import math
from time import perf_counter
import pygame
from nucleo.config import versoes
from nucleo.laya import Laya
from .regras import NIVEIS, NOMES_DIRECAO
from .sessao import Sessao
from .sons import Sons

FUNDO = (9, 18, 36)
CARTAO = (18, 32, 53)
TEXTO = (227, 236, 245)
MUTED = (146, 164, 186)
VERDE = (72, 205, 117)
VERMELHO = (240, 78, 88)
AZUL = (76, 155, 234)
TRADUCAO = {"straight": "Reto", "left": "Esquerda", "right": "Direita"}


class Aplicativo:
    def __init__(self, args, decisor=None, pasta_runs=None):
        pygame.init()
        self.tela = pygame.display.set_mode((1280, 860), pygame.RESIZABLE)
        pygame.display.set_caption("Laya Games · Snake v0.1")
        self.canvas = pygame.Surface((1280, 860))
        self.fontes = {}
        self.args = args
        self.nivel = args.nivel
        self.versao = args.versao
        self.versoes = sorted(set(versoes()) | {self.versao})
        self.modo = args.modo
        self.velocidade = str(args.passos_por_segundo).removesuffix(".0")
        self.partidas = str(args.partidas)
        self.automatico = args.partidas > 1
        self.decisor_injetado = decisor
        self.pasta_runs = pasta_runs
        self.estado = "selecao"
        self.painel = True
        self.cheia = False
        self.rodando = True
        self.botoes = []
        self.campos = {}
        self.foco = None
        self.sessao = None
        self.jogo = None
        self.registro = None
        self.resultado = None
        self.erro = ""
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="laya")
        self.futuro = None
        self.tarefa = ""
        self.proximo_passo = 0
        self.ultimo_passo = perf_counter()
        self.corpo_anterior = []
        self.probs = dict.fromkeys(TRADUCAO, 0.0)
        self.historico = deque(maxlen=36)
        self.acordos = 0
        self.placar = 0.0
        self.sons = Sons()
        self.status = "Escolha o nível e a versão."

    def fonte(self, tamanho=20, mono=False):
        chave = tamanho, mono
        if chave not in self.fontes:
            self.fontes[chave] = pygame.font.SysFont("consolas" if mono else "segoeui", tamanho)
        return self.fontes[chave]

    def texto(self, conteudo, x, y, tamanho=20, cor=TEXTO, mono=False):
        self.canvas.blit(self.fonte(tamanho, mono).render(str(conteudo), True, cor), (x, y))

    def botao(self, titulo, retangulo, acao, ativo=True):
        rect = pygame.Rect(retangulo)
        pygame.draw.rect(self.canvas, AZUL if ativo else (43, 53, 68), rect, border_radius=8)
        imagem = self.fonte(18).render(titulo, True, TEXTO if ativo else MUTED)
        self.canvas.blit(imagem, imagem.get_rect(center=rect.center))
        self.botoes.append((rect, acao, ativo))

    def campo(self, nome, valor, rect):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.canvas, CARTAO, rect, border_radius=5)
        pygame.draw.rect(self.canvas, AZUL if self.foco == nome else MUTED, rect, 1, border_radius=5)
        self.texto(valor + ("|" if self.foco == nome else ""), rect.x + 10, rect.y + 7)
        self.campos[nome] = rect

    def _enviar(self, tarefa, funcao):
        self.tarefa = tarefa
        self.futuro = self.pool.submit(funcao)

    def iniciar(self):
        if self.futuro:
            return
        try:
            quantidade = int(self.partidas)
            velocidade = float(self.velocidade)
            if quantidade < 1 or not math.isfinite(velocidade) or velocidade <= 0:
                raise ValueError
        except ValueError:
            self.erro = "Informe partidas e passos/s positivos."
            return
        self.erro = ""
        try:
            self.sessao = Sessao(self.decisor_injetado or Laya(self.versao, self.args.cpu),
                                 self.nivel, quantidade, self.versao, pasta=self.pasta_runs, modo=self.modo)
        except Exception as exc:
            self.erro = f"Não foi possível criar a sessão: {exc}"
            return
        self.estado = "carregando"
        self.status = "Conectando ao Laya; o primeiro carregamento pode demorar..."
        self._enviar("carregar", lambda: getattr(self.sessao.decisor, "carregar", lambda: None)())

    def _nova_run(self):
        self.jogo = self.sessao.iniciar_run()
        self.registro = None
        self.resultado = None
        self.corpo_anterior = list(self.jogo.corpo)
        self.historico.clear()
        self.probs = dict.fromkeys(TRADUCAO, 0.0)
        self.acordos = 0
        self.placar = 0
        self.estado = "jogando"
        self.status = "Laya está jogando; calculando e registrando decisões."
        self.proximo_passo = perf_counter()

    def _coletar(self):
        if not self.futuro or not self.futuro.done():
            return
        futuro, tarefa = self.futuro, self.tarefa
        self.futuro = None
        try:
            valor = futuro.result()
            if tarefa == "carregar":
                self._nova_run()
            elif tarefa == "passo":
                self.registro = valor
                self.ultimo_passo = perf_counter()
                self.historico.append(valor)
                self.acordos += valor["escolha"] == valor["jogada_ideal"]
                if self.modo == "normal" and valor["pontos_ganhos"]:
                    self.sons.tocar("comida")
                if self.jogo.fim:
                    self.estado = "apurando"
                    self.status = "Salvando a run e calculando a partida do algoritmo..."
                    if self.modo == "normal":
                        self.sons.tocar("vitoria" if self.jogo.vitoria else "morte")
                    self._enviar("finalizar", self.sessao.finalizar_run)
            elif tarefa == "finalizar":
                self.resultado = valor
                self.estado = "resultado"
                self.proximo_passo = perf_counter() + 2
                if self.modo == "rapido" and not self.sessao.concluida:
                    self._nova_run()
        except Exception as exc:
            self.erro = f"Falha: {type(exc).__name__}: {exc}"
            self.estado = "erro"
            if self.sessao:
                self.sessao.interromper(exc)

    def atualizar(self, dt):
        self._coletar()
        if self.registro:
            for acao, alvo in self.registro["probabilidades"].items():
                self.probs[acao] += (alvo - self.probs[acao]) * min(1, dt * 9)
        if self.jogo:
            self.placar += (self.jogo.pontos - self.placar) * min(1, dt * 8)
        agora = perf_counter()
        if self.estado == "jogando" and not self.futuro and agora >= self.proximo_passo:
            self.corpo_anterior = list(self.jogo.corpo)
            self._enviar("passo", self.sessao.passo)
            try:
                velocidade = max(.1, float(self.velocidade))
            except ValueError:
                velocidade = 1
            self.proximo_passo = agora + 1 / velocidade
        if (self.estado == "resultado" and self.automatico and not self.sessao.concluida
                and agora >= self.proximo_passo):
            self._nova_run()

    def desenhar_selecao(self):
        self.texto("Snake", 80, 110, 64, VERDE)
        self.texto("Laya v0.1 · Decisões em tempo real", 84, 188, 28)
        self.texto("Paredes, corpo e o limite sem comer encerram a partida.", 84, 238, 22, MUTED)
        n = NIVEIS[self.nivel]
        self.botao(f"Nível: {n.tamanho} × {n.tamanho}", (84, 310, 245, 48), "nivel")
        self.texto(f"Vitória: {n.meta} gomos · Limite: {n.limite} passos sem comer", 350, 322)
        self.botao(f"Laya: {self.versao}", (84, 380, 245, 48), "versao")
        self.texto("v000 = modelo base, sem treino", 350, 392, 20, MUTED)
        self.botao(f"Modo: {'Normal' if self.modo == 'normal' else 'Rápido'}", (84, 450, 245, 48), "modo")
        self.texto("Partidas seguidas", 350, 462)
        self.campo("partidas", self.partidas, (525, 450, 100, 46))
        self.botao(f"Automático: {'sim' if self.automatico else 'não'}", (655, 450, 215, 46), "auto")
        self.controles_velocidade(84, 530)
        self.botao("Start · Conectar ao Laya", (84, 630, 300, 55), "start")
        self.botao("Treinar · em breve, v0.2", (410, 630, 270, 55), "treinar", False)
        self.texto("F11: tela cheia     Tab: mostrar/esconder painel     Esc: voltar", 84, 755, 19, MUTED)
        self.texto("Dispositivo: " + ("CPU solicitado" if self.args.cpu else "CUDA se disponível, senão CPU"), 84, 705, 19, MUTED)

    def controles_velocidade(self, x, y):
        self.texto("Passos/s", x, y + 10, 19)
        self.botao("−1", (x + 105, y, 48, 44), "menos")
        self.campo("velocidade", self.velocidade, (x + 164, y, 82, 44))
        self.botao("+1", (x + 257, y, 48, 44), "mais")

    def desenhar_tabuleiro(self):
        if not self.jogo:
            return
        largura = 760 if self.painel else 1240
        area = pygame.Rect(20, 105, largura, 650)
        n = self.nivel
        lado = min(area.width, area.height) // n
        origem_x = area.centerx - n * lado // 2
        origem_y = area.centery - n * lado // 2
        ret = pygame.Rect(origem_x, origem_y, lado * n, lado * n)
        pygame.draw.rect(self.canvas, (12, 27, 46), ret)
        for i in range(n + 1):
            pygame.draw.line(self.canvas, (18, 35, 53), (origem_x + i * lado, origem_y), (origem_x + i * lado, ret.bottom))
            pygame.draw.line(self.canvas, (18, 35, 53), (origem_x, origem_y + i * lado), (ret.right, origem_y + i * lado))
        progresso = min(1, (perf_counter() - self.ultimo_passo) / .22)
        progresso = progresso * progresso * (3 - 2 * progresso)
        for i in range(len(self.jogo.corpo) - 1, -1, -1):
            x, y = self.jogo.corpo[i]
            if self.corpo_anterior:
                ox, oy = self.corpo_anterior[min(i, len(self.corpo_anterior) - 1)]
                x, y = ox + (x - ox) * progresso, oy + (y - oy) * progresso
            rect = pygame.Rect(origem_x + x * lado + 1, origem_y + y * lado + 1, lado - 2, lado - 2)
            pygame.draw.rect(self.canvas, (29, 113, 69) if i == 0 else VERDE, rect)
            if i == 0:
                dx, dy = ((0, -1), (1, 0), (0, 1), (-1, 0))[self.jogo.direcao]
                for sinal in (-1, 1):
                    centro = (int(rect.centerx + dx * lado * .2 - dy * sinal * lado * .2),
                              int(rect.centery + dy * lado * .2 + dx * sinal * lado * .2))
                    pygame.draw.circle(self.canvas, TEXTO, centro, max(2, lado // 12))
                    pygame.draw.circle(self.canvas, FUNDO, centro, max(1, lado // 22))
                confianca = self.registro["confianca"] if self.registro else 0
                cor = (int(240 * (1 - confianca)), int(80 + 150 * confianca), 70)
                ponta = (rect.centerx + dx * lado * .44, rect.centery + dy * lado * .44)
                base = (rect.centerx - dx * lado * .12, rect.centery - dy * lado * .12)
                pygame.draw.polygon(self.canvas, cor, [ponta, (base[0] - dy * lado * .13, base[1] + dx * lado * .13),
                                                         (base[0] + dy * lado * .13, base[1] - dx * lado * .13)])
        if self.jogo.comida:
            x, y = self.jogo.comida
            pygame.draw.rect(self.canvas, VERMELHO, (origem_x + x * lado + 2, origem_y + y * lado + 2, lado - 4, lado - 4), border_radius=3)
        self.texto(f"Gomos {len(self.jogo.corpo)}/{self.jogo.nivel.meta}    Sem comer {self.jogo.sem_comer}/{self.jogo.nivel.limite}", 40, 765, 20, MUTED)

    def desenhar_painel(self):
        x = 810
        pygame.draw.rect(self.canvas, CARTAO, (790, 100, 470, 740), border_radius=12)
        self.texto("Decisão do Laya", x, 112, 25)
        y = 151
        for acao, prob in self.probs.items():
            self.texto(TRADUCAO[acao], x, y, 17)
            pygame.draw.rect(self.canvas, FUNDO, (x + 100, y + 3, 265, 16), border_radius=3)
            pygame.draw.rect(self.canvas, AZUL, (x + 100, y + 3, int(265 * prob), 16), border_radius=3)
            self.texto(f"{prob:.0%}", x + 375, y - 1, 18)
            y += 28
        r = self.registro
        if r:
            self.texto(f"Escolha: {TRADUCAO[r['escolha']]}   Latência: {r['latencia_ms']:.1f} ms", x, 240, 18)
            self.texto(f"Confiança: {r['confianca']:.1%}", x, 270, 18)
            pygame.draw.rect(self.canvas, FUNDO, (x + 180, 275, 250, 13))
            pygame.draw.rect(self.canvas, VERDE, (x + 180, 275, int(250 * r["confianca"]), 13))
            self.texto(f"Gabarito: {TRADUCAO[r['jogada_ideal']]} · Concordância {self.acordos / self.jogo.passos:.0%}", x, 300, 18)
            self.texto("Histórico · confiança", x, 328, 17, MUTED)
            pontos = [(x + i * 12, 398 - h["confianca"] * 42) for i, h in enumerate(self.historico)]
            if len(pontos) > 1:
                pygame.draw.lines(self.canvas, VERDE, False, pontos, 2)
            ultimas = list(self.historico)[-6:]
            self.texto(" · ".join(TRADUCAO[h["escolha"]][:1] for h in ultimas), x, 405, 16, MUTED)
            estado = r["estado"]
        else:
            self.texto("Aguardando a primeira decisão...", x, 270, 19, MUTED)
            estado = self.jogo.estado() if self.jogo else ""
        self.texto("Estado recebido (inglês)", x, 437, 18)
        linhas = estado.splitlines()
        # Legenda inteira com quebra; mapa inteiro, sem omitir casas.
        yy = 464
        for linha in linhas[:3]:
            palavras = linha.split()
            trecho = ""
            for palavra in palavras:
                if self.fonte(11, True).size(trecho + palavra)[0] > 430:
                    self.texto(trecho, x, yy, 11, MUTED, True)
                    yy += 12
                    trecho = ""
                trecho += palavra + " "
            self.texto(trecho, x, yy, 11, MUTED, True)
            yy += 12
        tamanho = min(15, max(8, (832 - yy) // self.nivel))
        for linha in linhas[3:]:
            self.texto(linha, x, yy, tamanho, TEXTO, True)
            yy += tamanho

    def desenhar_progresso(self):
        self.texto("Sessão rápida" if self.modo == "rapido" else "Carregando", 100, 180, 44)
        self.texto(self.status, 100, 250, 22, MUTED)
        if self.sessao:
            s = self.sessao
            total = s.partidas
            self.texto(f"Runs concluídas: {s.indice} de {total}", 100, 330, 32)
            pygame.draw.rect(self.canvas, CARTAO, (100, 395, 1000, 26), border_radius=10)
            pygame.draw.rect(self.canvas, VERDE, (100, 395, int(1000 * s.indice / total), 26), border_radius=10)
            segundos = perf_counter() - s.inicio
            self.texto(f"Tempo: {segundos:.0f} s", 100, 460, 24)
            if s.resultados:
                pontos = sum(r["comparacao"]["geral"]["laya"]["pontos"] for r in s.resultados)
                self.texto(f"Resumo parcial: {pontos} pontos nas runs concluídas", 100, 505, 24)
            if self.jogo:
                self.texto(f"Run atual: {self.jogo.passos} passos · {self.jogo.pontos} pontos", 100, 555, 24)
            self.hardware(100, 650)

    def hardware(self, x, y):
        if not self.sessao:
            return
        decisor = self.sessao.decisor
        dados = decisor.telemetria() if hasattr(decisor, "telemetria") else {"dispositivo": "mock"}
        rotulo = dados["dispositivo"].upper()
        if dados.get("gpu"):
            rotulo += " · " + dados["gpu"]
        if "vram_alocada_mb" in dados:
            rotulo += f" · VRAM {dados['vram_alocada_mb']:.0f}/{dados['vram_total_mb']:.0f} MB"
        self.texto(rotulo, x, y, 17, MUTED)

    def desenhar_resultado(self):
        s = self.sessao
        titulo = "Resumo da sessão" if self.modo == "rapido" else f"Resultado da run {s.indice}"
        self.texto(titulo, 90, 145, 42)
        resultados = s.resultados if self.modo == "rapido" else s.resultados[-1:]
        for i, (nome, chave) in enumerate((("Laya", "laya"), ("Algoritmo", "algoritmo"))):
            x = 90 + i * 550
            self.texto(nome, x, 240, 30, VERDE if i else AZUL)
            resumos = [r["comparacao"]["geral"][chave] for r in resultados]
            self.texto(f"Pontos: {sum(r['pontos'] for r in resumos)}", x, 300, 26)
            self.texto(f"Passos: {sum(r['passos'] for r in resumos)}", x, 345, 26)
            self.texto(f"Vitórias: {sum(r['vitoria'] for r in resumos)}/{len(resumos)}", x, 390, 26)
            if len(resumos) == 1:
                self.texto(f"Fim: {resumos[0]['morte'] or 'vitória'}", x, 435, 22)
        registros = self.sessao.registros
        media = sum(r["latencia_ms"] for r in registros) / max(1, len(registros))
        concordancia = sum(r["comparacao"]["concordancia"] for r in resultados) / max(1, len(resultados))
        self.texto(f"Concordância: {concordancia:.1%} · Latência média da última run: {media:.1f} ms", 90, 505, 22)
        pps = sum(r["passos_por_segundo"] for r in resultados) / max(1, len(resultados))
        self.texto(f"Velocidade medida: {pps:.2f} passos/s · Registros em {s.pasta.name}", 90, 550, 21, MUTED)
        self.hardware(90, 605)
        if not s.concluida:
            self.botao("Próxima partida", (90, 680, 240, 50), "proxima")
        self.botao("Retry · Nova sessão", (360, 680, 240, 50), "retry")
        self.botao("Seleção", (630, 680, 180, 50), "selecao")
        self.botao("Treinar · em breve, v0.2", (845, 680, 300, 50), "treinar", False)

    def desenhar(self):
        self.canvas.fill(FUNDO)
        self.botoes.clear()
        self.campos.clear()
        self.texto("LAYA GAMES / SNAKE", 25, 20, 22, MUTED)
        if self.estado == "selecao":
            self.desenhar_selecao()
        elif self.estado == "resultado":
            self.desenhar_resultado()
        elif self.estado in ("carregando", "apurando") or self.modo == "rapido" and self.estado == "jogando":
            self.desenhar_progresso()
        elif self.estado == "erro":
            self.texto("Não foi possível continuar a sessão.", 70, 230, 30)
            self.texto("Confira a instalação e os arquivos parciais em runs/.", 70, 285, 22, MUTED)
            self.botao("Voltar à seleção", (70, 380, 260, 50), "selecao")
        else:
            self.texto(f"Placar: {round(self.placar)}", 30, 60, 28, VERDE)
            self.texto(f"Run {self.sessao.indice + 1}/{self.sessao.partidas}", 350, 65, 22)
            self.hardware(600, 28)
            self.desenhar_tabuleiro()
            if self.painel:
                self.desenhar_painel()
            self.controles_velocidade(30, 805)
            self.botao("Retry", (365, 805, 100, 44), "retry", not self.futuro)
            self.botao(f"Auto: {'sim' if self.automatico else 'não'}", (485, 805, 150, 44), "auto")
            self.botao("Treinar · v0.2", (650, 805, 130, 44), "treinar", False)
        if self.erro:
            # Quebrar mensagens de exceção para caberem na janela.
            for i in range(0, min(len(self.erro), 330), 110):
                self.texto(self.erro[i:i + 110], 30, 740 + (i // 110) * 24, 19, VERMELHO)
        janela = self.tela.get_rect()
        escala = min(janela.width / 1280, janela.height / 860)
        tamanho = (max(1, int(1280 * escala)), max(1, int(860 * escala)))
        self.destino = pygame.Rect(0, 0, *tamanho)
        self.destino.center = janela.center
        self.tela.fill(FUNDO)
        self.tela.blit(pygame.transform.smoothscale(self.canvas, tamanho), self.destino)
        pygame.display.flip()

    def acionar(self, acao):
        if acao == "nivel":
            niveis = list(NIVEIS)
            self.nivel = niveis[(niveis.index(self.nivel) + 1) % len(niveis)]
        elif acao == "versao":
            self.versao = self.versoes[(self.versoes.index(self.versao) + 1) % len(self.versoes)]
        elif acao == "modo":
            self.modo = "rapido" if self.modo == "normal" else "normal"
            self.velocidade = "5" if self.modo == "rapido" else "1"
        elif acao == "auto":
            self.automatico = not self.automatico
        elif acao in ("mais", "menos"):
            try:
                self.velocidade = str(max(1, float(self.velocidade) + (1 if acao == "mais" else -1))).removesuffix(".0")
            except ValueError:
                self.velocidade = "1"
        elif acao == "start":
            self.iniciar()
        elif acao == "proxima":
            self._nova_run()
        elif acao in ("selecao", "retry") and not self.futuro:
            if self.sessao and not self.sessao.concluida:
                self.sessao.interromper()
            self.estado = "selecao"
            self.erro = ""
            if acao == "retry":
                self.iniciar()

    def evento(self, event):
        if event.type == pygame.QUIT:
            self.rodando = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                self.cheia = not self.cheia
                self.tela = pygame.display.set_mode((0, 0), pygame.FULLSCREEN) if self.cheia else pygame.display.set_mode((1280, 860), pygame.RESIZABLE)
            elif event.key == pygame.K_TAB:
                self.painel = not self.painel
            elif event.key == pygame.K_ESCAPE:
                if self.foco:
                    self.foco = None
                elif not self.futuro:
                    self.acionar("selecao")
            elif self.foco:
                valor = getattr(self, self.foco)
                if event.key == pygame.K_BACKSPACE:
                    valor = valor[:-1]
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.foco = None
                    return
                elif event.unicode and event.unicode in "0123456789." and len(valor) < 7:
                    valor += event.unicode
                setattr(self, self.foco, valor)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = event.pos
            destino = getattr(self, "destino", self.tela.get_rect())
            pos = ((x - destino.x) * 1280 / destino.width, (y - destino.y) * 860 / destino.height)
            self.foco = next((nome for nome, r in self.campos.items() if r.collidepoint(pos)), None)
            if not self.foco:
                for r, acao, ativo in self.botoes:
                    if ativo and r.collidepoint(pos):
                        self.acionar(acao)
                        break

    def executar(self, max_frames=None):
        clock = pygame.time.Clock()
        frames = 0
        try:
            while self.rodando and (max_frames is None or frames < max_frames):
                dt = clock.tick(60) / 1000
                for event in pygame.event.get():
                    self.evento(event)
                self.atualizar(dt)
                self.desenhar()
                frames += 1
        finally:
            self.fechar()

    def fechar(self):
        # A escrita fica com uma única thread; terminar a inferência antes do checkpoint.
        self.pool.shutdown(wait=True, cancel_futures=True)
        if self.sessao and not self.sessao.concluida:
            self.sessao.interromper()
        pygame.quit()
