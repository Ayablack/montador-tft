"""Ícones de campeões e itens como 'data URI', para usar direto no HTML/CSS da página."""

import base64
import io
from functools import lru_cache

from PIL import Image

from dados import cdragon

TAMANHO = 64  # px; os ícones originais têm 128


@lru_cache(maxsize=None)
def data_uri(tipo, chave):
    """tipo = "campeao" ou "item". Devolve "" se o ícone não existe."""
    caminho = cdragon.caminho_do_icone(tipo, chave) if chave else None
    if not caminho:
        return ""
    imagem = Image.open(caminho).convert("RGB").resize((TAMANHO, TAMANHO), Image.LANCZOS)
    memoria = io.BytesIO()
    imagem.save(memoria, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(memoria.getvalue()).decode()
