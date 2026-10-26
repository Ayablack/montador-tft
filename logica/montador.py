"""Sugere composições a partir do que o jogador tem em jogo.

Ideia: monta times campeão por campeão (busca em feixe), dando nota para cada time.
A nota soma:
  + traços ativos (quanto mais alto o nível do traço, mais pontos)
  + campeões que você já tem (mais ainda se estiverem com 2★ ou 3★)
  - campeões que faltam, pesando pela chance de achar no seu nível
Os pesos ficam todos aqui em cima, para facilitar ajustes.
"""

from dataclasses import dataclass, field

from logica.loja import chance_na_loja, copias_por_estrela
from logica.tracos import contar, situacao_do_traco, tracos_do_time

# ---------------------------------------------------------------- pesos

PONTOS_POR_ESTILO = {1: 1.0, 2: 2.0, 3: 3.5, 4: 5.0}  # bronze, prata, ouro, prismático
PONTOS_TRACO_UNICO = 0.5        # traços de um campeão só ativam sozinhos, valem pouco
PESO_PROGRESSO = 0.4            # crédito parcial por estar perto do próximo nível
BONUS_JA_TEM = 1.5              # por campeão que você já tem
BONUS_POR_ESTRELA = 0.75        # extra por estrela acima de 1★
PONTOS_POR_CUSTO = 0.15         # campeões mais caros são mais fortes
PENALIDADE_FALTANDO = 0.5       # base por campeão que falta comprar
PENALIDADE_RARIDADE = 2.0       # extra para custos que aparecem pouco na loja no seu nível
PENALIDADE_INDISPONIVEL = 3.0   # campeão que ainda não aparece na loja no seu nível

LARGURA_DO_FEIXE = 60
PENALIDADE_REPETIDO = 1.2       # para variar: campeão (que você não tem) já usado numa sugestão anterior
DIFERENCA_MINIMA = 2            # comps sugeridas precisam diferir em pelo menos 2 campeões


@dataclass
class Situacao:
    """O que o jogador tem agora."""
    nivel: int
    unidades: dict = field(default_factory=dict)   # campeao_id -> estrelas
    emblemas: list = field(default_factory=list)   # ids dos traços dos emblemas que tem
    fixos: list = field(default_factory=list)      # campeões que quer obrigatoriamente no time


@dataclass
class CompAvaliada:
    nome: str
    campeoes: list
    tracos: list          # TracoNoTime
    pontuacao: float
    tem: list             # campeões que você já tem
    faltam: list          # campeões que faltam comprar
    origem: str = "Algoritmo"
    estatisticas: dict = field(default_factory=dict)  # só para comps meta (colocação média etc.)

    @property
    def porcentagem_que_tem(self):
        return len(self.tem) / len(self.campeoes) if self.campeoes else 0


# ---------------------------------------------------------------- nota de um time

def _pontos_de_tracos(contagem, catalogo):
    pontos = 0.0
    for id_traco, quantidade in contagem.items():
        traco = catalogo.tracos.get(id_traco)
        if not traco or not traco.niveis:
            continue
        situacao = situacao_do_traco(traco, quantidade)
        if situacao.ativo:
            pontos += PONTOS_TRACO_UNICO if traco.unico else PONTOS_POR_ESTILO.get(situacao.estilo, 1.0)
        if situacao.proximo_nivel:
            estilo_seguinte = traco.estilos[traco.niveis.index(situacao.proximo_nivel)]
            pontos += PESO_PROGRESSO * PONTOS_POR_ESTILO.get(estilo_seguinte, 1.0) * quantidade / situacao.proximo_nivel
    return pontos


def _pontos_do_campeao(campeao, situacao, catalogo):
    pontos = PONTOS_POR_CUSTO * campeao.custo
    estrelas = situacao.unidades.get(campeao.id)
    if estrelas:
        return pontos + BONUS_JA_TEM + BONUS_POR_ESTRELA * (estrelas - 1)
    chances = catalogo.chances_no_nivel(situacao.nivel)
    chance_do_custo = chances.get(campeao.custo, 0.0)
    if chance_do_custo == 0:
        return pontos - PENALIDADE_INDISPONIVEL
    # comparado ao custo mais comum no seu nível: 1.0 = o mais fácil de achar
    facilidade = chance_do_custo / max(chances.values())
    return pontos - PENALIDADE_FALTANDO - PENALIDADE_RARIDADE * (1 - facilidade)


