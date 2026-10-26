"""Endereço dos ícones de campeões e itens para usar no HTML/CSS da página.

Os ícones ficam em static/icones e o Streamlit serve essa pasta em /app/static/
(opção enableStaticServing em .streamlit/config.toml). Assim o navegador baixa cada
ícone uma vez e guarda em cache, em vez de receber as imagens a cada clique.
"""

from dados import cdragon


def icone(tipo, chave):
    """tipo = "campeao" ou "item". Devolve "" se o ícone não foi baixado."""
    if not chave or not cdragon.caminho_do_icone(tipo, chave):
        return ""
    return f"./app/static/icones/{tipo}/{chave}.png"
