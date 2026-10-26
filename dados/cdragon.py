"""Nomes em português e ícones dos itens, do Community Dragon (dados extraídos do cliente do jogo).

Serve para a leitura de tela: o jogo mostra os nomes em pt-BR e os itens como ícones.
As chaves internas do Community Dragon são as mesmas do datatft (ex.: 'DA_18_LeBlanc'),
então a ligação entre os dois é exata.
"""

from pathlib import Path

import requests

URL_DADOS = "https://raw.communitydragon.org/latest/cdragon/tft/pt_br.json"
URL_ARQUIVOS = "https://raw.communitydragon.org/latest/game/"
PASTA_ICONES = Path(__file__).parent / "icones"
TIMEOUT = 60
TIPOS_COM_ICONE = ("Componente", "Completo", "Emblema", "Radiante", "Artefato")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS nomes_locais (
    set_numero TEXT, idioma TEXT, chave TEXT, tipo TEXT, nome TEXT, icone TEXT,
    PRIMARY KEY (set_numero, idioma, chave)
);
"""


def _url_do_icone(caminho):
    """'assets/.../tft_item_bfsword.tex' -> URL do .png no Community Dragon."""
    return URL_ARQUIVOS + caminho.lower().replace(".tex", ".png")


def importar(conexao, numero_set="18", progresso=print):
    progresso("Baixando nomes em português do Community Dragon...")
    dados = requests.get(URL_DADOS, timeout=TIMEOUT).json()
    do_set = next(s for s in dados["setData"] if s.get("mutator") == f"TFTSet{numero_set}")
    itens = {item["apiName"]: item for item in dados["items"]}

    conexao.executescript(ESQUEMA)
    conexao.execute("DELETE FROM nomes_locais WHERE set_numero=? AND idioma='pt_br'", (numero_set,))
    linhas = []
    for campeao in do_set["champions"]:
        linhas.append((campeao["apiName"], "campeao", campeao["name"], campeao.get("tileIcon")))
    for traco in do_set["traits"]:
        linhas.append((traco["apiName"], "traco", traco["name"], traco.get("icon")))
    chaves_de_itens = [linha[0] for linha in conexao.execute(
        "SELECT chave FROM itens WHERE set_numero=? AND idioma='en' AND tipo IN (%s)" % ",".join("?" * len(TIPOS_COM_ICONE)),
        (numero_set, *TIPOS_COM_ICONE),
    )]
    for chave in chaves_de_itens:
        if chave in itens:
            linhas.append((chave, "item", itens[chave]["name"], itens[chave].get("icon")))
    conexao.executemany(
        "INSERT OR REPLACE INTO nomes_locais VALUES (?, 'pt_br', ?, ?, ?, ?)",
        [(numero_set, *linha) for linha in linhas],
    )
    conexao.commit()

    for tipo in ("item", "campeao"):
        baixar_icones(conexao, numero_set, tipo, progresso)


def baixar_icones(conexao, numero_set, tipo, progresso=print):
    """Salva o ícone de cada item/campeão em dados/icones/<tipo>/<chave>.png (só os que faltam)."""
    pasta = PASTA_ICONES / tipo
    pasta.mkdir(parents=True, exist_ok=True)
    pendentes = [
        (chave, icone) for chave, icone in conexao.execute(
            "SELECT chave, icone FROM nomes_locais WHERE set_numero=? AND tipo=? AND icone IS NOT NULL",
            (numero_set, tipo),
        )
        if not (pasta / f"{chave}.png").exists()
    ]
    for numero, (chave, icone) in enumerate(pendentes, start=1):
        progresso(f"Baixando ícone de {tipo} {numero}/{len(pendentes)}...")
        resposta = requests.get(_url_do_icone(icone), timeout=TIMEOUT)
        if resposta.ok:
            (pasta / f"{chave}.png").write_bytes(resposta.content)


def nomes_locais(conexao, numero_set="18"):
    """{chave: nome em pt-BR}. Vazio se ainda não foi importado."""
    conexao.executescript(ESQUEMA)
    return dict(conexao.execute(
        "SELECT chave, nome FROM nomes_locais WHERE set_numero=? AND idioma='pt_br'", (numero_set,)
    ).fetchall())


def caminho_do_icone(tipo, chave):
    """tipo = "item" ou "campeao". None se o ícone não foi baixado."""
    caminho = PASTA_ICONES / tipo / f"{chave}.png"
    return caminho if caminho.exists() else None
