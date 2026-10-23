"""Uma janela a 60 fps. Inferência e gabarito trabalham fora da thread gráfica."""
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import math
import os
import sys
from time import perf_counter
import pygame
from nucleo.config import versoes
from nucleo.laya_processo import LayaProcesso
from .regras import NIVEIS, NOMES_DIRECAO
from .sessao import Sessao
from .controles import Pausa
from . import ux
from .sons import Sons

FUNDO = (9, 18, 36)
CARTAO = (18, 32, 53)
TEXTO = (227, 236, 245)
MUTED = (146, 164, 186)
VERDE = (72, 205, 117)
VERMELHO = (240, 78, 88)
AZUL = (76, 155, 234)
TREINAR = "Treinar · disponível na v0.2"
TRADUCAO = {"straight": "Reto", "left": "Esquerda", "right": "Direita"}


def tamanho_inicial_janela(desktop: tuple[int, int]) -> tuple[int, int]:
    """Preserva a proporção do canvas, com margem para título e barra de tarefas."""
    largura, altura = desktop
    escala = min(largura * .9 / 1280, max(1, altura - 120) * .9 / 860)
    escala = min(max(.5, escala), largura / 1280, altura / 860)
    return max(1, int(1280 * escala)), max(1, int(860 * escala))


def mouse_para_logico(pos: tuple[int, int],
                      destino: tuple[int, int, int, int]) -> tuple[float, float]:
    """Converte coordenadas da janela usando a área onde o canvas foi desenhado."""
    x, y = pos
    esquerda, topo, largura, altura = destino
    return (x - esquerda) * 1280 / largura, (y - topo) * 860 / altura


