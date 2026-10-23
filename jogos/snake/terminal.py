"""Execução sem SDL e painel ANSI; formatação independente do modelo."""
from concurrent.futures import CancelledError, ThreadPoolExecutor, TimeoutError
import os
import shutil
import sys
from threading import Event
from time import perf_counter

from nucleo.laya_processo import LayaProcesso
from .sessao import Sessao


def duracao(segundos):
    if segundos is None:
        return "calculando"
    minutos, segundos = divmod(int(segundos), 60)
    return f"{minutos:02d}:{segundos:02d}"


def painel(d):
    """Recebe somente um snapshot de valores, sem acessar a sessão em execução."""
    feitos, total = d['feitos'], d['total']
    media = d['tempo'] / feitos if feitos else None
    barra = '#' * int(20 * feitos / total)
    return '\n'.join([
        f"Laya Games | Nível {d['nivel']} | Laya {d['versao']}",
        f"Dispositivo: {d['hardware'].get('gpu') or d['hardware'].get('dispositivo', 'CPU')} | "
        f"VRAM usada: {d['hardware'].get('vram_alocada_mb', 0):.0f} MB",
        f"Sessão [{barra:<20}] {feitos}/{total} | {d['fase']}",
        f"Tempo: {duracao(d['tempo'])} | Estimado pro fim: {duracao(media * (total-feitos) if media is not None else None)}",
        f"Médio por partida: {duracao(media)}",
        f"Partida atual: {min(feitos+1, total)}/{total} | Comidas: {d['comidas']} | Meta: {d['gomos']}/{d['meta']} gomos",
        f"Passos: {d['passos']} | Sem comer: {d['sem_comer']}/{d['limite']}",
        f"Pontos Laya x algoritmo: {d['pontos']} x {d['algoritmo']}",
        f"Jogadas iguais: {d['acordos']:.1%} | Confiança média: {d['confianca']:.1%}",
        f"Decisão: {d['latencia']:.2f} ms | Jogadas/s: {d['taxa']:.2f}",
        f"Acumulado Laya x algoritmo: {d['totais'][0]} x {d['totais'][1]}",
        f"Melhor partida: {d['melhor']} | Vitórias: {d['vitorias']}",
        f"Fim: parede {d['fins']['parede']} / corpo {d['fins']['corpo']} / limite sem comer {d['fins']['limite_sem_comer']}",
        "Ctrl+C: parar e salvar os dados já rodados.",
    ])


def resumo(sessao):
    linhas = ['Resumo da sessão', 'Partida | Laya (pontos) | Algoritmo (pontos)', '--------+---------------+-------------------']
    totais = [0, 0]
    for r in sessao.resultados if sessao else []:
        valores = [r['comparacao']['geral'][a]['pontos'] for a in ('laya', 'algoritmo')]
        linhas.append(f"{r['run']:7} | {valores[0]:13} | {valores[1]:18}")
        totais = [a+b for a, b in zip(totais, valores)]
    linhas.append(f"Total   | {totais[0]:13} | {totais[1]:18}")
    if sessao:
        linhas.append(f"Status: {sessao.documento['status']} | Dados salvos em: {sessao.pasta.resolve()}")
        if sessao.jogo and not sessao.concluida:
            linhas.append(f"Última partida Laya: {sessao.jogo.passos} passos, {sessao.jogo.pontos} pontos (consulte os arquivos da run).")
    return '\n'.join(linhas)


class TelaTerminal:
    def __init__(self, saida):
        self.saida = saida
        self.ansi = saida.isatty()
        self.modo_anterior = None
        if self.ansi and os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            self.kernel = ctypes.windll.kernel32
            self.kernel.GetStdHandle.restype = wintypes.HANDLE
            self.kernel.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            self.kernel.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            self.handle = self.kernel.GetStdHandle(-11)
            modo = ctypes.c_ulong()
            if self.kernel.GetConsoleMode(self.handle, ctypes.byref(modo)):
                self.modo_anterior = modo.value
                self.kernel.SetConsoleMode(self.handle, modo.value | 4)
        if self.ansi:
            saida.write('\x1b[2J\x1b[H\x1b[?25l')

    def atualizar(self, conteudo):
        if self.ansi:
            colunas, linhas = shutil.get_terminal_size()
            texto = '\n'.join(l[:max(1, colunas-1)] for l in conteudo.splitlines()[:max(1, linhas-1)])
            self.saida.write('\x1b[H' + texto.replace('\n', '\x1b[K\n') + '\x1b[K\x1b[J')
            self.saida.flush()

    def fechar(self):
        if self.ansi:
            self.saida.write('\x1b[H\x1b[J\x1b[?25h')
            self.saida.flush()
        if self.modo_anterior is not None:
            self.kernel.SetConsoleMode(self.handle, self.modo_anterior)


