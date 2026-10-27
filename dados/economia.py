"""Regras de economia do TFT (Set 18). Nem a API da Riot nem o Community Dragon trazem esses números.

Fontes (conferidas em 26/10/2026):
- Chances da loja e pool: noxutft.com/tft-shop-odds e tftsense.gg (Set 18, patch 18.3).
  O nível 7 (16/30/43/10/1) foi conferido no próprio jogo: o HUD mostra as chances acima da loja.
- XP para subir: conferido nos prints do jogo ("2/56" no nível 7, "6/20" no nível 5).
- Juros, sequências e renda: notas do patch 14.1 da Riot (sequências a partir de 3) e guias do Set 18.
  Os guias não concordam sobre as sequências; se o jogo mudar, é só ajustar aqui.

Se um patch mudar algum número, este é o único lugar para mexer.
"""

# nível -> {custo: chance de cada carta da loja ser desse custo}
CHANCES_DA_LOJA = {
    1: {1: 1.00},
    2: {1: 1.00},
    3: {1: 0.75, 2: 0.25},
    4: {1: 0.55, 2: 0.30, 3: 0.15},
    5: {1: 0.45, 2: 0.33, 3: 0.20, 4: 0.02},
    6: {1: 0.30, 2: 0.40, 3: 0.25, 4: 0.05},
    7: {1: 0.16, 2: 0.30, 3: 0.43, 4: 0.10, 5: 0.01},
    8: {1: 0.15, 2: 0.20, 3: 0.32, 4: 0.30, 5: 0.03},
    9: {1: 0.10, 2: 0.17, 3: 0.25, 4: 0.33, 5: 0.15},
    10: {1: 0.05, 2: 0.10, 3: 0.20, 4: 0.40, 5: 0.25},
    11: {1: 0.01, 2: 0.02, 3: 0.12, 4: 0.50, 5: 0.35},
}

# custo -> cópias de cada campeão no pool compartilhado pelos 8 jogadores
COPIAS_POR_CUSTO = {1: 30, 2: 25, 3: 18, 4: 10, 5: 9}

# nível atual -> XP que falta para o próximo (o HUD mostra "XP atual / este número")
XP_PARA_SUBIR = {2: 2, 3: 6, 4: 10, 5: 20, 6: 36, 7: 56, 8: 68, 9: 68}

# ---------------------------------------------------------------- ouro e XP por rodada
RENDA_BASE = 5  # a partir da rodada 2-2
OURO_POR_VITORIA = 1  # vitória contra outro jogador
JUROS_A_CADA = 10  # +1 de ouro para cada 10 guardados...
JUROS_MAXIMO = 5  # ...até +5 (com 50 ou mais)
OURO_POR_SEQUENCIA = {
    3: 1,
    4: 1,
    5: 2,
    6: 3,
}  # vitórias ou derrotas seguidas; 6 ou mais = +3
CUSTO_DO_XP = 4  # 4 de ouro compram 4 de XP
XP_POR_COMPRA = 4
XP_POR_RODADA = 2  # XP que vem sozinho a cada rodada
CUSTO_DO_ROLL = 2
CARTAS_NA_LOJA = 5


def juros(ouro):
    return min(max(ouro, 0) // JUROS_A_CADA, JUROS_MAXIMO)


def ouro_da_sequencia(tamanho):
    if tamanho < min(OURO_POR_SEQUENCIA):
        return 0
    return OURO_POR_SEQUENCIA.get(tamanho, max(OURO_POR_SEQUENCIA.values()))
