"""Leitura de texto com o OCR que já vem no Windows (sem instalar programa)."""

from dataclasses import dataclass

import winocr
from PIL import Image, ImageOps

IDIOMA = "pt-BR"
AMPLIAR = 2  # texto pequeno do HUD é lido melhor ampliado


@dataclass
class Linha:
    texto: str
    x: float  # posição dentro da imagem recortada (em pixels da imagem original)
    y: float


MARGEM = 30  # o OCR do Windows erra menos quando o texto não encosta na borda


def preparar(imagem, inverter=False, ampliar=AMPLIAR, limiar=0):
    """Cinza, ampliado e com margem.

    inverter: texto claro em fundo escuro vira escuro em fundo claro.
    limiar: se > 0, vira preto e branco (pixels mais claros que o limiar viram texto preto).
    """
    imagem = ImageOps.grayscale(imagem)
    imagem = imagem.resize(
        (imagem.width * ampliar, imagem.height * ampliar), Image.LANCZOS
    )
    if limiar:
        imagem = imagem.point(lambda valor: 0 if valor > limiar else 255)
    elif inverter:
        imagem = ImageOps.invert(imagem)
    imagem = ImageOps.expand(
        imagem, border=MARGEM, fill=255 if (limiar or inverter) else 0
    )
    return imagem.convert("RGB")


def ler_linhas(imagem, inverter=False, ampliar=AMPLIAR, limiar=0):
    resultado = winocr.recognize_pil_sync(
        preparar(imagem, inverter, ampliar, limiar), IDIOMA
    )
    linhas = []
    for linha in resultado.get("lines", []):
        primeira = (
            linha["words"][0]["bounding_rect"]
            if linha.get("words")
            else {"x": MARGEM, "y": MARGEM}
        )
        linhas.append(
            Linha(
                linha["text"],
                (primeira["x"] - MARGEM) / ampliar,
                (primeira["y"] - MARGEM) / ampliar,
            )
        )
    return linhas


def ler_texto(imagem, inverter=False, ampliar=AMPLIAR, limiar=0):
    return " ".join(
        linha.texto for linha in ler_linhas(imagem, inverter, ampliar, limiar)
    )
