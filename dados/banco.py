"""Banco SQLite com os dados de jogo (do datatft) e as partidas de alto elo (da Riot).

Cada tabela de dados de jogo tem as colunas "set" e "idioma", então dá para guardar
vários sets lado a lado. Exemplos de consulta estão no README.
"""

import json
import re
import sqlite3
from pathlib import Path

CAMINHO_DB = Path(__file__).parent / "datatft.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS metadados (
    set_numero TEXT, idioma TEXT, atualizado_em INTEGER,
    PRIMARY KEY (set_numero, idioma)
);
CREATE TABLE IF NOT EXISTS campeoes (
    set_numero TEXT, idioma TEXT, id INTEGER, chave TEXT, nome TEXT, custo INTEGER,
    tracos TEXT, papel TEXT, vida TEXT, vida_1 REAL, ataque TEXT, ataque_1 REAL,
    armadura REAL, resist_magica REAL, vel_ataque REAL, alcance INTEGER, critico REAL,
    mana_max INTEGER, mana_inicial INTEGER,
    habilidade TEXT, habilidade_desc TEXT, itens_recomendados TEXT,
    PRIMARY KEY (set_numero, idioma, id)
);
CREATE TABLE IF NOT EXISTS tracos (
    set_numero TEXT, idioma TEXT, id TEXT, chave TEXT, nome TEXT, tipo TEXT, descricao TEXT,
    PRIMARY KEY (set_numero, idioma, id)
);
CREATE TABLE IF NOT EXISTS traco_niveis (
    set_numero TEXT, idioma TEXT, traco_id TEXT, quantidade INTEGER, estilo INTEGER, descricao TEXT
);
CREATE TABLE IF NOT EXISTS campeao_traco (
    set_numero TEXT, idioma TEXT, campeao_id INTEGER, traco_id TEXT
);
CREATE TABLE IF NOT EXISTS itens (
    set_numero TEXT, idioma TEXT, id INTEGER, chave TEXT, nome TEXT, tipo TEXT, efeito TEXT,
    componente_1 INTEGER, componente_2 INTEGER, traco_id TEXT,
    PRIMARY KEY (set_numero, idioma, id)
);
CREATE TABLE IF NOT EXISTS augments (
    set_numero TEXT, idioma TEXT, chave TEXT, nome TEXT, tier TEXT, descricao TEXT,
    rodadas TEXT, tipos TEXT
);
CREATE TABLE IF NOT EXISTS charms (
    set_numero TEXT, idioma TEXT, chave TEXT, nome TEXT, categoria TEXT, tier INTEGER,
    custo INTEGER, efeito TEXT, efeito_melhorado TEXT, rodadas TEXT, requisitos TEXT
);
CREATE TABLE IF NOT EXISTS economia_loja (
    set_numero TEXT, idioma TEXT, nivel INTEGER, custo INTEGER, chance REAL
);
CREATE TABLE IF NOT EXISTS economia_xp (
    set_numero TEXT, idioma TEXT, nivel INTEGER, xp_para_subir INTEGER
);
CREATE TABLE IF NOT EXISTS pool (
    set_numero TEXT, idioma TEXT, custo INTEGER, copias INTEGER
);

