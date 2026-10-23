"""Lógica do retoque de UX (v0.1.2), sem Pygame: testável fora do desenho."""
import re

# Grade da tela de seleção: rótulos/alternadores na coluna 1, campos e textos na coluna 2.
COLUNA_1 = 84
COLUNA_2 = 380
LARGURA_ALTERNADOR = 260
ALTURA_LINHA = 46
TOPO_GRADE = 300
PASSO_LINHA = 60

ALTERNADORES = frozenset({"nivel", "versao", "modo", "auto"})
CAMPOS = frozenset({"partidas", "velocidade"})
# Ordem do Tab na tela de seleção.
ORDEM_FOCO = ("nivel", "versao", "modo", "auto", "partidas", "velocidade", "start")

DURACAO_CLIQUE = .1
PERIODO_CURSOR = .5


def linha_grade(indice: int) -> int:
    """Topo (y) da linha `indice` da grade; espaçamento sempre igual."""
    return TOPO_GRADE + indice * PASSO_LINHA


def rotulo_alternador(nome: str, valor) -> str:
    return f"<  {nome}: {valor}  >"


def ciclar(opcoes, atual, passo=1):
    """Próxima (passo=1) ou anterior (passo=-1) opção, dando a volta nas pontas."""
    opcoes = list(opcoes)
    return opcoes[(opcoes.index(atual) + passo) % len(opcoes)]


def proximo_foco(ordem, atual, passo=1):
    """Tab / Shift+Tab: sem foco, começa pelo primeiro (ou pelo último, se voltando)."""
    ordem = list(ordem)
    if atual not in ordem:
        return ordem[0] if passo > 0 else ordem[-1]
    return ordem[(ordem.index(atual) + passo) % len(ordem)]


def _misturar(cor, alvo, fator):
    return tuple(round(c + (a - c) * fator) for c, a in zip(cor, alvo))


def cor_botao(base, ativo=True, hover=False, pressionado=False, desativado=(43, 53, 68)):
    """Mesma cor do botão normal; clareia no hover e escurece enquanto afundado."""
    if not ativo:
        return desativado
    if pressionado:
        return _misturar(base, (0, 0, 0), .3)
    if hover:
        return _misturar(base, (255, 255, 255), .18)
    return base


class Pressao:
    """Lembra qual botão foi clicado para mostrá-lo afundado por ~100 ms."""

    def __init__(self, duracao=DURACAO_CLIQUE):
        self.duracao = duracao
        self.chave = None
        self.ate = 0.0

    def pressionar(self, chave, agora):
        self.chave, self.ate = chave, agora + self.duracao

    def ativa(self, chave, agora):
        return self.chave == chave and agora < self.ate


class CampoNumerico:
    """Texto de um campo numérico que nunca fica com valor inválido ao confirmar.

    Letras e valores acima do máximo são recusados na digitação; valores vazios ou
    abaixo do mínimo voltam ao último valor válido ao confirmar.
    """

    def __init__(self, texto, minimo, maximo, inteiro=False, casas=2, passo=1, piso_passo=None):
        self.minimo, self.maximo, self.inteiro, self.casas = minimo, maximo, inteiro, casas
        self.passo = passo
        self.piso_passo = minimo if piso_passo is None else piso_passo
        self.texto = ""
        self.ultimo_valido = ""
        self.ultima_digitacao = 0.0
        self.definir(texto)

    def _valor(self, texto):
        try:
            return int(texto) if self.inteiro else float(texto)
        except ValueError:
            return None

    def _formatar(self, valor):
        return str(int(valor)) if self.inteiro else f"{valor:g}"

    def _padrao(self):
        return re.compile(r"\d{1,4}" if self.inteiro else rf"\d{{0,4}}(\.\d{{0,{self.casas}}})?")

    def valido(self, texto):
        valor = self._valor(texto)
        return valor is not None and self.minimo <= valor <= self.maximo and valor == valor

    @property
    def valor(self):
        return self._valor(self.ultimo_valido)

    def definir(self, texto):
        """Define o texto sem aplicar limites (ex.: valor vindo da linha de comando)."""
        texto = str(texto).removesuffix(".0")
        if self._valor(texto) is None:
            texto = self.ultimo_valido or self._formatar(self.minimo)
        self.texto = self.ultimo_valido = texto

    def digitar(self, caractere, agora=0.0):
        """Aceita só dígitos (e um ponto, nos decimais) que mantenham o valor dentro do máximo."""
        if len(caractere) != 1 or caractere not in "0123456789.":
            return False
        candidato = self.texto + caractere
        if not self._padrao().fullmatch(candidato):
            return False
        valor = self._valor(candidato if candidato != "." else "0")
        if valor is not None and valor > self.maximo:
            return False
        self.texto = candidato
        self.ultima_digitacao = agora
        if self.valido(candidato):
            self.ultimo_valido = candidato
        return True

    def apagar(self, agora=0.0):
        self.texto = self.texto[:-1]
        self.ultima_digitacao = agora
        if self.valido(self.texto):
            self.ultimo_valido = self.texto

    def confirmar(self):
        """Fim da edição: texto inválido/fora do limite volta ao último valor válido."""
        if self.valido(self.texto):
            self.ultimo_valido = self.texto = self._formatar(self._valor(self.texto))
        else:
            self.texto = self.ultimo_valido
        return self.texto

    def mudar(self, direcao, agora=0.0):
        """Setas e botões ±: soma `passo`, sem sair dos limites (e sem cair abaixo do piso do passo)."""
        self.confirmar()
        atual = self.valor
        novo = atual + direcao * self.passo
        novo = min(max(novo, min(self.piso_passo, atual)), self.maximo)
        self.texto = self.ultimo_valido = self._formatar(novo)
        self.ultima_digitacao = agora

    def cursor_visivel(self, agora):
        """Pisca a cada 0,5 s; reinicia (visível) a cada tecla digitada."""
        return int(max(0.0, agora - self.ultima_digitacao) / PERIODO_CURSOR) % 2 == 0
