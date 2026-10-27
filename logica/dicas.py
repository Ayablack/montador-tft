"""Dicas para o momento da partida: juros, quando subir de nível e quando rolar.

Usa o que a leitura da tela traz (estágio, nível, XP e ouro) e o plano da comp alvo
(reroll, jogar no 8 ou subir para o 9 — veja logica/taticas.py).

As curvas de nível são as que os guias de alto elo recomendam (Set 18): elas dizem
em que rodada o normal é já estar em cada nível. Ficam aqui em cima para ajustar.
"""

from dataclasses import dataclass
from math import ceil

from dados import economia

# (estágio, rodada, nível): a partir dessa rodada, o normal é estar nesse nível
CURVA_JOGAR_NO_8 = [(2, 1, 4), (2, 5, 5), (3, 2, 6), (4, 1, 7), (4, 2, 8)]
CURVA_SUBIR_PARA_O_9 = CURVA_JOGAR_NO_8 + [(5, 1, 9)]
RODADA_DO_REROLL = {
    5: (3, 1),
    6: (3, 2),
    7: (4, 1),
}  # nível do reroll -> quando começar a rolar
OURO_DO_ROLLDOWN = 10  # num rolldown, role até sobrar mais ou menos isso
QUASE_JUROS = 3  # faltando até 3 de ouro para a próxima dezena, vale segurar


@dataclass
class Dica:
    texto: str
    tipo: str  # "nivel", "rolar", "juros"; usado só para o ícone
    urgente: bool = False

    @property
    def icone(self):
        return {"nivel": "⬆️", "rolar": "🎲", "juros": "💰"}.get(self.tipo, "💡")


def curva_do_plano(plano):
    """Lista (estágio, rodada, nível) do plano. Reroll: sobe até o nível do reroll e para lá."""
    if plano is None or plano.estilo == "Jogar no 8":
        return CURVA_JOGAR_NO_8
    if plano.estilo == "Subir para o 9":
        return CURVA_SUBIR_PARA_O_9
    estagio, rodada = RODADA_DO_REROLL.get(plano.nivel_alvo, (3, 2))
    curva = [(e, r, n) for e, r, n in CURVA_JOGAR_NO_8 if n < plano.nivel_alvo]
    return curva + [(estagio, rodada, plano.nivel_alvo)]


def nivel_esperado(estagio, curva):
    """O nível do último ponto da curva que já passou. None no estágio 1."""
    esperado = None
    for e, r, nivel in curva:
        if (e, r) <= estagio:
            esperado = nivel
    return esperado


def xp_ate(nivel_atual, xp_atual, nivel_desejado, xp_para_subir):
    """XP que falta para ir do nível atual (com xp_atual) até o nível desejado."""
    falta = 0
    for nivel in range(nivel_atual, nivel_desejado):
        falta += xp_para_subir.get(nivel, 0)
    return max(falta - xp_atual, 0)


def dicas(leitura, plano, catalogo, faltando=(), tres_estrelas_feitos=False):
    """Lista de dicas, da mais importante para a menos.

    leitura: LeituraDaTela (precisa de estágio, nível e ouro; o que faltar é ignorado)
    plano: Plano da comp alvo ou None
    faltando: campeões da comp alvo que você ainda não tem
    tres_estrelas_feitos: no reroll, se os alvos já estão 3★ (aí é hora de subir de nível)
    """
    resultado = []
    estagio, nivel, ouro = leitura.estagio, leitura.nivel, leitura.ouro
    if not estagio or not nivel or ouro is None:
        return resultado
    if estagio[0] == 1:
        return [
            Dica(
                "Estágio 1: compre campeões que formem pares e guarde o resto. Não compre XP.",
                "juros",
            )
        ]

    reroll = plano is not None and plano.estilo == "Reroll"
    curva = (
        CURVA_SUBIR_PARA_O_9
        if reroll and tres_estrelas_feitos
        else curva_do_plano(plano)
    )
    esperado = nivel_esperado(estagio, curva)
    rodada = f"{estagio[0]}-{estagio[1]}"

    # ---- nível
    if esperado and nivel < esperado:
        xp_atual = leitura.xp[0] if leitura.xp else 0
        falta_xp = xp_ate(nivel, xp_atual, esperado, catalogo.xp_para_subir)
        custo = ceil(falta_xp / economia.XP_POR_COMPRA) * economia.CUSTO_DO_XP
        resultado.append(
            Dica(
                f"{rodada}: o normal é estar no nível {esperado}. Compre XP: faltam {falta_xp} de XP ({custo} de ouro).",
                "nivel",
                urgente=custo <= ouro,
            )
        )

    # ---- rolar
    nomes = ", ".join(c.nome for c in list(faltando)[:3])
    if reroll and nivel >= plano.nivel_alvo and not tres_estrelas_feitos:
        alvos = " e ".join(c.nome for c in plano.tres_estrelas) or "os campeões baratos"
        if ouro > 50:
            resultado.append(
                Dica(
                    f"Reroll: role {ouro - 50} de ouro (só o que passa de 50) atrás de {alvos} 3★.",
                    "rolar",
                    urgente=True,
                )
            )
        else:
            resultado.append(
                Dica(
                    f"Reroll: junte até 50 e role só o que passar, atrás de {alvos} 3★.",
                    "rolar",
                )
            )
    elif not reroll and nivel >= 8 and estagio >= (4, 2) and faltando:
        if ouro > OURO_DO_ROLLDOWN + economia.CUSTO_DO_ROLL:
            resultado.append(
                Dica(
                    f"Hora do rolldown no 8: role até sobrar uns {OURO_DO_ROLLDOWN} de ouro procurando {nomes}.",
                    "rolar",
                    urgente=True,
                )
            )
    elif not reroll and nivel == 7 and estagio >= (4, 1) and faltando:
        resultado.append(
            Dica(
                f"No 7: se estiver perdendo muita vida, role até ~20 de ouro para estabilizar ({nomes}); "
                "se não, guarde para rolar no 8.",
                "rolar",
            )
        )

    # ---- juros
    juros = economia.juros(ouro)
    if ouro >= 50:
        resultado.append(
            Dica(
                f"Você tem {ouro - 50} acima de 50: dá para gastar isso sem perder juros.",
                "juros",
            )
        )
    else:
        proxima = (ouro // economia.JUROS_A_CADA + 1) * economia.JUROS_A_CADA
        if proxima - ouro <= QUASE_JUROS:
            resultado.append(
                Dica(
                    f"Faltam {proxima - ouro} para {proxima}: segure e ganhe +{juros + 1} de juros.",
                    "juros",
                )
            )
    resultado.sort(key=lambda d: not d.urgente)
    return resultado
