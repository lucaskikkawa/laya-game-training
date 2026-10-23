"""A sessão é a unidade de seleção: nunca aproveitar só suas runs vitoriosas."""
import json
from pathlib import Path


def valida_para_treino(documento):
    """Exige conclusão e marcação explícita; arquivos antigos ficam de fora."""
    return (documento.get("status") == "concluida"
            and documento.get("valida_para_treino") is True
            and documento.get("motivo") is None)


def selecionar_sessoes(pasta):
    """Retorna caminhos de sessao.json elegíveis, em ordem estável."""
    selecionadas = []
    for arquivo in sorted(Path(pasta).glob("*/sessao.json")):
        documento = json.loads(arquivo.read_text(encoding="utf-8"))
        if valida_para_treino(documento):
            selecionadas.append(arquivo)
    return selecionadas
