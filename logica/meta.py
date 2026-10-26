"""Comps meta: agrupa as partidas de alto elo salvas no banco e calcula o desempenho.

Cada tabuleiro é identificado pelo "carry" (o campeão com mais itens) mais os 2
traços principais. Tabuleiros com a mesma identidade viram uma comp, com
colocação média, % de top 4, % de vitória e os campeões mais frequentes.
"""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass

from dados import banco
from logica.montador import avaliar
from logica.tradutor import Tradutor

FILA_RANQUEADA = 1100
MINIMO_DE_JOGOS = 5          # comps com menos jogos que isso ficam de fora
JOGOS_DE_CONFIANCA = 10      # média ajustada: comps com poucos jogos são puxadas para 4,5
COLOCACAO_NEUTRA = 4.5
FREQUENCIA_MINIMA = 0.4      # campeão entra na comp se aparece em 40% dos tabuleiros dela
MAXIMO_DE_CAMPEOES = 9


@dataclass
class Tabuleiro:
    colocacao: int
    campeoes: list
    carry: object
    itens_do_carry: list
    tracos_principais: tuple


def _ler_tabuleiros(catalogo, tradutor):
    conexao = banco.conectar()
    linhas = conexao.execute(
        """SELECT p.colocacao, p.unidades, p.tracos FROM participacoes p
           JOIN partidas m ON m.match_id = p.match_id
           WHERE m.fila = ? AND m.set_numero = ?""",
        (FILA_RANQUEADA, int(float(catalogo.numero_set))),
    ).fetchall()
    conexao.close()

    tabuleiros = []
    for linha in linhas:
        unidades = json.loads(linha["unidades"])
        campeoes = []
        carry, itens_do_carry, mais_itens = None, [], -1
        for unidade in unidades:
            campeao = tradutor.campeao(unidade["id"])
            if not campeao:
                continue
            campeoes.append(campeao)
            if len(unidade["itens"]) > mais_itens:
                carry, mais_itens = campeao, len(unidade["itens"])
                itens_do_carry = [i for i in (tradutor.item(nome) for nome in unidade["itens"]) if i]

        ativos = []
        for traco_riot in json.loads(linha["tracos"]):
            traco = tradutor.traco(traco_riot["id"])
            if traco and not traco.unico and (traco_riot["tier"] or 0) > 0:
                ativos.append((traco_riot["estilo"] or 0, traco_riot["unidades"] or 0, traco.id))
        principais = tuple(sorted(id_traco for _, _, id_traco in sorted(ativos, reverse=True)[:2]))

        if carry:
            tabuleiros.append(Tabuleiro(linha["colocacao"], campeoes, carry, itens_do_carry, principais))
    return tabuleiros


def comps_meta(situacao, catalogo):
    """Devolve (comps avaliadas contra o que você tem, resumo dos dados)."""
    tradutor = Tradutor(catalogo)
    tabuleiros = _ler_tabuleiros(catalogo, tradutor)

    grupos = defaultdict(list)
    for tabuleiro in tabuleiros:
        grupos[(tabuleiro.carry.id, tabuleiro.tracos_principais)].append(tabuleiro)

    comps = []
    for (id_carry, ids_tracos), do_grupo in grupos.items():
        jogos = len(do_grupo)
        if jogos < MINIMO_DE_JOGOS:
            continue
        frequencia = Counter(c.id for t in do_grupo for c in {x.id: x for x in t.campeoes}.values())
        frequentes = [id_c for id_c, n in frequencia.most_common(MAXIMO_DE_CAMPEOES) if n / jogos >= FREQUENCIA_MINIMA]
        itens = Counter(i.nome for t in do_grupo for i in t.itens_do_carry)

        carry = catalogo.campeoes[id_carry]
        nomes_tracos = " + ".join(catalogo.tracos[i].nome for i in ids_tracos)
        comp = avaliar(
            [catalogo.campeoes[i] for i in frequentes], situacao, catalogo,
            nome=f"{carry.nome} — {nomes_tracos}" if nomes_tracos else carry.nome, origem="Meta",
        )
        colocacoes = [t.colocacao for t in do_grupo]
        comp.estatisticas = {
            "jogos": jogos,
            "colocacao_media": round(sum(colocacoes) / jogos, 2),
            "media_ajustada": round(
                (sum(colocacoes) + COLOCACAO_NEUTRA * JOGOS_DE_CONFIANCA) / (jogos + JOGOS_DE_CONFIANCA), 2
            ),
            "top4": sum(1 for c in colocacoes if c <= 4) / jogos,
            "vitoria": sum(1 for c in colocacoes if c == 1) / jogos,
            "carry": carry.nome,
            "itens_do_carry": [nome for nome, _ in itens.most_common(3)],
        }
        comps.append(comp)

    comps.sort(key=lambda comp: comp.estatisticas["media_ajustada"])
    resumo = {
        "tabuleiros": len(tabuleiros),
        "partidas": len(tabuleiros) // 8,
        "nao_encontrados": dict(tradutor.nao_encontrados.most_common(10)),
    }
    return comps, resumo
