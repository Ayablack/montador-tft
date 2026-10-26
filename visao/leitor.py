"""Lê o HUD do TFT a partir de um print: loja, nível, ouro, traços e itens no banco."""

import re
from collections import Counter
from dataclasses import dataclass, field

import cv2
import numpy as np

from dados import cdragon
from logica.tradutor import Tradutor
from visao import ocr, regioes
from visao.captura import recortar

TAMANHO_COMPARACAO = 40     # px; ícones são comparados nesse tamanho
SEMELHANCA_MINIMA = 0.55    # abaixo disso, o ícone do banco não é considerado reconhecido
BRILHO_DE_VAZIO = 18        # quadrado de item quase preto = vazio
SATURACAO_DE_ATIVO = 60     # hexágono do traço colorido (bronze/prata/ouro) = traço ativo; cinza ~10
TIPOS_NO_BANCO = ("Componente", "Completo", "Emblema", "Radiante", "Artefato")


@dataclass
class LeituraDaTela:
    nivel: int | None = None
    ouro: int | None = None
    loja: list = field(default_factory=list)          # 5 posições: Campeao ou None (vazia/comprada)
    tracos: dict = field(default_factory=dict)        # traco_id -> quantidade (do painel)
    itens: Counter = field(default_factory=Counter)   # item_id -> quantidade no banco
    textos_crus: dict = field(default_factory=dict)   # o que o OCR leu, para conferir


def _recorte(imagem, caixa):
    return recortar(imagem, regioes.em_fracao(caixa))


def _numero(texto):
    achado = re.search(r"\d+", texto.replace("O", "0").replace("o", "0"))
    return int(achado.group()) if achado else None