def executar(args, decisor=None, pasta=None, saida=None):
    saida = saida or sys.stdout
    decisor = decisor if decisor is not None else LayaProcesso(args.versao, args.cpu)
    tela = TelaTerminal(saida)
    parar = Event()
    sessao = None
    estado = {}
    erro = ''
    codigo = 0

    def publicar(fase, algoritmo=0):
        if parar.is_set():
            raise CancelledError()
        agora = perf_counter()
        if fase == estado.get('fase') and agora - estado.get('publicado_em', 0) < .1:
            return
        estado['fase'], estado['publicado_em'] = fase, agora
        jogo = sessao.jogo
        registros = sessao.registros
        resumos = [r['comparacao']['geral'] for r in sessao.resultados]
        tempo_run = perf_counter() - sessao.inicio_run if jogo else 0
        estado['snapshot'] = dict(
            feitos=sessao.indice, total=sessao.partidas, nivel=sessao.nivel, versao=sessao.versao,
            hardware=decisor.telemetria() if hasattr(decisor, 'telemetria') else {'dispositivo': 'CPU'},
            tempo=perf_counter()-sessao.inicio, fase=fase,
            comidas=jogo.comidas_consumidas if jogo else 0, gomos=len(jogo.corpo) if jogo else 3,
            meta=jogo.nivel.meta if jogo else 0, limite=jogo.nivel.limite if jogo else 0,
            passos=jogo.passos if jogo else 0, sem_comer=jogo.sem_comer if jogo else 0,
            pontos=jogo.pontos if jogo else 0, algoritmo=algoritmo,
            acordos=sum(r['escolha'] == r['jogada_ideal'] for r in registros)/max(1,len(registros)),
            confianca=estado.get('confianca', 0)/max(1,len(registros)),
            latencia=sum(r['latencia_ms'] for r in registros)/max(1,len(registros)),
            taxa=jogo.passos/max(tempo_run, 1e-9) if jogo else 0,
            totais=[sum(r[a]['pontos'] for r in resumos) for a in ('laya','algoritmo')],
            melhor=max((r['laya']['pontos'] for r in resumos), default=0),
            vitorias=sum(r['laya']['vitoria'] for r in resumos),
            fins={m:sum(r['laya']['morte']==m for r in resumos) for m in ('parede','corpo','limite_sem_comer')})

    def rodar():
        publicar('Carregando o Laya...')
        getattr(decisor, 'carregar', lambda: None)()
        while not sessao.concluida:
            publicar('Iniciando partida')
            sessao.iniciar_run()
            estado['confianca'] = 0
            while not sessao.jogo.fim:
                inicio = perf_counter()
                publicar('Laya jogando (algoritmo: aguardando apuração)')
                r = sessao.passo()
                estado['confianca'] += r['confianca']
                publicar('Laya jogando (algoritmo: aguardando apuração)')
                if parar.wait(max(0, 1/args.passos_por_segundo-(perf_counter()-inicio))):
                    raise CancelledError()
            sessao.finalizar_run(lambda g: publicar('Apurando algoritmo', g.pontos))
        publicar('Concluída', sessao.resultados[-1]['comparacao']['geral']['algoritmo']['pontos'])

    try:
        sessao = Sessao(decisor, args.nivel, args.partidas, args.versao, pasta=pasta, modo=args.modo)
        with ThreadPoolExecutor(max_workers=1) as pool:
            futuro = pool.submit(rodar)
            try:
                while True:
                    if 'snapshot' in estado:
                        d = dict(estado['snapshot'], tempo=perf_counter()-sessao.inicio)
                        tela.atualizar(painel(d))
                    try:
                        futuro.result(timeout=.25)
                        break
                    except TimeoutError:
                        if futuro.done():
                            raise
            except KeyboardInterrupt:
                codigo = 130
                parar.set()
                if isinstance(decisor, LayaProcesso):
                    decisor.fechar()
                try:
                    futuro.result()
                except Exception:
                    pass
                sessao.interromper()
    except Exception as exc:
        codigo = 1
        erro = f'Falha: {type(exc).__name__}: {exc}'
        if sessao:
            sessao.interromper(exc)
    finally:
        try:
            getattr(decisor, 'fechar', lambda: None)()
        finally:
            tela.fechar()
    if erro:
        print(erro, file=saida)
    if codigo == 130:
        print('Interrompido por Ctrl+C; dados preservados.', file=saida)
    print(resumo(sessao), file=saida)
    return codigo
