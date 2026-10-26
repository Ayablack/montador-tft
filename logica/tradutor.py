"""Liga nomes de fora aos campeões, traços e itens do catálogo.

Serve para dois casos:
  - nomes internos da Riot nas partidas (ex.: 'DA_18_Varus', 'DA_Component_RecurveBow');
  - textos lidos da tela pelo OCR, em português (ex.: 'Gume do Infinito', 'Krugue'),
    que podem vir com pequenos erros de leitura.
"""

import re
from collections import Counter
from difflib import get_close_matches

# Itens que a Riot renomeou no jogo mas manteve o nome interno antigo (sets antigos usavam TFT_Item_...)
ITENS_RENOMEADOS = {
    "guardianangel": "Edge of Night",
    "madredsbloodrazor": "Giant Slayer",
    "runaanshurricane": "Kraken's Fury",
    "frozenheart": "Protector's Vow",
    "leviathan": "Nashor's Tooth",
    "unstableconcoction": "Hand Of Justice",
    "nightharvester": "Steadfast Heart",
    "powergauntlet": "Striker's Flail",
    "seraphsembrace": "Blue Buff",
    "redemption": "Spirit Visage",
    "spectralgauntlet": "Evenshroud",
    "statikkshiv": "Void Staff",
    "rapidfirecannon": "Red Buff",
    "forceofnature": "Tacticians Crown",
}
SUFIXOS_IGNORADOS = {"ap", "ad", "base"}  # variações do mesmo campeão (ex.: DA_Nidalee18_AP)
SEMELHANCA_MINIMA = 0.75                  # para textos do OCR com erro de leitura


def normalizar(texto):
    """'Kog'Maw' -> 'kogmaw' ; 'Gume do Infinito' -> 'gumedoinfinito'."""
    return "".join(letra for letra in (texto or "").lower() if letra.isalnum())


def _sem_prefixo(id_riot):
    """'TFT18_Leblanc' -> 'Leblanc' ; 'TFT_Item_InfinityEdge' -> 'InfinityEdge'."""
    partes = [p for p in (id_riot or "").split("_") if not p.upper().startswith("TFT") and p != "Item"]
    return "".join(partes)


def _nome_da_chave(chave):
    """'DA_Nidalee18_AP' -> 'nidalee' ; 'DA_18_Slayer' -> 'slayer'."""
    partes = []
    for parte in (chave or "").split("_"):
        parte = re.sub(r"\d+$", "", parte)  # tira o número do set do fim ("Krug18")
        if parte and parte != "DA" and parte.lower() not in SUFIXOS_IGNORADOS:
            partes.append(parte)
    return normalizar("".join(partes))


class _Tabela:
    """Índice de um tipo de objeto (campeões, traços ou itens)."""

    def __init__(self, objetos, nomes_locais):
        self.por_chave = {o.chave: o for o in objetos if o.chave}
        self.por_nome = {}
        for objeto in objetos:
            self.por_nome[normalizar(objeto.nome)] = objeto
            if objeto.nome_en:
                self.por_nome.setdefault(normalizar(objeto.nome_en), objeto)
            if objeto.chave:
                self.por_nome.setdefault(_nome_da_chave(objeto.chave), objeto)
                if objeto.chave in nomes_locais:  # nome em português (Community Dragon)
                    self.por_nome.setdefault(normalizar(nomes_locais[objeto.chave]), objeto)

    def buscar_id(self, id_riot):
        return self.por_chave.get(id_riot) or self.por_nome.get(normalizar(_sem_prefixo(id_riot)))

    def buscar_texto(self, texto):
        chave = normalizar(texto)
        if not chave:
            return None
        if chave in self.por_nome:
            return self.por_nome[chave]
        parecidos = get_close_matches(chave, self.por_nome, n=1, cutoff=SEMELHANCA_MINIMA)
        return self.por_nome[parecidos[0]] if parecidos else None


class Tradutor:
    def __init__(self, catalogo):
        nomes_locais = getattr(catalogo, "nomes_locais", {}) or {}
        self.campeoes = _Tabela(catalogo.campeoes.values(), nomes_locais)
        self.tracos = _Tabela(catalogo.tracos.values(), nomes_locais)
        self.itens = _Tabela(catalogo.itens.values(), nomes_locais)
        for nome_interno, nome in ITENS_RENOMEADOS.items():
            if normalizar(nome) in self.itens.por_nome:
                self.itens.por_nome.setdefault(nome_interno, self.itens.por_nome[normalizar(nome)])
        self.nao_encontrados = Counter()

    def _anotar(self, achado, id_riot):
        if not achado:
            self.nao_encontrados[id_riot] += 1
        return achado

    # nomes internos (partidas da Riot)
    def campeao(self, id_riot):
        return self._anotar(self.campeoes.buscar_id(id_riot), id_riot)

    def traco(self, id_riot):
        return self._anotar(self.tracos.buscar_id(id_riot), id_riot)

    def item(self, id_riot):
        return self._anotar(self.itens.buscar_id(id_riot), id_riot)

    # textos da tela (OCR)
    def campeao_do_texto(self, texto):
        return self.campeoes.buscar_texto(texto)

    def traco_do_texto(self, texto):
        return self.tracos.buscar_texto(texto)
