"""Dados do set atual a partir do Community Dragon (communitydragon.org).

O Community Dragon extrai os arquivos do próprio cliente do TFT da Riot, em português.
Daqui saem campeões (com atributos e habilidade), traços (com os breakpoints), itens
(com as receitas), augments e os ícones usados na tela e na leitura do jogo.

A API da Riot não tem esses dados: ela só tem partidas, ranking e jogadores.
"""

import re
from pathlib import Path

import requests

from dados import banco

URL_DADOS = "https://raw.communitydragon.org/latest/cdragon/tft/pt_br.json"
URL_ARQUIVOS = "https://raw.communitydragon.org/latest/game/"
PASTA_ICONES = Path(__file__).resolve().parent.parent / "static" / "icones"  # servida pelo Streamlit
TIMEOUT = 60
SET_ATUAL = "18"

# Estilos do Community Dragon -> estilos do app (1 bronze, 2 prata, 3 ouro, 4 prismático).
# O 4 do Community Dragon é o dos traços únicos (de um campeão só): mostramos como ouro.
ESTILOS = {1: 1, 2: 1, 3: 2, 4: 3, 5: 3, 6: 4}


# ---------------------------------------------------------------- textos

def _url_do_icone(caminho):
    """'ASSETS/.../tft_item_bfsword.tex' -> URL do .png no Community Dragon."""
    return URL_ARQUIVOS + caminho.lower().replace(".tex", ".png").replace(".dds", ".png")


def _numero_curto(valor):
    if valor is None:
        return "?"
    if abs(valor - round(valor)) < 0.05 or abs(valor) >= 100:
        return f"{valor:.0f}"
    return f"{valor:.2f}".rstrip("0")


def _hash(nome):
    """Hash FNV-1a que o cliente usa no lugar de muitos nomes: 'BonusDamagePercentBase' -> '{a9a813e7}'."""
    valor = 0x811C9DC5
    for byte in nome.lower().encode():
        valor = ((valor ^ byte) * 0x01000193) & 0xFFFFFFFF
    return f"{{{valor:08x}}}"


def _resolver(texto, variaveis):
    """Troca @Nome@ e @Nome*100@ pelo valor da variável. Valores por estrela viram '100/150/225'."""
    def trocar(achado):
        nome = achado.group(1)
        valor = variaveis.get(nome, variaveis.get(_hash(nome)))
        if valor is None:
            return "?"
        fator = 100 if achado.group(2) else 1
        valores = valor if isinstance(valor, list) else [valor]
        return "/".join(_numero_curto(v * fator if v is not None else None) for v in valores)
    return re.sub(r"@([A-Za-z0-9_.]+)(\*100)?@", trocar, texto or "")


def _limpar(texto):
    """Tira as marcações do cliente (<b>, %i:scaleAP%, {{...}}) e deixa texto simples."""
    texto = re.sub(r"<br\s*/?>|</?row>", "\n", texto or "")
    texto = re.sub(r"<[^>]+>|%i:[^%]+%|\{\{[^}]*\}\}", "", texto)
    texto = texto.replace("\r", "").replace("\\n", "\n")
    return re.sub(r"\n{2,}", "\n", texto).strip()


def _nucleo(chave):
    """'DA_18_EmblemJuggernaut' -> 'juggernaut' ; 'DA_Juggernaut18' -> 'juggernaut'."""
    return re.sub(r"^da_|_?18_?|emblem|_", "", chave.lower())


# ---------------------------------------------------------------- campeões, traços, itens

def e_campeao_da_loja(campeao):
    """Fora: monstros sem traço, bigornas, formas alternativas ('Lux (Solar)') e custo > 5."""
    return bool(
        campeao["apiName"].startswith("DA_") and campeao.get("traits")
        and 1 <= campeao.get("cost", 0) <= 5 and "(" not in campeao["name"]
    )


def tipo_do_item(item):
    """Componente, Completo, Emblema, Radiante, Artefato, Especial ou None (fora do app)."""
    chave = item["apiName"]
    if not chave.startswith("DA_") or item.get("isAugment") or not item.get("name"):
        return None
    if "component" in item.get("tags", []):
        return "Componente"
    if "Emblem" in chave:
        return "Emblema"
    if "Radiant" in chave:
        return "Radiante"
    if "Artifact" in chave:
        return "Artefato"
    if "Tacticians" in chave:
        return "Especial"
    if len(item.get("composition") or []) == 2:
        return "Completo"
    return None


