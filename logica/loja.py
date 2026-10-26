"""Chance de achar um campeão na loja, a partir das chances por nível e do tamanho do pool."""

from dataclasses import dataclass

SLOTS_NA_LOJA = 5
CUSTO_DO_ROLL = 2


def copias_por_estrela(estrelas):
    """1★ = 1 cópia, 2★ = 3 cópias, 3★ = 9 cópias."""
    return 3 ** (max(estrelas, 1) - 1)


@dataclass
class ChanceNaLoja:
    chance_por_loja: float  # chance de aparecer pelo menos 1 cópia numa loja
    rolls_esperados: float  # média de rolls até ver uma cópia
    copias_restantes: int

    @property
    def ouro_esperado(self):
        return self.rolls_esperados * CUSTO_DO_ROLL


def chance_na_loja(campeao, nivel, catalogo, copias_suas=0, copias_de_outros=0):
    chance_do_custo = catalogo.chances_no_nivel(nivel).get(campeao.custo, 0.0)
    copias_no_pool = catalogo.copias_por_custo.get(campeao.custo, 0)
    campeoes_do_mesmo_custo = sum(1 for c in catalogo.campeoes.values() if c.custo == campeao.custo)

    restantes = max(copias_no_pool - copias_suas - copias_de_outros, 0)
    total_do_custo = copias_no_pool * campeoes_do_mesmo_custo - copias_suas - copias_de_outros
    if not chance_do_custo or not restantes or total_do_custo <= 0:
        return ChanceNaLoja(0.0, float("inf"), restantes)

    chance_por_slot = chance_do_custo * restantes / total_do_custo
    chance_por_loja = 1 - (1 - chance_por_slot) ** SLOTS_NA_LOJA
    return ChanceNaLoja(chance_por_loja, 1 / chance_por_loja, restantes)
