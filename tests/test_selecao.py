import json

import pytest

from treino.selecao import selecionar_sessoes, valida_para_treino


@pytest.mark.parametrize('alteracoes', [
    {'valida_para_treino': False, 'motivo': 'algoritmo_perdeu'},
    {'status': 'em_andamento'}, {'status': 'interrompida'}, {'status': 'erro'},
    {'motivo': 'algoritmo_perdeu'}, {'valida_para_treino': None},
])
def test_selecao_rejeita_sessao_inapta(alteracoes):
    documento = {'status': 'concluida', 'valida_para_treino': True, 'motivo': None}
    assert not valida_para_treino({**documento, **alteracoes})


def test_selecao_ignora_sessao_inteira_e_legadas(tmp_path):
    documentos = {
        'valida': {'status': 'concluida', 'valida_para_treino': True, 'motivo': None},
        'invalida': {'status': 'concluida', 'valida_para_treino': False,
                     'motivo': 'algoritmo_perdeu', 'resultados': [{'vitoria': True}]},
        'legada': {'status': 'concluida'},
    }
    for nome, documento in documentos.items():
        pasta = tmp_path / nome
        pasta.mkdir()
        (pasta / 'sessao.json').write_text(json.dumps(documento))
    assert selecionar_sessoes(tmp_path) == [tmp_path / 'valida' / 'sessao.json']
