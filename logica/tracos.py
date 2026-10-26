"""Calcula quais traços um time ativa e quanto falta para o próximo nível."""

from collections import Counter
from dataclasses import dataclass

from logica.catalogo import Traco

NOMES_ESTILO = {0: "Inativo", 1: "Bronze", 2: "Prata", 3: "Ouro", 4: "Prismático"}


@dataclass
class TracoNoTime:
    traco: Traco
    quantidade: int
    nivel_ativo: int | None    # breakpoint atingido (ex.: 4), ou None
    estilo: int                # 0 se inativo
    proximo_nivel: int | None  # próximo breakpoint, ou None se já está no máximo

    @property
    def ativo(self):
        return self.estilo > 0

    @property
    def faltam(self):
        return self.proximo_nivel - self.quantidade if self.proximo_nivel else 0

    @property
    def nome_estilo(self):
        return NOMES_ESTILO.get(self.estilo, "")

    def texto(self):
        """Ex.: 'Blossom 5/7' ou 'Avatar'."""
        if self.traco.unico:
            return self.traco.nome
        alvo = self.proximo_nivel or self.nivel_ativo
        return f"{self.traco.nome} {self.quantidade}/{alvo}"


def contar(campeoes, emblemas=()):
    """Conta quantos campeões diferentes de cada traço o time tem (repetidos não contam)."""
    contagem = Counter()
    for campeao in {c.id: c for c in campeoes}.values():
        contagem.update(campeao.tracos)
    contagem.update(emblemas)
    return contagem


def situacao_do_traco(traco, quantidade):
    nivel_ativo, estilo, proximo = None, 0, None
    for nivel, estilo_do_nivel in zip(traco.niveis, traco.estilos):
        if quantidade >= nivel:
            nivel_ativo, estilo = nivel, estilo_do_nivel
        elif proximo is None:
            proximo = nivel
    return TracoNoTime(traco, quantidade, nivel_ativo, estilo, proximo)


def tracos_do_time(campeoes, catalogo, emblemas=()):
    """Lista os traços do time: ativos primeiro (do mais forte pro mais fraco), depois os inativos."""
    resultado = [
        situacao_do_traco(catalogo.tracos[id_traco], quantidade)
        for id_traco, quantidade in contar(campeoes, emblemas).items()
        if id_traco in catalogo.tracos
    ]
    resultado.sort(key=lambda t: (t.ativo, t.estilo, t.quantidade), reverse=True)
    return resultado
