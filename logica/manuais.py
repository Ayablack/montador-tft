"""Comps cadastradas à mão no arquivo minhas_comps.json (na raiz do projeto).

Formato do arquivo (nomes como aparecem no jogo; acento e maiúsculas não importam):
[
  {
    "nome": "Sabugueiro Enfeitiçador",
    "campeoes": ["LeBlanc", "Alistar", "Ornn", "Ezreal", "Gnar"],
    "notas": "Jogar no nível 8 e procurar Ezreal 2★"
  }
]
"""

import json
from pathlib import Path

from logica.montador import avaliar

ARQUIVO = Path(__file__).parent.parent / "minhas_comps.json"


def ler():
    if not ARQUIVO.exists():
        return []
    return json.loads(ARQUIVO.read_text(encoding="utf-8"))


def salvar(comps):
    ARQUIVO.write_text(
        json.dumps(comps, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def avaliar_todas(situacao, catalogo):
    """Avalia cada comp do arquivo contra o que você tem. Devolve (comps, nomes não encontrados)."""
    avaliadas, desconhecidos = [], []
    for cadastro in ler():
        campeoes = []
        for nome in cadastro.get("campeoes", []):
            campeao = catalogo.campeao_por_nome(nome)
            if campeao:
                campeoes.append(campeao)
            else:
                desconhecidos.append(nome)
        if campeoes:
            comp = avaliar(
                campeoes,
                situacao,
                catalogo,
                nome=cadastro.get("nome", "Sem nome"),
                origem="Minhas comps",
            )
            comp.estatisticas = {"notas": cadastro.get("notas", "")}
            avaliadas.append(comp)
    avaliadas.sort(
        key=lambda comp: (comp.porcentagem_que_tem, comp.pontuacao), reverse=True
    )
    return avaliadas, desconhecidos
