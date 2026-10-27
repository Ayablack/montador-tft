import pandas as pd
import streamlit as st

from dados import banco
from logica import itens as modulo_itens
from logica import manuais, montador, taticas
from logica.loja import chance_na_loja

BRANCO = "⠀"


def aba_itens(catalogo, componentes):
    possiveis = modulo_itens.itens_que_pode_montar(componentes, catalogo)
    if possiveis:
        st.markdown("**Com seus componentes, dá para montar:**")
        for item in possiveis:
            receita = " + ".join(catalogo.itens[c].nome for c in item.componentes)
            st.markdown(f"- **{item.nome}** ({receita})")
    else:
        st.info("Clique nos componentes que você tem, na coluna da esquerda.")

    st.markdown("**Todas as receitas**")
    nome_de = lambda id_item: (
        catalogo.itens[id_item].nome if id_item in catalogo.itens else ""
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Item": i.nome,
                    "Tipo": i.tipo,
                    "Componente 1": nome_de(i.componentes[0]),
                    "Componente 2": nome_de(i.componentes[1]),
                }
                for i in sorted(catalogo.receitas(), key=lambda i: (i.tipo, i.nome))
            ]
        ),
        hide_index=True,
        width="stretch",
    )


def aba_loja(situacao, catalogo):
    st.markdown(f"**Chance de ver cada campeão numa loja no nível {situacao.nivel}**")
    linhas = []
    for campeao in sorted(catalogo.campeoes.values(), key=lambda c: (c.custo, c.nome)):
        copias = montador.copias_que_voce_tem(campeao, situacao)
        chance = chance_na_loja(campeao, situacao.nivel, catalogo, copias_suas=copias)
        linhas.append(
            {
                "Campeão": campeao.nome,
                "Custo": campeao.custo,
                "Você tem (cópias)": copias,
                "Chance por loja (%)": round(chance.chance_por_loja * 100, 1),
                "Rolls esperados": (
                    None
                    if chance.chance_por_loja == 0
                    else round(chance.rolls_esperados, 1)
                ),
            }
        )
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")

    st.markdown("**Chance de cada custo por nível (%)**")
    tabela = pd.DataFrame(catalogo.chances_loja).T.sort_index().fillna(0) * 100
    tabela.columns = [f"Custo {c}" for c in tabela.columns]
    tabela.index.name = "Nível"
    st.dataframe(tabela.round(0), width="stretch")


def aba_cadastro(catalogo):
    nome = st.text_input("Nome da comp")
    todos = sorted(catalogo.campeoes.values(), key=lambda c: (c.custo, c.nome))
    escolhidos = st.multiselect(
        "Campeões",
        todos,
        format_func=lambda c: f"{c.nome} ({c.custo})",
        key="nova_comp",
        placeholder="Escolha os campeões",
    )
    notas = st.text_area("Notas (opcional)")
    if st.button("Salvar comp") and nome and escolhidos:
        cadastro = manuais.ler()
        cadastro.append(
            {"nome": nome, "campeoes": [c.nome for c in escolhidos], "notas": notas}
        )
        manuais.salvar(cadastro)
        st.success("Comp salva em minhas_comps.json.")

    cadastradas = manuais.ler()
    if cadastradas:
        st.markdown("**Cadastradas**")
        for posicao, cadastro in enumerate(cadastradas):
            a, b = st.columns([5, 1])
            a.markdown(
                f"**{cadastro.get('nome')}** — {', '.join(cadastro.get('campeoes', []))}"
            )
            if b.button("Apagar", key=f"apagar_{posicao}"):
                manuais.salvar([c for i, c in enumerate(cadastradas) if i != posicao])
                st.rerun()


def aba_taticas(catalogo, tabelas_de_taticas_fn, total_de_partidas_fn):
    tabelas = tabelas_de_taticas_fn(catalogo, total_de_partidas_fn())
    if not tabelas:
        st.info(
            "Baixe partidas do alto elo (⚙️ Dados e chave da Riot) para ver as táticas."
        )
        return
    st.caption(
        f"Tabuleiro final de {tabelas['partidas']} partidas ranqueadas de Challenger/Grão-Mestre do BR. "
        "Colocação ajustada: com poucos jogos, a média é puxada para 4,5."
    )
    a, b = st.columns([2, 3])
    with a:
        st.markdown("**Nível final x colocação**")
        st.dataframe(tabelas["por_nivel"], hide_index=True, width="stretch")
    with b:
        st.markdown("**Campeões que mais ajudam a colocar bem**")
        st.dataframe(tabelas["campeoes"], hide_index=True, width="stretch", height=260)
    st.markdown("**Traços mais fortes (por nível ativado)**")
    st.dataframe(tabelas["tracos"], hide_index=True, width="stretch", height=260)

    st.markdown("**Melhores builds de 3 itens**")
    carries = sorted(catalogo.campeoes.values(), key=lambda c: -c.taxa_de_itens)
    campeao = st.selectbox(
        "Campeão",
        carries,
        format_func=lambda c: f"{c.nome} (segura 3 itens em {c.taxa_de_itens:.0%} dos jogos)",
    )
    builds = taticas.builds_do_campeao(catalogo, campeao.id)
    if builds:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Itens": " + ".join(catalogo.itens[i].nome for i in b.itens),
                        "Jogos": b.desempenho.jogos,
                        "Colocação média": round(b.desempenho.media, 2),
                        "Top 4": f"{b.desempenho.top4:.0%}",
                    }
                    for b in builds
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("Poucos jogos com esse campeão segurando 3 itens.")


TABELAS_DO_BANCO = [
    "campeoes",
    "tracos",
    "traco_niveis",
    "campeao_traco",
    "itens",
    "augments",
    "partidas",
    "participacoes",
    "metadados",
]


def aba_banco():
    a, b = st.columns(2)
    tabela = a.selectbox("Tabela", TABELAS_DO_BANCO)
    busca = b.text_input("Filtrar (qualquer coluna)")
    conexao = banco.conectar()
    limite = " LIMIT 2000" if tabela == "participacoes" else ""
    dados = pd.read_sql(f"SELECT * FROM {tabela}{limite}", conexao)
    conexao.close()
    if busca:
        dados = dados[
            dados.astype(str)
            .apply(lambda col: col.str.contains(busca, case=False))
            .any(axis=1)
        ]
    st.caption(f"{len(dados)} linhas" + (" (as primeiras 2000)" if limite else ""))
    st.dataframe(dados, hide_index=True, width="stretch")