def _ativar_dpi_awareness():
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class Aplicativo:
    def __init__(self, args, decisor=None, pasta_runs=None):
        _ativar_dpi_awareness()
        os.environ["SDL_VIDEO_CENTERED"] = "1"
        pygame.init()
        try:
            desktop = pygame.display.get_desktop_sizes()[0]
        except (pygame.error, IndexError):
            desktop = (1280, 860)
        self.tamanho_inicial = tamanho_inicial_janela(desktop)
        self.tela = pygame.display.set_mode(self.tamanho_inicial, pygame.RESIZABLE)
        pygame.display.set_caption("Laya Games · Snake v0.1")
        self.canvas = pygame.Surface((1280, 860))
        self.fontes = {}
        self.args = args
        self.nivel = args.nivel
        self.versao = args.versao
        self.versoes = sorted(set(versoes()) | {self.versao})
        self.modo = args.modo
        # Limites digitáveis; valores vindos da linha de comando não são alterados.
        self.entradas = {
            "partidas": ux.CampoNumerico(args.partidas, 1, 9999, inteiro=True),
            "velocidade": ux.CampoNumerico(args.passos_por_segundo, .1, 1000, piso_passo=1),
        }
        self.pressao = ux.Pressao()
        self.mouse_logico = (-1, -1)
        self._mao = False
        self.automatico = args.auto_iniciar or args.partidas > 1
        self.decisor_injetado = decisor
        self.pasta_runs = pasta_runs
        self.estado = "selecao"
        self.painel = True
        self.cheia = False
        self.rodando = True
        self._fechado = False
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
        self.pausa = Pausa()
        self.acordos = 0
        self.placar = 0.0
        self.sons = Sons()
        self.status = "Escolha o nível e a versão."

    @property
    def partidas(self):
        return self.entradas["partidas"].texto

    @partidas.setter
    def partidas(self, valor):
        self.entradas["partidas"].definir(valor)

    @property
    def velocidade(self):
        return self.entradas["velocidade"].texto

    @velocidade.setter
    def velocidade(self, valor):
        self.entradas["velocidade"].definir(valor)

    @property
    def editando(self):
        """True quando um campo de texto está em foco (teclas viram digitação)."""
        return self.foco in ux.CAMPOS

    def fonte(self, tamanho=20, mono=False):
        chave = tamanho, mono
        if chave not in self.fontes:
            self.fontes[chave] = pygame.font.SysFont("consolas" if mono else "segoeui", tamanho)
        return self.fontes[chave]

    def texto(self, conteudo, x, y, tamanho=20, cor=TEXTO, mono=False):
        self.canvas.blit(self.fonte(tamanho, mono).render(str(conteudo), True, cor), (x, y))

    def botao(self, titulo, retangulo, acao, ativo=True):
        rect = pygame.Rect(retangulo)
        pressionado = ativo and self.pressao.ativa(acao, perf_counter())
        hover = ativo and rect.collidepoint(self.mouse_logico)
        desenho = rect.inflate(-4, -4) if pressionado else rect
        pygame.draw.rect(self.canvas, ux.cor_botao(AZUL, ativo, hover, pressionado), desenho, border_radius=8)
        if not ativo:
            pygame.draw.rect(self.canvas, (62, 74, 92), rect, 1, border_radius=8)
        if self.foco == acao:
            pygame.draw.rect(self.canvas, TEXTO, rect.inflate(6, 6), 2, border_radius=10)
        imagem = self.fonte(18).render(titulo, True, TEXTO if ativo else MUTED)
        self.canvas.blit(imagem, imagem.get_rect(center=desenho.center))
        self.botoes.append((rect, acao, ativo))

    def alternador(self, nome, valor, retangulo, acao):
        self.botao(ux.rotulo_alternador(nome, valor), retangulo, acao)

    def campo(self, nome, rect):
        rect = pygame.Rect(rect)
        entrada = self.entradas[nome]
        focado = self.foco == nome
        pygame.draw.rect(self.canvas, CARTAO, rect, border_radius=5)
        pygame.draw.rect(self.canvas, AZUL if focado else MUTED, rect, 2 if focado else 1, border_radius=5)
        fonte = self.fonte(20)
        imagem = fonte.render(entrada.texto, True, TEXTO)
        self.canvas.blit(imagem, (rect.x + 10, rect.centery - imagem.get_height() // 2))
        if focado and entrada.cursor_visivel(perf_counter()):
            x = rect.x + 10 + imagem.get_width() + 2
            pygame.draw.line(self.canvas, TEXTO, (x, rect.y + 9), (x, rect.bottom - 10), 2)
        self.campos[nome] = rect

    def _enviar(self, tarefa, funcao):
        self.tarefa = tarefa
        self.futuro = self.pool.submit(funcao)

    def iniciar(self):
        if self._fechado or self.futuro:
            return
        for entrada in self.entradas.values():
            entrada.confirmar()
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
            if self.sessao and isinstance(self.sessao.decisor, LayaProcesso):
                self.sessao.decisor.fechar()
            self.sessao = Sessao(self.decisor_injetado or LayaProcesso(self.versao, self.args.cpu),
                                 self.nivel, quantidade, self.versao, pasta=self.pasta_runs, modo=self.modo)
        except Exception as exc:
            self.erro = f"Não foi possível criar a sessão: {exc}"
            return
        self.estado = "carregando"
        self.foco = None
        self.status = f"Carregando o Laya na {'CPU' if self.args.cpu else 'GPU'}..."
        self._enviar("carregar", lambda: getattr(self.sessao.decisor, "carregar", lambda: None)())

    def _nova_run(self):
        self.jogo = self.sessao.iniciar_run()
        self.registro = None
        self.resultado = None
        self.corpo_anterior = list(self.jogo.corpo)
        self.historico.clear()
        self.pausa.ativa = False
        self.probs = dict.fromkeys(TRADUCAO, 0.0)
        self.acordos = 0
        self.placar = 0
        self.estado = "jogando"
        self.status = "Laya está jogando; calculando e registrando decisões."
        self.proximo_passo = perf_counter()
        if self.jogo.fim:
            self.estado = "apurando"
            self._enviar("finalizar", self.sessao.finalizar_run)

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
                    self.status = "Salvando a partida e calculando a partida do algoritmo..."
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
        if self._fechado or self.pausa.ativa:
            return
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
        c1, c2, larg, alt = ux.COLUNA_1, ux.COLUNA_2, ux.LARGURA_ALTERNADOR, ux.ALTURA_LINHA
        n = NIVEIS[self.nivel]
        linha = ux.linha_grade
        # Coluna 1: alternadores e rótulos; coluna 2: campos e textos de apoio.
        self.alternador("Nível", f"{n.tamanho}x{n.tamanho}", (c1, linha(0), larg, alt), "nivel")
        self.texto(f"Vitória: {n.meta} gomos · Limite: {n.limite} passos sem comer", c2, linha(0) + 12)
        self.alternador("Laya", self.versao, (c1, linha(1), larg, alt), "versao")
        self.texto("v000 = modelo base, sem treino", c2, linha(1) + 12, 20, MUTED)
        self.alternador("Modo", "Normal" if self.modo == "normal" else "Rápido", (c1, linha(2), larg, alt), "modo")
        self.alternador("Automático", "sim" if self.automatico else "não", (c1, linha(3), larg, alt), "auto")
        self.texto("Partidas", c1, linha(4) + 12)
        self.campo("partidas", (c2, linha(4), 110, alt))
        self.texto("Passos/s", c1, linha(5) + 12)
        self.campo("velocidade", (c2, linha(5), 110, alt))
        self.botao("−1", (c2 + 122, linha(5), 48, alt), "menos")
        self.botao("+1", (c2 + 180, linha(5), 48, alt), "mais")
        self.botao("Iniciar · Conectar ao Laya", (c1, linha(6) + 20, larg, 55), "start")
        self.botao(TREINAR, (c2, linha(6) + 20, 300, 55), "treinar", False)
        self.texto("Dispositivo: " + ("CPU solicitado" if self.args.cpu else "CUDA se disponível, senão CPU"), c1, 765, 19, MUTED)
        self.texto("Enter: iniciar     Tab: próximo controle     ← →: mudar opção     F11: tela cheia     Esc: voltar", c1, 800, 19, MUTED)

    def controles_velocidade(self, x, y):
        self.texto("Passos/s", x, y + 10, 19)
        self.botao("−1", (x + 105, y, 48, 44), "menos")
        self.campo("velocidade", (x + 164, y, 82, 44))
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
            self.texto(f"Partidas concluídas: {s.indice} de {total}", 100, 330, 32)
            pygame.draw.rect(self.canvas, CARTAO, (100, 395, 1000, 26), border_radius=10)
            pygame.draw.rect(self.canvas, VERDE, (100, 395, int(1000 * s.indice / total), 26), border_radius=10)
            segundos = perf_counter() - s.inicio
            self.texto(f"Tempo: {segundos:.0f} s", 100, 460, 24)
            if s.resultados:
                pontos = sum(r["comparacao"]["geral"]["laya"]["pontos"] for r in s.resultados)
                self.texto(f"Resumo parcial: {pontos} pontos nas partidas concluídas", 100, 505, 24)
            if self.jogo:
                self.texto(f"Partida atual: {self.jogo.passos} passos · {self.jogo.pontos} pontos", 100, 555, 24)
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
        titulo = "Resumo da sessão" if self.modo == "rapido" else f"Resultado da partida {s.indice}"
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
        self.texto(f"Concordância: {concordancia:.1%} · Latência média da última partida: {media:.1f} ms", 90, 505, 22)
        pps = sum(r["passos_por_segundo"] for r in resultados) / max(1, len(resultados))
        self.texto(f"Velocidade medida: {pps:.2f} passos/s · Registros em {s.pasta.name}", 90, 550, 21, MUTED)
        self.hardware(90, 605)
        if not s.documento["valida_para_treino"]:
            self.texto("Sessão excluída do treino: o algoritmo perdeu uma partida.", 90, 640, 22, VERMELHO)
        if not s.concluida:
            self.botao("Próxima partida", (90, 680, 240, 50), "proxima")
        self.botao("Repetir · Nova sessão", (360, 680, 240, 50), "retry")
        self.botao("Seleção", (630, 680, 180, 50), "selecao")
        self.botao(TREINAR, (845, 680, 300, 50), "treinar", False)

    def _atualizar_ponteiro(self):
        """Posição do mouse no canvas (para hover) e cursor de mãozinha sobre botões ativos."""
        destino = getattr(self, "destino", None) or self.tela.get_rect()
        try:
            self.mouse_logico = mouse_para_logico(pygame.mouse.get_pos(), tuple(destino))
        except ZeroDivisionError:
            self.mouse_logico = (-1, -1)

    def _cursor(self):
        mao = any(ativo and r.collidepoint(self.mouse_logico) for r, _, ativo in self.botoes)
        if mao != self._mao:
            self._mao = mao
            try:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if mao else pygame.SYSTEM_CURSOR_ARROW)
            except pygame.error:
                pass

    def desenhar(self):
        self._atualizar_ponteiro()
        self.canvas.fill(FUNDO)
        self.botoes.clear()
        self.campos.clear()
        self.texto("LAYA GAMES / COBRINHA", 25, 20, 22, MUTED)
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
            self.texto(f"Partida {self.sessao.indice + 1}/{self.sessao.partidas}", 350, 65, 22)
            self.hardware(600, 28)
            self.desenhar_tabuleiro()
            if self.painel:
                self.desenhar_painel()
            self.controles_velocidade(30, 805)
            self.botao("Repetir", (365, 805, 100, 44), "retry", not self.futuro)
            self.alternador("Automático", "sim" if self.automatico else "não", (485, 805, 210, 44), "auto")
            self.botao(TREINAR, (710, 805, 270, 44), "treinar", False)
        if self.erro:
            # Quebrar mensagens de exceção para caberem na janela.
            for i in range(0, min(len(self.erro), 330), 110):
                self.texto(self.erro[i:i + 110], 30, 740 + (i // 110) * 24, 19, VERMELHO)
        self.pausa.desenhar(self)
        self._cursor()
        janela = self.tela.get_rect()
        escala = min(janela.width / 1280, janela.height / 860)
        tamanho = (max(1, int(1280 * escala)), max(1, int(860 * escala)))
        self.destino = pygame.Rect(0, 0, *tamanho)
        self.destino.center = janela.center
        self.tela.fill(FUNDO)
        self.tela.blit(pygame.transform.smoothscale(self.canvas, tamanho), self.destino)
        pygame.display.flip()

    def acionar(self, acao, passo=1):
        """`passo` = -1 volta a opção anterior dos alternadores (clique direito / seta)."""
        if acao == "nivel":
            self.nivel = ux.ciclar(NIVEIS, self.nivel, passo)
        elif acao == "versao":
            self.versao = ux.ciclar(self.versoes, self.versao, passo)
        elif acao == "modo":
            self.modo = "rapido" if self.modo == "normal" else "normal"
            self.velocidade = "5" if self.modo == "rapido" else "1"
        elif acao == "auto":
            self.automatico = not self.automatico
        elif acao in ("mais", "menos"):
            self.entradas["velocidade"].mudar(1 if acao == "mais" else -1, perf_counter())
        elif acao == "start":
            self.iniciar()
        elif acao == "proxima":
            self._nova_run()
        elif acao in ("selecao", "retry") and not self.futuro:
            if self.sessao and not self.sessao.concluida:
                self.sessao.interromper()
            self.estado = "selecao"
            self.pausa.ativa = False
            self.erro = ""
            self.foco = None
            if acao == "retry":
                self.iniciar()

    def _focar(self, nome):
        """Muda o foco; sair de um campo confirma (valor inválido volta ao último válido)."""
        if self.foco in ux.CAMPOS and self.foco != nome:
            self.entradas[self.foco].confirmar()
        self.foco = nome
        if nome in ux.CAMPOS:
            self.entradas[nome].ultima_digitacao = perf_counter()

    def _tecla(self, event):
        tecla = event.key
        if tecla in (pygame.K_p, pygame.K_SPACE) and not self.editando:
            self.pausa.alternar(self.estado)
        elif tecla == pygame.K_F11:
            self.cheia = not self.cheia
            self.tela = pygame.display.set_mode((0, 0), pygame.FULLSCREEN) if self.cheia else pygame.display.set_mode(self.tamanho_inicial, pygame.RESIZABLE)
        elif tecla == pygame.K_TAB:
            if self.estado == "selecao":
                recuar = getattr(event, "mod", 0) & pygame.KMOD_SHIFT
                self._focar(ux.proximo_foco(ux.ORDEM_FOCO, self.foco, -1 if recuar else 1))
            else:
                self.painel = not self.painel
        elif tecla == pygame.K_ESCAPE:
            if self.editando:
                self._focar(None)
            elif not self.futuro:
                self.acionar("selecao")
        elif tecla in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.editando:
                self.entradas[self.foco].confirmar()
            if self.estado == "selecao":
                self.acionar("start")
            else:
                self._focar(None)
        elif tecla in (pygame.K_RIGHT, pygame.K_UP, pygame.K_LEFT, pygame.K_DOWN):
            passo = 1 if tecla in (pygame.K_RIGHT, pygame.K_UP) else -1
            if self.foco in ux.ALTERNADORES:
                self.acionar(self.foco, passo)
            elif self.editando:
                self.entradas[self.foco].mudar(passo, perf_counter())
        elif self.editando:
            entrada = self.entradas[self.foco]
            if tecla == pygame.K_BACKSPACE:
                entrada.apagar(perf_counter())
            elif event.unicode:
                entrada.digitar(event.unicode, perf_counter())

    def _clique(self, event):
        pos = mouse_para_logico(event.pos, tuple(getattr(self, "destino", self.tela.get_rect())))
        if event.button == 1:
            campo = next((nome for nome, r in self.campos.items() if r.collidepoint(pos)), None)
            if campo:
                self._focar(campo)
                return
        for r, acao, ativo in self.botoes:
            if ativo and r.collidepoint(pos):
                if event.button == 3 and acao not in ux.ALTERNADORES:
                    return
                self.pressao.pressionar(acao, perf_counter())
                self._focar(acao if acao in ux.ALTERNADORES else None)
                self.acionar(acao, -1 if event.button == 3 else 1)
                return
        if event.button == 1:
            self._focar(None)

    def evento(self, event):
        if event.type == pygame.QUIT:
            self.rodando = False
        elif event.type == pygame.VIDEORESIZE and not self.cheia:
            self.tela = pygame.display.set_mode((max(1, event.w), max(1, event.h)), pygame.RESIZABLE)
        elif event.type == pygame.KEYDOWN:
            self._tecla(event)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            self._clique(event)

    def resumo_terminal(self):
        linhas = ([self.erro] if self.erro else []) + ["Resumo da sessão"]
        total_laya = total_algoritmo = 0
        for i, resultado in enumerate(self.sessao.resultados if self.sessao else [], 1):
            geral = resultado["comparacao"]["geral"]
            laya = geral["laya"]["pontos"]
            algoritmo = geral["algoritmo"]["pontos"]
            linhas.append(f"Partida {i}: Laya: {laya} pontos · Algoritmo: {algoritmo} pontos")
            total_laya += laya
            total_algoritmo += algoritmo
        linhas.append(f"Totais: Laya: {total_laya} pontos · Algoritmo: {total_algoritmo} pontos")
        return "\n".join(linhas)

    def executar(self, max_frames=None):
        clock = pygame.time.Clock()
        frames = 0
        try:
            if self.args.auto_iniciar:
                self.iniciar()
            while self.rodando and (max_frames is None or frames < max_frames):
                if self.args.auto_iniciar and self.erro:
                    break
                dt = clock.tick(60) / 1000
                for event in pygame.event.get():
                    self.evento(event)
                self.atualizar(dt)
                if self.args.auto_iniciar and (self.erro or
                        self.estado == "resultado" and self.sessao.concluida):
                    break
                self.desenhar()
                frames += 1
        except Exception as exc:
            if not self.args.auto_iniciar:
                raise
            self.erro = f"Falha: {type(exc).__name__}: {exc}"
            self.estado = "erro"
        finally:
            try:
                self.fechar()
            finally:
                if self.args.auto_iniciar and (self.erro or
                        self.sessao and self.sessao.concluida):
                    print(self.resumo_terminal())

    def fechar(self):
        if self._fechado:
            return
        self._fechado = True
        self.rodando = False
        try:
            if self.sessao and isinstance(self.sessao.decisor, LayaProcesso):
                self.sessao.decisor.fechar()
            # recv() já foi desbloqueado; preservar a única thread de escrita
            # antes de salvar o checkpoint da sessão.
            self.pool.shutdown(wait=True, cancel_futures=True)
            if self.sessao and not self.sessao.concluida:
                self.sessao.interromper()
        finally:
            pygame.quit()
