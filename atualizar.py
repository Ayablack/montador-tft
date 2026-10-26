"""Atualiza o banco de dados.

    python atualizar.py            baixa os dados de jogo do datatft (todos os sets)
    python atualizar.py --meta     também baixa partidas de alto elo da Riot (precisa da chave)
"""

import sys

from dados import banco, cdragon, coleta, riot


def atualizar_dados_de_jogo(progresso=print):
    conexao = banco.conectar()
    arquivos = coleta.descobrir_arquivos()
    for (idioma, numero_set), url in sorted(arquivos.items()):
        progresso(f"Baixando set {numero_set} ({idioma})...")
        dados = coleta.baixar_set(url, idioma, numero_set)
        banco.importar_set(conexao, dados, idioma, numero_set)
    cdragon.importar(conexao, progresso=progresso)  # nomes em pt-BR e ícones, para ler a tela
    conexao.close()
    progresso(f"Pronto: {len(arquivos)} arquivos importados.")


def atualizar_meta(progresso=print):
    chave = riot.ler_chave()
    if not chave:
        raise riot.ErroRiot("Sem chave da Riot. Coloque RIOT_API_KEY=... no arquivo .env (veja o README).")
    conexao = banco.conectar()
    novas = riot.coletar_partidas(conexao, chave, progresso=progresso)
    total = conexao.execute("SELECT COUNT(*) FROM partidas").fetchone()[0]
    conexao.close()
    progresso(f"Pronto: {novas} partidas novas ({total} no banco).")


if __name__ == "__main__":
    atualizar_dados_de_jogo()
    if "--meta" in sys.argv:
        atualizar_meta()
