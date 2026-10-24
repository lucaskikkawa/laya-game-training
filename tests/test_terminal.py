import io
import json
import subprocess
import sys

import pytest

from jogos.snake.__main__ import argumentos
from jogos.snake import terminal
from test_sessao import MockLaya


@pytest.mark.parametrize('argv', [
    ['--sem-janela'], ['--sem-janela', '--partidas', '1'],
    ['--sem-janela', '--modo', 'rapido'],
    ['--sem-janela', '--modo', 'rapido', '--partidas', '0'],
])
def test_sem_janela_exige_partidas_e_rapido(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        argumentos(argv)
    assert exc.value.code == 2
    assert capsys.readouterr().err


def args():
    return argumentos(['--sem-janela', '--modo', 'rapido', '--partidas', '1',
                       '--passos-por-segundo', '100000'])


def test_sem_importar_pygame():
    codigo = 'import sys; from jogos.snake import terminal; assert "pygame" not in sys.modules'
    subprocess.run([sys.executable, '-c', codigo], check=True)


def test_main_escolhe_terminal(monkeypatch):
    from jogos.snake import __main__
    monkeypatch.setattr(__main__, 'argumentos', args)
    monkeypatch.setattr(terminal, 'executar', lambda a: 42)
    assert __main__.main() == 42


def test_execucao_salva_e_painel_tem_campos(tmp_path, monkeypatch):
    from jogos.snake.regras import NIVEIS, Nivel
    monkeypatch.setitem(NIVEIS, 15, Nivel(15, 4, 60))
    snapshots = []
    monkeypatch.setattr(terminal.TelaTerminal, 'atualizar', lambda self, texto: snapshots.append(texto))
    saida = io.StringIO()
    assert terminal.executar(args(), MockLaya(), tmp_path, saida) == 0
    pasta, = tmp_path.iterdir()
    dados = json.loads((pasta/'sessao.json').read_text())
    assert dados['status'] == 'concluida' and len(dados['resultados']) == 1
    assert (pasta/'run_0001_algoritmo.json').exists()
    assert 'Algoritmo (pontos)' in saida.getvalue() and str(pasta) in saida.getvalue()
    texto = '\n'.join(snapshots)
    for campo in ('Nível', 'VRAM', 'Sessão', 'Estimado', 'Médio', 'Comidas', 'gomos',
                  'Passos', 'Sem comer', 'Pontos', 'iguais', 'Confiança', 'ms', 'Jogadas/s',
                  'Acumulado', 'Melhor', 'Vitórias', 'parede', 'corpo', 'limite sem comer'):
        assert campo in texto


def test_falha_antes_do_resumo_e_parcial_salvo(tmp_path):
    class Falha(MockLaya):
        def decidir(self, *args):
            raise RuntimeError('modelo falhou')
    saida = io.StringIO()
    assert terminal.executar(args(), Falha(), tmp_path, saida) == 1
    texto = saida.getvalue()
    assert texto.index('Falha:') < texto.index('Resumo')
    pasta, = tmp_path.iterdir()
    assert (pasta/'run_0001_laya_parcial.json').exists()


def test_ctrl_c_preserva_passos_e_fecha(tmp_path, monkeypatch):
    original = terminal.TelaTerminal.atualizar
    def interromper(self, texto):
        if 'Passos: 1 ' in texto:
            raise KeyboardInterrupt
        original(self, texto)
    monkeypatch.setattr(terminal.TelaTerminal, 'atualizar', interromper)
    a = args()
    a.passos_por_segundo = 1
    saida = io.StringIO()
    assert terminal.executar(a, MockLaya(), tmp_path, saida) == 130
    pasta, = tmp_path.iterdir()
    parcial = json.loads((pasta/'run_0001_laya_parcial.json').read_text())
    assert parcial['resumo']['passos'] >= 1
    assert json.loads((pasta/'sessao.json').read_text())['status'] == 'interrompida'


def test_ansi_redesenha_e_restaura_cursor(monkeypatch):
    class TTY(io.StringIO):
        def isatty(self):
            return True
    saida = TTY()
    tela = terminal.TelaTerminal(saida)
    tela.atualizar('primeira\nsegunda')
    tela.atualizar('curta')
    tela.fechar()
    texto = saida.getvalue()
    assert '\x1b[Hcurta\x1b[K\x1b[J' in texto
    assert texto.endswith('\x1b[?25h')


def test_interrupcao_durante_apuracao_preserva_ambos_agentes(tmp_path):
    from concurrent.futures import CancelledError
    from jogos.snake.sessao import Sessao
    s = Sessao(MockLaya(), pasta=tmp_path, comidas=[(0, 0)])
    s.iniciar_run()
    while not s.jogo.fim:
        s.passo()
    def cancelar(gabarito):
        if gabarito.passos == 1:
            raise CancelledError()
    with pytest.raises(CancelledError):
        s.finalizar_run(cancelar)
    s.interromper()
    laya = json.loads((s.pasta/'run_0001_laya.json').read_text())
    algoritmo = json.loads((s.pasta/'run_0001_algoritmo.json').read_text())
    assert laya['status'] == 'concluida'
    assert algoritmo['status'] == 'interrompida'
    assert algoritmo['snapshot_final']['passo'] == 1
    assert s.documento['status'] == 'interrompida'
    assert not (s.pasta/'run_0001_laya_parcial.json').exists()
