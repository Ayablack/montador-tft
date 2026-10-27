"""Acompanha as leituras da tela ao longo do tempo e deduz o que mudou.

A tela não mostra os campeões do tabuleiro pelo nome, então eles são deduzidos
pelas compras: quando uma carta da loja fica vazia e o ouro cai, você comprou
aquele campeão. Venda, carrossel e campeões ganhos de outro jeito não aparecem:
esses você corrige à mão no app.
"""

from dataclasses import dataclass, field

COPIAS_POR_ESTRELA = {1: 1, 2: 3, 3: 9}


def estrelas_por_copias(copias):
    if copias >= 9:
        return 3
    return 2 if copias >= 3 else 1


@dataclass
class Compra:
    campeao: object
    posicao: int


@dataclass
class Acompanhamento:
    loja_anterior: list = field(default_factory=list)  # Campeao/None por posição
    textos_anteriores: list = field(default_factory=list)  # texto lido em cada posição
    ouro_anterior: int | None = None

    def detectar_compras(self, leitura):
        """Compara com a leitura anterior. Devolve a lista de compras detectadas."""
        compras = []
        loja_visivel = any(leitura.textos_crus.get("loja", []))
        if (
            self.loja_anterior
            and loja_visivel
            and self.ouro_anterior is not None
            and leitura.ouro is not None
        ):
            gastou = self.ouro_anterior - leitura.ouro
            textos = leitura.textos_crus["loja"]
            # um roll troca todas as cartas; compra esvazia só a carta comprada
            mudaram = sum(
                1
                for antes, agora in zip(self.loja_anterior, leitura.loja)
                if antes != agora
            )
            if gastou > 0 and mudaram <= 2:
                for posicao, (antes, texto_agora) in enumerate(
                    zip(self.loja_anterior, textos)
                ):
                    if antes is not None and texto_agora == "":
                        compras.append(Compra(antes, posicao))

        if loja_visivel:
            self.loja_anterior = list(leitura.loja)
            self.textos_anteriores = list(leitura.textos_crus.get("loja", []))
        if leitura.ouro is not None:
            self.ouro_anterior = leitura.ouro
        return compras


def aplicar_compras(unidades, copias, compras):
    """Soma as cópias compradas e atualiza as estrelas. `unidades` e `copias` são dicts por id."""
    for compra in compras:
        id_campeao = compra.campeao.id
        atual = copias.get(id_campeao) or COPIAS_POR_ESTRELA.get(
            unidades.get(id_campeao, 0), 0
        )
        copias[id_campeao] = atual + 1
        unidades[id_campeao] = estrelas_por_copias(copias[id_campeao])


def componentes_e_emblemas(itens_lidos, catalogo):
    """Separa os itens lidos no banco: componentes (Counter por id) e emblemas (ids de traço)."""
    componentes, emblemas = {}, []
    for id_item, quantidade in itens_lidos.items():
        item = catalogo.itens.get(id_item)
        if not item:
            continue
        if item.tipo == "Componente":
            componentes[id_item] = quantidade
        elif item.tipo == "Emblema" and item.traco_id:
            emblemas += [item.traco_id] * quantidade
    return componentes, emblemas