class Leitor:
    def __init__(self, catalogo):
        self.catalogo = catalogo
        self.tradutor = Tradutor(catalogo)
        self.modelos = self._carregar_modelos_de_itens()

    def _carregar_modelos_de_itens(self):
        modelos = {}
        for item in self.catalogo.itens.values():
            caminho = cdragon.caminho_do_icone("item", item.chave)
            if item.tipo in TIPOS_NO_BANCO and caminho:
                icone = cv2.imdecode(np.fromfile(str(caminho), dtype=np.uint8), cv2.IMREAD_COLOR)
                modelos[item.id] = cv2.resize(icone, (TAMANHO_COMPARACAO, TAMANHO_COMPARACAO), interpolation=cv2.INTER_AREA)
        return modelos

    # ------------------------------------------------------------ partes do HUD

    def ler_nivel(self, imagem):
        """Pelo XP: '6/20' quer dizer que faltam 20 de XP para subir, e isso só acontece no nível 5."""
        texto = ocr.ler_texto(_recorte(imagem, regioes.NIVEL_E_XP))
        escrito = re.search(r"Nv\.?\s*(\d+)", texto)
        if escrito:
            return texto, int(escrito.group(1))
        xp = re.search(r"(\d+)\s*/\s*(\d+)", texto)
        if xp:
            niveis = [nivel for nivel, total in self.catalogo.xp_para_subir.items() if total == int(xp.group(2))]
            if niveis:
                return texto, min(niveis)  # se dois níveis pedem o mesmo XP, fica o menor
        return texto, None

    def ler_ouro(self, imagem):
        texto = ocr.ler_texto(_recorte(imagem, regioes.OURO))
        return texto, _numero(texto)

    # tratamentos de imagem tentados em ordem até reconhecer o texto: (ampliar, limiar)
    TENTATIVAS_LOJA = [(2, 0), (3, 0), (2, 150)]
    TENTATIVAS_TRACO = [(2, 140), (3, 170), (3, 0)]

    def ler_loja(self, imagem):
        """Nome de cada carta da loja. Cartas vazias ou especiais (ex.: 'Solitude') ficam None."""
        textos, campeoes = [], []
        for caixa in regioes.LOJA_NOMES:
            recorte = _recorte(imagem, caixa)
            texto, campeao = "", None
            for ampliar, limiar in self.TENTATIVAS_LOJA:
                texto = ocr.ler_texto(recorte, ampliar=ampliar, limiar=limiar)
                campeao = self.tradutor.campeao_do_texto(texto)
                if campeao:
                    break
            textos.append(texto)
            campeoes.append(campeao)
        return textos, campeoes

    def ler_tracos(self, imagem):
        """Painel da esquerda, linha por linha: '3 Solar 3/3', '2 Fumegante 2 > 3 > 4', '1 Defendente 1/2'.

        O nome sai quase sempre; o número às vezes some no OCR. Sem ele, usamos o '1/2'
        (traço inativo: o primeiro número é a quantidade) ou o primeiro breakpoint.
        """
        textos, tracos, linhas_vazias = [], {}, 0
        for caixa, hexagono in zip(regioes.caixas_dos_tracos(), regioes.caixas_dos_hexagonos()):
            recorte = _recorte(imagem, caixa)
            ativo = np.asarray(_recorte(imagem, hexagono).convert("HSV"))[:, :, 1].mean() > SATURACAO_DE_ATIVO
            traco, quantidade = None, None
            for ampliar, limiar in self.TENTATIVAS_TRACO:
                texto = ocr.ler_texto(recorte, ampliar=ampliar, limiar=limiar)
                # palavras de 2+ letras: assim o "I" (que é o 1 na fonte do jogo) não gruda no nome
                nome = re.search(r"[A-Za-zÀ-ÿ']{2,}(?:\s+[A-Za-zÀ-ÿ']{2,})*", texto)
                traco = self.tradutor.traco_do_texto(nome.group()) if nome else None
                if traco:
                    textos.append(texto)
                    quantidade = self._quantidade_do_traco(texto, nome, traco, ativo)
                    break
            if traco:
                tracos[traco.id] = quantidade
                linhas_vazias = 0
            else:
                linhas_vazias += 1
                if linhas_vazias == 2:  # acabou a lista de traços
                    break
        return textos, tracos

    @staticmethod
    def _quantidade_do_traco(texto, nome, traco, ativo):
        """O número fica numa caixinha antes do nome. Depois do nome vêm os breakpoints
        ('2 > 3 > 4') ou, se o traço está inativo, 'quantidade/próximo' ('1/2')."""
        def com_uns(trecho):  # a fonte do jogo desenha o 1 parecido com um I
            return re.sub(r"[Il|!]", "1", trecho)

        primeiro_nivel = traco.niveis[0] if traco.niveis else 1
        antes = re.search(r"(\d+)\s*$", com_uns(texto[:nome.start()]))
        numero_antes = int(antes.group(1)) if antes else None
        if ativo:
            if numero_antes and numero_antes >= primeiro_nivel:
                return numero_antes
            return primeiro_nivel  # sem o número: pelo menos o primeiro breakpoint
        depois = re.search(r"\d", com_uns(texto[nome.end():]))
        for candidato in (numero_antes, int(depois.group()) if depois else None):
            if candidato and candidato < primeiro_nivel:
                return candidato
        return 1

    def ler_itens(self, imagem):
        itens, detalhes = Counter(), []
        for caixa in regioes.caixas_dos_itens():
            pedaco = np.asarray(_recorte(imagem, caixa))[:, :, ::-1]  # PIL (RGB) -> OpenCV (BGR)
            if pedaco.mean() < BRILHO_DE_VAZIO:
                detalhes.append("vazio")
                continue
            pedaco = cv2.resize(pedaco, (TAMANHO_COMPARACAO, TAMANHO_COMPARACAO), interpolation=cv2.INTER_AREA)
            melhor_id, melhor_nota = None, -1.0
            for id_item, modelo in self.modelos.items():
                nota = float(cv2.matchTemplate(pedaco, modelo, cv2.TM_CCOEFF_NORMED)[0][0])
                if nota > melhor_nota:
                    melhor_id, melhor_nota = id_item, nota
            if melhor_nota >= SEMELHANCA_MINIMA:
                itens[melhor_id] += 1
                detalhes.append(f"{self.catalogo.itens[melhor_id].nome} ({melhor_nota:.2f})")
            else:
                detalhes.append(f"? ({melhor_nota:.2f})")
        return detalhes, itens

    # ------------------------------------------------------------ tudo de uma vez

    def ler(self, imagem):
        leitura = LeituraDaTela()
        texto_nivel, leitura.nivel = self.ler_nivel(imagem)
        texto_ouro, leitura.ouro = self.ler_ouro(imagem)
        textos_loja, leitura.loja = self.ler_loja(imagem)
        textos_tracos, leitura.tracos = self.ler_tracos(imagem)
        detalhes_itens, leitura.itens = self.ler_itens(imagem)
        leitura.textos_crus = {
            "nivel": texto_nivel, "ouro": texto_ouro, "loja": textos_loja,
            "tracos": textos_tracos, "itens": detalhes_itens,
        }
        return leitura