-- Partidas ranqueadas de alto elo, vindas da API oficial da Riot
CREATE TABLE IF NOT EXISTS partidas (
    match_id TEXT PRIMARY KEY, data INTEGER, versao TEXT, set_numero INTEGER, fila INTEGER
);
CREATE TABLE IF NOT EXISTS participacoes (
    match_id TEXT, puuid TEXT, colocacao INTEGER, nivel INTEGER,
    unidades TEXT, tracos TEXT, augments TEXT,
    PRIMARY KEY (match_id, puuid)
);
"""

TABELAS_DE_JOGO = [
    "metadados", "campeoes", "tracos", "traco_niveis", "campeao_traco", "itens",
    "augments", "charms", "economia_loja", "economia_xp", "pool",
]

TIPOS_ITEM = {
    "part": "Componente",
    "common": "Completo",
    "guangming": "Radiante",
    "aoen": "Artefato",
    "zhuanzhi": "Emblema",
    "zhuanzhi2": "Emblema",
    "zhuanzhiJgg": "Emblema",
    "daoju": "Especial",
    "other": "Consumível",
    "remove": "Utilitário",
}

TIERS_AUGMENT = ["Prata", "Ouro", "Prismático"]  # ordem dos 3 grupos em "hexs"


def conectar(caminho=None):
    conexao = sqlite3.connect(caminho or CAMINHO_DB)
    conexao.row_factory = sqlite3.Row
    conexao.executescript(ESQUEMA)
    return conexao


# ---------------------------------------------------------------- conversões

def _sem_html(texto):
    texto = re.sub(r"<br\s*/?>|<div class='skill-divider'></div>", "\n", texto or "")
    return re.sub(r"<[^>]+>", "", texto).strip()


def _primeiro_valor(texto):
    """'550/990/1782' -> 550.0 (valor de 1 estrela)."""
    try:
        return float(str(texto).split("/")[0])
    except ValueError:
        return None


def _numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _porcentagem(texto):
    """'75%' -> 0.75 ; '-' -> 0.0"""
    texto = str(texto).strip().rstrip("%")
    return float(texto) / 100 if texto not in ("", "-") else 0.0


def _id_traco_do_emblema(trait_id):
    """O site usa 'race_1' / 'job_7'; aqui os traços são 'origem_1' / 'classe_7'."""
    if not trait_id:
        return None
    tipo, numero = trait_id.split("_")
    return f"{'origem' if tipo == 'race' else 'classe'}_{numero}"


def _separar_ids(texto):
    return [int(parte) for parte in str(texto or "").split(",") if parte.strip().isdigit()]


# ---------------------------------------------------------------- importação

def importar_set(conexao, dados, idioma, numero_set):
    """Apaga o que havia desse set/idioma e grava tudo de novo."""
    s, i = numero_set, idioma

    def campo(nome):  # as chaves do JSON vêm com o número do set: "heros18", "races16.5"...
        return dados.get(f"{nome}{s}") or []

    for tabela in TABELAS_DE_JOGO:
        conexao.execute(f"DELETE FROM {tabela} WHERE set_numero=? AND idioma=?", (s, i))

    conexao.execute("INSERT INTO metadados VALUES (?,?,?)", (s, i, dados.get("databaseUpdateTime")))

    # traços: "races" são as origens e "jobs" são as classes
    ids_por_nome = {}
    for tipo, chave_lista, chave_id in [("origem", "races", "raceId"), ("classe", "jobs", "jobId")]:
        for traco in campo(chave_lista):
            id_traco = f"{tipo}_{traco[chave_id]}"
            ids_por_nome[traco["name"]] = id_traco
            conexao.execute(
                "INSERT INTO tracos VALUES (?,?,?,?,?,?,?)",
                (s, i, id_traco, traco.get("key"), traco["name"], tipo, _sem_html(traco.get("introduce"))),
            )
            for nivel in traco.get("level") or []:
                conexao.execute(
                    "INSERT INTO traco_niveis VALUES (?,?,?,?,?,?)",
                    (s, i, id_traco, nivel["level"], nivel.get("levelStyle"), _sem_html(nivel.get("levelDesc"))),
                )

    for heroi in campo("heros"):
        vida = heroi.get("lifeData2") or heroi.get("lifeData")
        ataque = heroi.get("attackData2") or heroi.get("attackData")
        conexao.execute(
            "INSERT INTO campeoes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                s, i, heroi["chessId"], heroi.get("key"), heroi["displayName"], heroi.get("price"),
                ", ".join((heroi.get("races") or []) + (heroi.get("jobs") or [])),
                heroi.get("role"), vida, _primeiro_valor(vida), ataque, _primeiro_valor(ataque),
                _numero(heroi.get("armor")), _numero(heroi.get("spellBlock")),
                _numero(heroi.get("attackSpeed")), heroi.get("attackRange"), _numero(heroi.get("crit")),
                heroi.get("magic"), heroi.get("startMagic"),
                heroi.get("skillName"), _sem_html(heroi.get("skillDetail2")), heroi.get("recEquip"),
            ),
        )
        for nome_traco in (heroi.get("races") or []) + (heroi.get("jobs") or []):
            if nome_traco in ids_por_nome:
                conexao.execute(
                    "INSERT INTO campeao_traco VALUES (?,?,?,?)",
                    (s, i, heroi["chessId"], ids_por_nome[nome_traco]),
                )

    vistos = set()
    for item in campo("equips"):
        if item["equipId"] in vistos:  # o site às vezes repete o mesmo item
            continue
        vistos.add(item["equipId"])
        componentes = _separar_ids(item.get("formula")) + [None, None]
        conexao.execute(
            "INSERT INTO itens VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                s, i, item["equipId"], item.get("key"), item["name"],
                TIPOS_ITEM.get(item.get("type2"), item.get("type2")), _sem_html(item.get("effect")),
                componentes[0], componentes[1], _id_traco_do_emblema(item.get("traitId")),
            ),
        )

    for posicao, grupo in enumerate(campo("hexs")):
        tier = TIERS_AUGMENT[posicao] if posicao < len(TIERS_AUGMENT) else str(posicao)
        for augment in grupo:
            conexao.execute(
                "INSERT INTO augments VALUES (?,?,?,?,?,?,?,?)",
                (
                    s, i, augment.get("hexId"), augment.get("name"), tier, _sem_html(augment.get("desc")),
                    ", ".join(augment.get("round") or []), json.dumps(augment.get("type") or []),
                ),
            )

    for charm in campo("charms"):
        conexao.execute(
            "INSERT INTO charms VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                s, i, charm.get("key"), charm.get("title"), charm.get("category"), charm.get("tier"),
                charm.get("cost"), _sem_html(charm.get("effect")),
                _sem_html((charm.get("upgrade") or {}).get("effect")),
                ", ".join(charm.get("rounds") or []), ", ".join(charm.get("requires") or []),
            ),
        )

    # chances da loja: lista de 45 = 9 níveis x 5 custos
    for posicao, chance in enumerate(campo("rates")):
        nivel, custo = posicao // 5 + 1, posicao % 5 + 1
        conexao.execute("INSERT INTO economia_loja VALUES (?,?,?,?,?)", (s, i, nivel, custo, _porcentagem(chance)))

    # exps[0] é o XP para ir do nível 2 para o 3, e assim por diante
    for posicao, xp in enumerate(campo("exps")):
        conexao.execute("INSERT INTO economia_xp VALUES (?,?,?,?)", (s, i, posicao + 2, xp))

    for posicao, copias in enumerate(campo("quantitys")):
        conexao.execute("INSERT INTO pool VALUES (?,?,?,?)", (s, i, posicao + 1, copias))

    conexao.commit()
