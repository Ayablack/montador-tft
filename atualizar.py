"""Atualiza o banco de dados (dados/tft.db).

python atualizar.py            dados do set (Community Dragon) e ícones
python atualizar.py --meta     também baixa partidas de alto elo da Riot (precisa da chave)
"""

import sys
from pathlib import Path

from dados import banco, cdragon, riot
from log import get_logger

BANCO_ANTIGO = Path(__file__).parent / "dados" / "datatft.db"  # versão anterior do app


def atualizar_dados_de_jogo(progresso=None):
    if progresso is None:
        progresso = get_logger().info
    conexao = banco.conectar()
    cdragon.importar(conexao, progresso=progresso)
    trazidas = banco.importar_partidas_antigas(conexao, BANCO_ANTIGO)
    if trazidas:
        progresso(f"{trazidas} registros de partidas trazidos do banco antigo.")
    conexao.close()
    progresso("Pronto: dados do set atualizados.")


def atualizar_meta(progresso=None):
    if progresso is None:
        progresso = get_logger().info
    chave = riot.ler_chave()
    if not chave:
        raise riot.ErroRiot(
            "Sem chave da Riot. Coloque RIOT_API_KEY=... no arquivo .env (veja o README)."
        )
    conexao = banco.conectar()
    novas = riot.coletar_partidas(conexao, chave, progresso=progresso)
    total = conexao.execute("SELECT COUNT(*) FROM partidas").fetchone()[0]
    conexao.close()
    progresso(f"Pronto: {novas} partidas novas ({total} no banco).")


if __name__ == "__main__":
    atualizar_dados_de_jogo()
    if "--meta" in sys.argv:
        atualizar_meta()