def importar(conexao, numero_set=SET_ATUAL, progresso=print):
    progresso("Baixando os dados do set no Community Dragon...")
    dados = requests.get(URL_DADOS, timeout=TIMEOUT).json()
    do_set = next(s for s in dados["setData"] if s.get("mutator") == f"TFTSet{numero_set}")

    for tabela in banco.TABELAS_DE_JOGO:
        conexao.execute(f"DELETE FROM {tabela}")

    traco_por_nome = {}
    for traco in do_set["traits"]:
        traco_por_nome[traco["name"]] = traco["apiName"]
        # descrição geral: o texto antes das linhas de cada breakpoint, com os valores do primeiro nível
        geral = re.split(r"<row>", traco.get("desc") or "")[0]
        primeiro = (traco.get("effects") or [{}])[0].get("variables") or {}
        conexao.execute("INSERT INTO tracos VALUES (?,?,?,?)",
                        (traco["apiName"], traco["name"], _limpar(_resolver(geral, primeiro)), traco.get("icon")))
        # a descrição tem uma <row> por breakpoint; cada uma é preenchida com as variáveis do seu nível
        linhas = re.findall(r"<row>(.*?)</row>", traco.get("desc") or "", flags=re.S)
        efeitos = sorted(traco.get("effects", []), key=lambda e: e.get("minUnits") or 1)
        for posicao, efeito in enumerate(efeitos):
            texto = linhas[posicao] if len(linhas) == len(efeitos) else ""
            conexao.execute(
                "INSERT INTO traco_niveis VALUES (?,?,?,?,?)",
                (traco["apiName"], efeito.get("minUnits") or 1, efeito.get("maxUnits"), ESTILOS.get(efeito.get("style"), 1),
                 _limpar(_resolver(texto, {**(efeito.get("variables") or {}), "MinUnits": efeito.get("minUnits") or 1}))),
            )

    for campeao in filter(e_campeao_da_loja, do_set["champions"]):
        stats, habilidade = campeao.get("stats") or {}, campeao.get("ability") or {}
        # cada variável da habilidade tem 7 valores; os de 1, 2 e 3 estrelas são as posições 1 a 3
        variaveis = {v["name"]: (v.get("value") or [None] * 4)[1:4] for v in habilidade.get("variables", [])}
        conexao.execute(
            "INSERT INTO campeoes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (campeao["apiName"], campeao["name"], campeao["cost"],
             stats.get("hp"), stats.get("damage"), stats.get("armor"), stats.get("magicResist"),
             stats.get("attackSpeed"), stats.get("range"), stats.get("critChance"),
             stats.get("mana"), stats.get("initialMana"),
             habilidade.get("name"), _limpar(_resolver(habilidade.get("desc"), variaveis)),
             campeao.get("tileIcon") or campeao.get("squareIcon")),
        )
        for nome_traco in campeao["traits"]:
            if nome_traco in traco_por_nome:
                conexao.execute("INSERT INTO campeao_traco VALUES (?,?)",
                                (campeao["apiName"], traco_por_nome[nome_traco]))

    tracos_por_nucleo = {_nucleo(chave): chave for chave in traco_por_nome.values()}
    for item in dados["items"]:
        tipo = tipo_do_item(item)
        if not tipo:
            continue
        receita = (item.get("composition") or []) + [None, None]
        traco = None
        if tipo == "Emblema":  # 'DA_18_EmblemFloraFatalisAugment' -> traço 'DA_FloraFatalis18'
            nucleo = _nucleo(item["apiName"])
            traco = next((chave for parte, chave in tracos_por_nucleo.items() if nucleo.startswith(parte)), None)
        conexao.execute(
            "INSERT OR REPLACE INTO itens VALUES (?,?,?,?,?,?,?,?)",
            (item["apiName"], item["name"], tipo, receita[0], receita[1], traco,
             _limpar(_resolver(item.get("desc"), item.get("effects") or {})), item.get("icon")),
        )

    por_chave = {item["apiName"]: item for item in dados["items"]}
    for chave in do_set.get("augments", []):
        augment = por_chave.get(chave)
        if augment and augment.get("name"):
            conexao.execute(
                "INSERT OR REPLACE INTO augments VALUES (?,?,?,?)",
                (chave, augment["name"], _limpar(_resolver(augment.get("desc"), augment.get("effects") or {})),
                 augment.get("icon")),
            )

    banco.salvar_metadado(conexao, "set", numero_set)
    banco.salvar_metadado(conexao, "fonte", URL_DADOS)
    conexao.commit()
    for tabela in ("campeoes", "tracos", "itens", "augments"):
        progresso(f"{tabela}: {conexao.execute(f'SELECT COUNT(*) FROM {tabela}').fetchone()[0]}")

    baixar_icones(conexao, "campeao", "SELECT chave, icone FROM campeoes", progresso)
    baixar_icones(conexao, "item", "SELECT chave, icone FROM itens", progresso)


def baixar_icones(conexao, tipo, consulta, progresso=print):
    """Salva cada ícone em static/icones/<tipo>/<chave>.png (só os que faltam)."""
    pasta = PASTA_ICONES / tipo
    pasta.mkdir(parents=True, exist_ok=True)
    pendentes = [(chave, icone) for chave, icone in conexao.execute(consulta)
                 if icone and not (pasta / f"{chave}.png").exists()]
    for numero, (chave, icone) in enumerate(pendentes, start=1):
        progresso(f"Baixando ícone de {tipo} {numero}/{len(pendentes)}...")
        resposta = requests.get(_url_do_icone(icone), timeout=TIMEOUT)
        if resposta.ok:
            (pasta / f"{chave}.png").write_bytes(resposta.content)


def caminho_do_icone(tipo, chave):
    """tipo = "item" ou "campeao". None se o ícone não foi baixado."""
    caminho = PASTA_ICONES / tipo / f"{chave}.png"
    return caminho if caminho.exists() else None
