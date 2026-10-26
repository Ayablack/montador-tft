"""Carrega os dados do set do banco para objetos simples, usados pelo resto da lógica.

Os ids são os nomes internos da Riot (ex.: 'DA_18_LeBlanc'), iguais aos das partidas
da API, e os nomes estão em português, como aparecem no jogo.
"""

from dataclasses import dataclass, field, replace

from dados import banco, economia

SET_PADRAO = "18"
COMPONENTES_ESPECIAIS = {"DA_Component_Spatula", "DA_Component_FryingPan"}  # fazem emblemas


@dataclass(frozen=True)
class Traco:
    id: str
    nome: str
    niveis: tuple           # ex.: (2, 4, 6)
    estilos: tuple          # 1 bronze, 2 prata, 3 ouro, 4 prismático (um por nível)
    descricao: str = ""
    efeitos: tuple = ()     # texto do efeito de cada nível

    @property
    def unico(self):
        """Traço de um campeão só (ex.: Avatar da Lux): ativa sozinho."""
        return self.niveis == (1,)

    @property
    def chave(self):
        return self.id


@dataclass(frozen=True)
class Campeao:
    id: str
    nome: str
    custo: int
    tracos: tuple           # ids dos traços
    # os três abaixo vêm das partidas de alto elo (logica/taticas.py)
    itens_recomendados: tuple = ()
    impacto: float = 0.0        # colocação acima (+) ou abaixo (-) da média de quem termina com ele
    taxa_de_itens: float = 0.0  # fração das partidas em que ele segura 3 itens (alta = carry)
    habilidade: str = ""
    habilidade_desc: str = ""
    alcance: float = 0

    @property
    def chave(self):
        return self.id


@dataclass(frozen=True)
class Item:
    id: str
    nome: str
    tipo: str               # Componente, Completo, Emblema, Radiante, Artefato, Especial
    componentes: tuple      # (id, id) ou () para componentes e itens sem receita
    traco_id: str | None = None  # para emblemas
    descricao: str = ""

    @property
    def chave(self):
        return self.id


@dataclass
class Catalogo:
    numero_set: str
    campeoes: dict = field(default_factory=dict)        # id -> Campeao
    tracos: dict = field(default_factory=dict)          # id -> Traco
    itens: dict = field(default_factory=dict)           # id -> Item
    chances_loja: dict = field(default_factory=lambda: dict(economia.CHANCES_DA_LOJA))
    copias_por_custo: dict = field(default_factory=lambda: dict(economia.COPIAS_POR_CUSTO))
    xp_para_subir: dict = field(default_factory=lambda: dict(economia.XP_PARA_SUBIR))
    impacto_dos_tracos: dict = field(default_factory=dict)  # (traco_id, nivel) -> impacto (alto elo)

    def chances_no_nivel(self, nivel):
        """{custo: chance} no nível. Acima do último nível da tabela, usa o último."""
        return self.chances_loja.get(min(max(nivel, 1), max(self.chances_loja)), {})

    def campeao_por_nome(self, nome):
        """Aceita o nome com ou sem acento/maiúsculas (ex.: 'kogmaw' acha Kog'Maw) ou o id."""
        procurado = _simples(nome)
        return next((c for c in self.campeoes.values() if procurado in (_simples(c.nome), _simples(c.id))), None)

    def componentes(self):
        return sorted((i for i in self.itens.values() if i.tipo == "Componente"),
                      key=lambda i: (i.id in COMPONENTES_ESPECIAIS, i.nome))

    def receitas(self):
        """Itens que se montam com dois componentes."""
        return [i for i in self.itens.values() if len(i.componentes) == 2]


def _simples(texto):
    return "".join(letra for letra in (texto or "").lower() if letra.isalnum())


def carregar(numero_set=SET_PADRAO, com_taticas=True):
    """Lê o banco. Com `com_taticas`, os itens recomendados vêm das partidas de alto elo."""
    conexao = banco.conectar()
    catalogo = Catalogo(numero_set=numero_set)

    niveis = {}
    for linha in conexao.execute("SELECT traco, minimo, estilo, efeito FROM traco_niveis ORDER BY minimo"):
        niveis.setdefault(linha["traco"], []).append((linha["minimo"], linha["estilo"], linha["efeito"] or ""))
    for linha in conexao.execute("SELECT * FROM tracos"):
        lista = niveis.get(linha["chave"], [])
        catalogo.tracos[linha["chave"]] = Traco(
            id=linha["chave"], nome=linha["nome"], descricao=linha["descricao"] or "",
            niveis=tuple(n for n, _, _ in lista), estilos=tuple(e for _, e, _ in lista),
            efeitos=tuple(t for _, _, t in lista),
        )

    tracos_do_campeao = {}
    for linha in conexao.execute("SELECT campeao, traco FROM campeao_traco"):
        tracos_do_campeao.setdefault(linha["campeao"], []).append(linha["traco"])
    for linha in conexao.execute("SELECT * FROM campeoes"):
        catalogo.campeoes[linha["chave"]] = Campeao(
            id=linha["chave"], nome=linha["nome"], custo=linha["custo"],
            tracos=tuple(tracos_do_campeao.get(linha["chave"], [])),
            habilidade=linha["habilidade"] or "", habilidade_desc=linha["habilidade_desc"] or "",
            alcance=linha["alcance"] or 0,
        )

    for linha in conexao.execute("SELECT * FROM itens"):
        catalogo.itens[linha["chave"]] = Item(
            id=linha["chave"], nome=linha["nome"], tipo=linha["tipo"],
            componentes=tuple(c for c in (linha["componente_1"], linha["componente_2"]) if c),
            traco_id=linha["traco"], descricao=linha["descricao"] or "",
        )
    conexao.close()

    if com_taticas:
        aplicar_taticas(catalogo)
    return catalogo


def aplicar_taticas(catalogo):
    """Preenche itens recomendados, impacto e taxa de itens com o que as partidas de alto elo mostram."""
    from logica import taticas  # aqui dentro: taticas também usa o catálogo

    tabuleiros = taticas.ler_tabuleiros(catalogo)
    if not tabuleiros:
        return
    recomendados = taticas.itens_recomendados(catalogo)
    forca = taticas.forca_dos_campeoes(catalogo, tabuleiros)
    carry = taticas.taxa_de_carry(catalogo, tabuleiros)
    catalogo.campeoes = {
        id_: replace(
            c, itens_recomendados=tuple(recomendados.get(id_, ())),
            impacto=round(forca[id_].impacto, 3) if id_ in forca else 0.0,
            taxa_de_itens=round(carry.get(id_, 0.0), 3),
        )
        for id_, c in catalogo.campeoes.items()
    }
    catalogo.impacto_dos_tracos = {
        chave: round(d.impacto, 3) for chave, d in taticas.forca_dos_tracos(catalogo, tabuleiros).items()
    }
