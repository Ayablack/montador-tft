"""Itens: o que dá para montar com os componentes que você tem e em quem colocar."""

from collections import Counter
from dataclasses import dataclass

TIPOS_DE_ITEM_UTEIS = {"Completo", "Emblema"}


@dataclass
class ItemParaCampeao:
    item: object
    status: str  # "Pode montar", "Falta 1 componente" ou "Faltam 2 componentes"
    faltando: list  # componentes que faltam


def tem_componentes(componentes, receita):
    """componentes: Counter {id_componente: quantidade}. Considera receitas com 2 iguais."""
    return all(componentes[c] >= n for c, n in Counter(receita).items())


def itens_que_pode_montar(componentes, catalogo):
    """Todos os itens que dá para montar agora (cada um isoladamente)."""
    possiveis = [
        item
        for item in catalogo.receitas()
        if item.tipo in TIPOS_DE_ITEM_UTEIS
        and tem_componentes(componentes, item.componentes)
    ]
    return sorted(possiveis, key=lambda item: (item.tipo, item.nome))


def _usar_componentes(sobra, receita):
    """Gasta da `sobra` os componentes da receita que tiver e devolve os que faltaram."""
    faltando = []
    for componente in receita:
        if sobra[componente] > 0:
            sobra[componente] -= 1
        else:
            faltando.append(componente)
    return faltando


def itens_para_campeao(campeao, componentes, catalogo):
    """Itens recomendados do campeão, com o que falta para cada um.

    Os itens são vistos em ordem e cada um gasta os componentes que usa; assim,
    num item repetido (ex.: 2 Gargoyle), o segundo só conta o que sobrou do primeiro.
    """
    sobra = Counter(componentes)
    resultado = []
    for id_item in campeao.itens_recomendados:
        item = catalogo.itens.get(id_item)
        if not item or len(item.componentes) != 2:
            continue
        faltando = [
            catalogo.itens[c]
            for c in _usar_componentes(sobra, item.componentes)
            if c in catalogo.itens
        ]
        status = {0: "Pode montar", 1: "Falta 1 componente"}.get(
            len(faltando), "Faltam 2 componentes"
        )
        resultado.append(ItemParaCampeao(item, status, faltando))
    return resultado


def carregadores(comp, quantidade=2):
    """Os campeões que mais merecem itens no time.

    Quem mais segura 3 itens nas partidas de alto elo (taxa_de_itens); sem dados, os mais caros.
    """
    return sorted(comp.campeoes, key=lambda c: (-c.taxa_de_itens, -c.custo, c.nome))[
        :quantidade
    ]