def pontuar(campeoes, situacao, catalogo):
    contagem = contar(campeoes, situacao.emblemas)
    return _pontos_de_tracos(contagem, catalogo) + sum(
        _pontos_do_campeao(c, situacao, catalogo) for c in campeoes
    )


def avaliar(campeoes, situacao, catalogo, nome=None, origem="Algoritmo"):
    """Monta o resumo de um time: traços, o que você tem, o que falta e a nota."""
    campeoes = sorted(campeoes, key=lambda c: (c.custo, c.nome))
    tracos = tracos_do_time(campeoes, catalogo, situacao.emblemas)
    if nome is None:
        principais = [t.traco.nome for t in tracos if t.ativo and not t.traco.unico][:2]
        nome = " + ".join(principais) or "Time sem traços"
    return CompAvaliada(
        nome=nome,
        campeoes=campeoes,
        tracos=tracos,
        pontuacao=round(pontuar(campeoes, situacao, catalogo), 1),
        tem=[c for c in campeoes if c.id in situacao.unidades],
        faltam=[c for c in campeoes if c.id not in situacao.unidades],
        origem=origem,
    )


# ---------------------------------------------------------------- busca

def _buscar_time(situacao, catalogo, tamanho, ja_usados):
    """Uma busca em feixe. Devolve os times finais, do melhor pro pior."""
    campeoes = catalogo.campeoes
    fixos = frozenset(i for i in situacao.fixos if i in campeoes)

    def nota(time):
        repetidos = sum(1 for i in time if i in ja_usados and i not in situacao.unidades)
        return pontuar([campeoes[i] for i in time], situacao, catalogo) - PENALIDADE_REPETIDO * repetidos

    feixe = {fixos: nota(fixos)}
    for _passo in range(tamanho - len(fixos)):
        candidatos = {}
        for time in feixe:
            for id_campeao in campeoes:
                novo = time | {id_campeao}
                if id_campeao not in time and novo not in candidatos:
                    candidatos[novo] = nota(novo)
        feixe = dict(sorted(candidatos.items(), key=lambda item: item[1], reverse=True)[:LARGURA_DO_FEIXE])
    return [time for time, _ in sorted(feixe.items(), key=lambda item: item[1], reverse=True)]


def sugerir_comps(situacao, catalogo, quantidade=5, tamanho=None):
    """Devolve as melhores comps para a situação, diferentes entre si.

    Roda uma busca por sugestão; a cada rodada, os campeões já sugeridos perdem
    pontos, para a próxima busca explorar outros caminhos.
    """
    tamanho = tamanho or max(situacao.nivel, len(situacao.fixos), 1)
    escolhidos, ja_usados = [], set()
    for _rodada in range(quantidade):
        for time in _buscar_time(situacao, catalogo, tamanho, ja_usados):
            if all(len(time - outro) >= DIFERENCA_MINIMA for outro in escolhidos):
                escolhidos.append(time)
                ja_usados |= time
                break

    comps = [avaliar([catalogo.campeoes[i] for i in time], situacao, catalogo) for time in escolhidos]
    return sorted(comps, key=lambda comp: comp.pontuacao, reverse=True)


def copias_que_voce_tem(campeao, situacao):
    return copias_por_estrela(situacao.unidades[campeao.id]) if campeao.id in situacao.unidades else 0


def chance_dos_que_faltam(comp, situacao, catalogo):
    """Para cada campeão que falta: chance de vê-lo numa loja no seu nível."""
    return {
        c.id: chance_na_loja(c, situacao.nivel, catalogo, copias_suas=copias_que_voce_tem(c, situacao))
        for c in comp.faltam
    }
