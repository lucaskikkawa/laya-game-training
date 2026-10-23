from concurrent.futures import Future
import json

import pytest

from scripts import qa_algoritmo as qa


class PoolImediato:
    """Executa só o diagnóstico mockado, sem partidas reais ou subprocessos."""
    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def submit(self, funcao, tarefa):
        futuro = Future()
        futuro.set_result(funcao(tarefa))
        return futuro


def test_padrao_200_exige_100_por_cento(tmp_path, monkeypatch, capsys):
    tarefas = []
    def diagnosticar(tarefa):
        tarefas.append(tarefa)
        n, i = tarefa
        return n, {'partida': i} if (n, i) == (25, 199) else None
    monkeypatch.setattr(qa, 'ProcessPoolExecutor', PoolImediato)
    monkeypatch.setattr(qa, 'diagnosticar', diagnosticar)
    saida = tmp_path / 'qa.json'
    assert qa.main(['--saida', str(saida)]) == 1
    assert {n for n, _ in tarefas} == {15, 20, 25}
    assert len(tarefas) == 600
    resultados = json.loads(saida.read_text())['resultados']
    assert [r['partidas'] for r in resultados] == [200] * 3
    assert [r['vitorias'] for r in resultados] == [200, 200, 199]
    assert 'REPROVADO (exigido 100%)' in capsys.readouterr().out


def test_repeticao_usa_so_listas_salvas_e_preserva_falhas(tmp_path, monkeypatch, capsys):
    casos = [{'nivel': 25, 'partida': i, 'comidas': [[8, 7], [0, 0]]} for i in (62, 128)]
    arquivo = tmp_path / 'falhas.json'
    arquivo.write_text(json.dumps(casos))
    tarefas = []
    def diagnosticar(tarefa):
        tarefas.append(tarefa)
        return tarefa[0], (None if tarefa[1] == 62 else {
            'partida': 128, 'resumo': {'morte': 'limite_sem_comer'},
            'comidas': tarefa[2], 'erro': None})
    monkeypatch.setattr(qa, 'ProcessPoolExecutor', PoolImediato)
    monkeypatch.setattr(qa, 'diagnosticar', diagnosticar)
    saida = tmp_path / 'repeticao.json'
    assert qa.main(['--repetir-falhas', str(arquivo), '--saida', str(saida)]) == 1
    assert tarefas == [(25, c['partida'], c['comidas']) for c in casos]
    assert json.loads(arquivo.read_text()) == casos
    assert json.loads(saida.read_text())['resultados'][0]['falhas'][0]['partida'] == 128
    texto = capsys.readouterr().out
    assert 'partida 62: VITÓRIA' in texto
    assert 'partida 128: FALHA (limite_sem_comer)' in texto
    assert 'RESULTADO FINAL: 1/2' in texto


def test_diagnostico_repetido_nao_sorteia_e_preserva_erro_inicial(monkeypatch):
    def proibido(n):
        pytest.fail('Repetição não pode sortear')
    monkeypatch.setattr(qa, 'lista_comidas', proibido)
    nivel, falha = qa.diagnosticar((15, 62, [(7, 7)]))
    assert nivel == 15 and falha['partida'] == 62
    assert falha['erro'] is None
    assert falha['resumo']['morte'] == 'lista_esgotada'
    assert falha['comidas'] == [(7, 7)]


def test_carrega_relatorio_completo(tmp_path):
    arquivo = tmp_path / 'qa.json'
    arquivo.write_text(json.dumps({'resultados': [
        {'nivel': 15, 'falhas': []},
        {'nivel': 25, 'falhas': [{'partida': 62, 'comidas': [[0, 0]]}]}]}))
    assert qa.carregar_falhas(arquivo) == [(25, 62, [[0, 0]])]


def test_qa_rejeita_nivel_adiado():
    with pytest.raises(SystemExit):
        qa.main(['--nivel', '30'])
