"""Baixa os dados de jogo do datatft.com (campeões, traços, itens, augments...).

O site não tem API para isso: a página /database baixa um JSON estático por set,
com um hash no nome (ex.: h5-data-en-18-Cml3L0oR.json). O hash muda a cada deploy,
então aqui a gente descobre os nomes atuais lendo os scripts do site.
"""

import json
import re
from pathlib import Path

import requests

SITE = "https://www.datatft.com"
PASTA_BRUTOS = Path(__file__).parent / "brutos"
TIMEOUT = 30

# h5-data-<idioma>-<set>-<hash>.json  ->  idioma "en"/"cn", set "18", "16.5"...
PADRAO_ARQUIVO = re.compile(r"h5-data-(en|cn)-([\d.]+)-[\w-]+\.json")


def _baixar_texto(url):
    resposta = requests.get(url, timeout=TIMEOUT)
    resposta.raise_for_status()
    return resposta.text


def descobrir_arquivos():
    """Retorna {(idioma, set): url} com todos os arquivos de dados disponíveis no site."""
    pagina = _baixar_texto(f"{SITE}/database")
    script_principal = re.search(r'src="(/assets/index-[\w-]+\.js)"', pagina).group(1)
    codigo = _baixar_texto(SITE + script_principal)

    # O script principal só cita o "loadData-xxx.js", que é quem lista os JSONs
    carregador = re.search(r"assets/(loadData-[\w-]+\.js)", codigo).group(1)
    codigo_carregador = _baixar_texto(f"{SITE}/assets/{carregador}")

    arquivos = {}
    for encontrado in PADRAO_ARQUIVO.finditer(codigo_carregador):
        idioma, numero_set = encontrado.group(1), encontrado.group(2)
        arquivos[(idioma, numero_set)] = f"{SITE}/assets/{encontrado.group(0)}"
    return arquivos


def baixar_set(url, idioma, numero_set):
    """Baixa um arquivo de dados, salva uma cópia em dados/brutos/ e devolve o dict."""
    conteudo = json.loads(_baixar_texto(url))
    PASTA_BRUTOS.mkdir(exist_ok=True)
    destino = PASTA_BRUTOS / f"{idioma}-{numero_set}.json"
    destino.write_text(json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")
    return conteudo
