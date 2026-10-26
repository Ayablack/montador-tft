"""Carrega os dados de um set do banco para objetos simples, usados pelo resto da lógica.

Os nomes ficam em português (como aparecem no jogo) quando o Community Dragon tem
a tradução; o nome em inglês do datatft fica guardado em `nome_en`.
"""

from dataclasses import dataclass, field

from dados import banco, cdragon

SET_PADRAO = "18"
IDIOMA_PADRAO = "en"
COMPONENTES_ESPECIAIS = {508, 31000}  # Espátula e Frigideira (fazem emblemas)


@dataclass(frozen=True)
class Traco:
    id: str
    nome: str
    tipo: str               # "origem" ou "classe"
    niveis: tuple           # ex.: (2, 4, 6)
    estilos: tuple          # 1 bronze, 2 prata, 3 ouro, 4 prismático (um por nível)
    descricao: str = ""
    chave: str = ""         # nome interno (o mesmo da Riot e do Community Dragon)
    nome_en: str = ""

    @property
    def unico(self):
        """Traço de um campeão só (ex.: Avatar da Lux): ativa sozinho."""
        return self.niveis == (1,)


@dataclass(frozen=True)
class Campeao:
    id: int
    nome: str
    custo: int
    tracos: tuple           # ids dos traços
    itens_recomendados: tuple
    papel: str = ""
    habilidade: str = ""
    chave: str = ""
    nome_en: str = ""


@dataclass(frozen=True)
class Item:
    id: int
    nome: str
    tipo: str
    componentes: tuple      # (id, id) ou () para componentes e itens sem receita
    traco_id: str | None = None  # para emblemas
    chave: str = ""
    nome_en: str = ""


@dataclass
class Catalogo:
    numero_set: str
    campeoes: dict = field(default_factory=dict)        # id -> Campeao
    tracos: dict = field(default_factory=dict)          # id -> Traco
    itens: dict = field(default_factory=dict)           # id -> Item
    chances_loja: dict = field(default_factory=dict)    # nivel -> {custo: chance}
    copias_por_custo: dict = field(default_factory=dict)  # custo -> cópias de cada campeão no pool
    xp_para_subir: dict = field(default_factory=dict)   # nivel -> XP para ir ao próximo nível
    nomes_locais: dict = field(default_factory=dict)    # chave -> nome em português (como aparece no jogo)

    def chances_no_nivel(self, nivel):
        """{custo: chance} no nível. Acima do último nível da tabela, usa o último."""
        if not self.chances_loja:
            return {}
        return self.chances_loja.get(min(nivel, max(self.chances_loja)), {})

    def campeao_por_nome(self, nome):
        """Aceita o nome em português ou em inglês."""
        return next((c for c in self.campeoes.values() if nome in (c.nome, c.nome_en)), None)

    def componentes(self):
        return sorted((i for i in self.itens.values() if i.tipo == "Componente"), key=lambda i: i.id)

    def receitas(self):
        """Itens que se montam com dois componentes."""
        return [i for i in self.itens.values() if len(i.componentes) == 2]


def carregar(numero_set=SET_PADRAO, idioma=IDIOMA_PADRAO):
    conexao = banco.conectar()
    filtro = (numero_set, idioma)
    catalogo = Catalogo(numero_set=numero_set)
    catalogo.nomes_locais = cdragon.nomes_locais(conexao, numero_set)

    def nome_local(linha):
        return catalogo.nomes_locais.get(linha["chave"]) or linha["nome"]

    niveis = {}
    for linha in conexao.execute(
        "SELECT traco_id, quantidade, estilo FROM traco_niveis WHERE set_numero=? AND idioma=? ORDER BY quantidade",
        filtro,
    ):
        niveis.setdefault(linha["traco_id"], []).append((linha["quantidade"], linha["estilo"] or 1))

    for linha in conexao.execute("SELECT * FROM tracos WHERE set_numero=? AND idioma=?", filtro):
        lista = niveis.get(linha["id"], [])
        catalogo.tracos[linha["id"]] = Traco(
            id=linha["id"], nome=nome_local(linha), nome_en=linha["nome"], tipo=linha["tipo"],
            descricao=linha["descricao"], chave=linha["chave"] or "",
            niveis=tuple(q for q, _ in lista), estilos=tuple(e for _, e in lista),
        )

    tracos_do_campeao = {}
    for linha in conexao.execute("SELECT campeao_id, traco_id FROM campeao_traco WHERE set_numero=? AND idioma=?", filtro):
        tracos_do_campeao.setdefault(linha["campeao_id"], []).append(linha["traco_id"])

    for linha in conexao.execute("SELECT * FROM campeoes WHERE set_numero=? AND idioma=?", filtro):
        recomendados = tuple(int(x) for x in (linha["itens_recomendados"] or "").split(",") if x.strip().isdigit())
        catalogo.campeoes[linha["id"]] = Campeao(
            id=linha["id"], nome=nome_local(linha), nome_en=linha["nome"], custo=linha["custo"],
            tracos=tuple(tracos_do_campeao.get(linha["id"], [])), itens_recomendados=recomendados,
            papel=linha["papel"] or "", habilidade=linha["habilidade"] or "", chave=linha["chave"] or "",
        )

    for linha in conexao.execute("SELECT * FROM itens WHERE set_numero=? AND idioma=?", filtro):
        componentes = tuple(c for c in (linha["componente_1"], linha["componente_2"]) if c)
        catalogo.itens[linha["id"]] = Item(
            id=linha["id"], nome=nome_local(linha), nome_en=linha["nome"], tipo=linha["tipo"],
            componentes=componentes, traco_id=linha["traco_id"], chave=linha["chave"] or "",
        )

    for linha in conexao.execute("SELECT nivel, custo, chance FROM economia_loja WHERE set_numero=? AND idioma=?", filtro):
        catalogo.chances_loja.setdefault(linha["nivel"], {})[linha["custo"]] = linha["chance"]

    for linha in conexao.execute("SELECT custo, copias FROM pool WHERE set_numero=? AND idioma=?", filtro):
        catalogo.copias_por_custo[linha["custo"]] = linha["copias"]

    for linha in conexao.execute("SELECT nivel, xp_para_subir FROM economia_xp WHERE set_numero=? AND idioma=?", filtro):
        catalogo.xp_para_subir[linha["nivel"]] = linha["xp_para_subir"]

    conexao.close()
    return catalogo
