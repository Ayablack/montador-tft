"""Montador de comps de TFT. Para abrir:  streamlit run app.py  (ou clique em iniciar.bat)

Este arquivo só monta a página. O visual (HTML/CSS) fica em interface/ e as contas em logica/.
"""

import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

import atualizar
from dados import banco, riot
from interface import estilo
from interface.cartoes import html_da_comp, html_da_loja
from logica import catalogo as modulo_catalogo
from logica import itens as modulo_itens
from logica import manuais, meta, montador
from logica.loja import chance_na_loja
from visao import acompanhamento, estado_compartilhado
from visao.captura import capturar_tela
from visao.leitor import Leitor

st.set_page_config(page_title="Montador TFT", page_icon="🧩", layout="wide", initial_sidebar_state="collapsed")

ADICIONAR, REMOVER = "➕ Adicionar", "➖ Remover"
FONTES = ["Todas", "Para você", "Meta", "Minhas"]
BRANCO = "⠀"  # rótulo "vazio" para os botões de retrato
SEGUNDOS_ENTRE_LEITURAS = 2
PASTA_DO_APP = Path(__file__).resolve().parent


# ---------------------------------------------------------------- dados (com cache)

@st.cache_resource
def carregar_catalogo():
    return modulo_catalogo.carregar()


@st.cache_resource
def carregar_leitor():
    return Leitor(carregar_catalogo())


def banco_vazio():
    conexao = banco.conectar()
    vazio = conexao.execute("SELECT COUNT(*) FROM campeoes").fetchone()[0] == 0
    conexao.close()
    return vazio


def total_de_partidas():
    conexao = banco.conectar()
    total = conexao.execute("SELECT COUNT(*) FROM partidas").fetchone()[0]
    conexao.close()
    return total


def _situacao_de(chave):
    nivel, unidades, emblemas, fixos = chave
    return montador.Situacao(nivel=nivel, unidades=dict(unidades), emblemas=list(emblemas), fixos=list(fixos))


@st.cache_resource(show_spinner=False, max_entries=50)  # sem cópia: não quebra se o código mudar com o app aberto
def comps_do_algoritmo(_catalogo, chave_situacao, tamanho):
    return montador.sugerir_comps(_situacao_de(chave_situacao), _catalogo, quantidade=5, tamanho=tamanho)


@st.cache_resource(show_spinner=False, max_entries=50)
def comps_da_meta(_catalogo, chave_situacao, partidas):  # `partidas` só serve para renovar o cache
    return meta.comps_meta(_situacao_de(chave_situacao), _catalogo)


# ---------------------------------------------------------------- estado do seu jogo

def iniciar_estado():
    st.session_state.setdefault("unidades", {})          # campeao_id -> estrelas
    st.session_state.setdefault("componentes", Counter())  # componente_id -> quantidade
    st.session_state.setdefault("nivel", 7)
    st.session_state.setdefault("overlay", overlay_aberto())
    st.session_state.setdefault("copias", {})            # campeao_id -> cópias compradas (leitura da tela)
    st.session_state.setdefault("acompanhamento", acompanhamento.Acompanhamento())
    st.session_state.setdefault("leitura", None)         # última leitura da tela
    st.session_state.setdefault("emblemas_lidos", [])    # ids de traço dos emblemas no banco
    st.session_state.setdefault("compras_recentes", [])
    # o nível lido da tela só pode entrar antes de o campo "Nível" ser desenhado
    nivel_lido = st.session_state.pop("nivel_lido", None)
    if nivel_lido:
        st.session_state.nivel = nivel_lido


# ---------------------------------------------------------------- overlay (janela por cima do jogo)

@st.cache_resource
def processo_do_overlay():
    """Guarda o processo do overlay entre as atualizações da página."""
    return {"processo": None}


def overlay_aberto():
    processo = processo_do_overlay()["processo"]
    return processo is not None and processo.poll() is None


def ligar_ou_desligar_overlay():
    guardado = processo_do_overlay()
    if overlay_aberto():
        guardado["processo"].terminate()
    guardado["processo"] = None
    if st.session_state.overlay:
        sem_console = Path(sys.executable).with_name("pythonw.exe")
        python = str(sem_console) if sem_console.exists() else sys.executable
        guardado["processo"] = subprocess.Popen([python, "overlay.py", str(os.getpid())], cwd=PASTA_DO_APP)


def removendo():
    return st.session_state.get("modo") == REMOVER


def clicar_campeao(id_campeao):
    unidades = st.session_state.unidades
    estrelas = unidades.get(id_campeao, 0) + (-1 if removendo() else 1)
    if estrelas <= 0:
        unidades.pop(id_campeao, None)
    else:
        unidades[id_campeao] = min(estrelas, 3)
    # a correção à mão vale também para as cópias contadas pela leitura da tela
    st.session_state.copias[id_campeao] = acompanhamento.COPIAS_POR_ESTRELA.get(unidades.get(id_campeao, 0), 0)


def clicar_componente(id_componente):
    componentes = st.session_state.componentes
    componentes[id_componente] = max(componentes[id_componente] + (-1 if removendo() else 1), 0)


def limpar_tudo():
    st.session_state.unidades = {}
    st.session_state.componentes = Counter()
    st.session_state.copias = {}
    st.session_state.acompanhamento = acompanhamento.Acompanhamento()
    st.session_state.compras_recentes = []


# ---------------------------------------------------------------- leitura da tela do jogo

@st.fragment(run_every=SEGUNDOS_ENTRE_LEITURAS)
def leitura_da_tela(catalogo):
    """Roda sozinha a cada poucos segundos. Se algo mudou no jogo, atualiza a página toda."""
    if not st.session_state.get("lendo"):
        return
    try:
        leitura = carregar_leitor().ler(capturar_tela())
    except Exception as erro:  # ex.: tela bloqueada
        st.caption(f"⚠️ Não consegui capturar a tela: {erro}")
        return
    if not (leitura.nivel or leitura.ouro is not None or any(leitura.loja) or leitura.tracos):
        st.caption("⏸️ Não achei o TFT na tela (o jogo precisa estar em tela cheia ou sem bordas).")
        return

    compras = st.session_state.acompanhamento.detectar_compras(leitura)
    acompanhamento.aplicar_compras(st.session_state.unidades, st.session_state.copias, compras)
    if compras:
        nomes = [compra.campeao.nome for compra in compras]
        st.session_state.compras_recentes = (nomes + st.session_state.compras_recentes)[:6]

    anterior = st.session_state.leitura
    mudou = bool(compras) or anterior is None or (
        (leitura.nivel, leitura.ouro, leitura.loja, leitura.itens, leitura.tracos)
        != (anterior.nivel, anterior.ouro, anterior.loja, anterior.itens, anterior.tracos)
    )
    st.session_state.leitura = leitura
    estado_compartilhado.renovar()
    if mudou:
        componentes, emblemas = acompanhamento.componentes_e_emblemas(leitura.itens, catalogo)
        st.session_state.componentes = Counter(componentes)
        st.session_state.emblemas_lidos = emblemas
        if leitura.nivel and leitura.nivel != st.session_state.nivel:
            st.session_state.nivel_lido = leitura.nivel
        st.rerun(scope="app")
    st.caption(f"🟢 Lendo a tela a cada {SEGUNDOS_ENTRE_LEITURAS} s")


def resumo_da_leitura(catalogo):
    leitura = st.session_state.leitura
    if not (st.session_state.get("lendo") and leitura):
        return
    partes = []
    if leitura.nivel:
        partes.append(f"Nível **{leitura.nivel}**")
    if leitura.ouro is not None:
        partes.append(f"**{leitura.ouro}** de ouro")
    if partes:
        st.markdown(" · ".join(partes))
    if st.session_state.compras_recentes:
        st.caption("🛍️ Compras detectadas: " + ", ".join(st.session_state.compras_recentes))
    if leitura.tracos:
        no_jogo = ", ".join(f"{catalogo.tracos[t].nome} {q}" for t, q in leitura.tracos.items())
        st.caption(f"Traços no seu tabuleiro (lidos do jogo): {no_jogo}")


# ---------------------------------------------------------------- coluna da esquerda: seu jogo

def coluna_seu_jogo(catalogo):
    st.subheader("🎮 Seu jogo")
    st.toggle(
        "📷 Ler a tela do jogo", key="lendo",
        help="Lê nível, ouro, loja, componentes e emblemas sozinho. Os campeões entram quando você compra "
             "na loja; venda e carrossel você corrige clicando nos retratos.",
    )
    st.toggle(
        "🖥️ Overlay no jogo", key="overlay", on_change=ligar_ou_desligar_overlay,
        help="Mostra a primeira comp da lista e marca na loja o que comprar, por cima do jogo. "
             "O TFT precisa estar em 'Tela cheia sem bordas'. Não mexe no jogo: é uma janela por cima.",
    )
    leitura_da_tela(catalogo)
    resumo_da_leitura(catalogo)

    a, b, c = st.columns([1, 2, 1], vertical_alignment="bottom")
    nivel = a.number_input("Nível", 1, 10, key="nivel")
    b.segmented_control("Clique nos retratos para", [ADICIONAR, REMOVER], default=ADICIONAR, key="modo")
    c.button("Limpar", on_click=limpar_tudo, use_container_width=True)

    st.caption("Cada clique soma uma estrela (até 3★). Use ➖ Remover para tirar.")
    unidades = st.session_state.unidades
    for custo in range(1, 6):
        do_custo = sorted((x for x in catalogo.campeoes.values() if x.custo == custo), key=lambda x: x.nome)
        st.markdown(f'<div class="custo-titulo">{"🪙" * custo}  custo {custo}</div>', unsafe_allow_html=True)
        with st.container(horizontal=True, gap="small"):
            for campeao in do_custo:
                estrelas = unidades.get(campeao.id, 0)
                st.button(
                    campeao.nome,
                    key=f"campeao_{campeao.id}_{'tem' if estrelas else 'nao'}_e{estrelas}",
                    help=campeao.nome,
                    on_click=clicar_campeao, args=(campeao.id,),
                )

    st.markdown("**Componentes**")
    componentes = st.session_state.componentes
    with st.container(horizontal=True, gap="small"):
        for componente in catalogo.componentes():
            quantidade = componentes[componente.id]
            st.button(
                str(quantidade) if quantidade else BRANCO,
                key=f"componente_{componente.id}_{'tem' if quantidade else 'nao'}",
                help=componente.nome,
                on_click=clicar_componente, args=(componente.id,),
            )

    todos = sorted(catalogo.campeoes.values(), key=lambda x: (x.custo, x.nome))
    emblemas_disponiveis = sorted(
        (i for i in catalogo.itens.values() if i.tipo == "Emblema" and i.traco_id), key=lambda i: i.nome
    )
    emblemas = st.multiselect(
        "Emblemas que você tem", emblemas_disponiveis, format_func=lambda i: i.nome, placeholder="Nenhum"
    )
    fixos = st.multiselect(
        "Quero jogar com (obrigatórios)", todos, format_func=lambda x: f"{x.nome} ({x.custo})", placeholder="Nenhum"
    )

    situacao = montador.Situacao(
        nivel=nivel,
        unidades=dict(unidades),
        emblemas=[e.traco_id for e in emblemas] + st.session_state.emblemas_lidos,
        fixos=[x.id for x in fixos],
    )
    painel_de_dados()
    return situacao, Counter({k: v for k, v in componentes.items() if v})


def painel_de_dados():
    with st.expander("⚙️ Dados e chave da Riot"):
        if st.button("🔄 Atualizar dados do jogo (datatft + nomes em português)"):
            with st.status("Baixando...", expanded=True) as status:
                atualizar.atualizar_dados_de_jogo(progresso=status.write)
            st.cache_resource.clear()
            st.rerun()

        st.markdown(
            "**Chave da Riot** (para as comps meta): entre em **developer.riotgames.com**, faça login e copie a "
            "*Development API Key* (começa com `RGAPI-`). Ela vence a cada 24h."
        )
        nova = st.text_input("Chave da Riot", type="password", placeholder="RGAPI-...")
        if st.button("Salvar chave") and nova.strip():
            riot.salvar_chave(nova)
            st.success("Chave salva no arquivo .env.")
        if riot.ler_chave() and st.button("Baixar partidas do alto elo do BR (3 a 5 minutos)"):
            with st.status("Baixando partidas...", expanded=True) as status:
                try:
                    atualizar.atualizar_meta(progresso=status.write)
                    status.update(label="Partidas atualizadas!", state="complete")
                except riot.ErroRiot as erro:
                    status.update(label=str(erro), state="error")
        st.caption(f"{total_de_partidas()} partidas no banco.")


# ---------------------------------------------------------------- coluna da direita: comps

def coluna_comps(situacao, catalogo, componentes):
    chave = (situacao.nivel, tuple(sorted(situacao.unidades.items())), tuple(situacao.emblemas), tuple(situacao.fixos))
    a, b = st.columns([3, 1], vertical_alignment="bottom")
    fonte = a.pills("Mostrar", FONTES, default="Todas", key="fonte") or "Todas"
    tamanho = b.number_input("Tamanho do time", 1, 12, max(situacao.nivel, len(situacao.fixos), 1))

    comps = []
    if fonte in ("Todas", "Para você"):
        with st.spinner("Montando comps..."):
            comps += comps_do_algoritmo(catalogo, chave, tamanho)
    if fonte in ("Todas", "Meta"):
        da_meta, resumo = comps_da_meta(catalogo, chave, total_de_partidas())
        # as mais perto do que você tem primeiro; empate decide pela colocação média ajustada
        da_meta = sorted(da_meta, key=lambda c: (-c.porcentagem_que_tem, c.estatisticas["media_ajustada"]))
        comps += da_meta[:5 if fonte == "Todas" else 15]
        if fonte == "Meta":
            st.caption(f"{resumo['partidas']} partidas de Challenger/Grão-Mestre do BR · "
                       "ordem: mais perto do que você tem, depois melhor colocação média")
    if fonte in ("Todas", "Minhas"):
        minhas, desconhecidos = manuais.avaliar_todas(situacao, catalogo)
        comps += minhas
        if desconhecidos:
            st.warning("Campeões não encontrados no set atual: " + ", ".join(desconhecidos))

    leitura = st.session_state.leitura
    selos = []
    if st.session_state.get("lendo") and leitura and any(leitura.loja):
        selos = estado_compartilhado.selos_da_loja(leitura.loja, comps[:3], situacao)
        st.html(html_da_loja(leitura.loja, selos))
    estado_compartilhado.salvar(
        estado_compartilhado.montar(comps[0] if comps else None, situacao, selos, catalogo, componentes)
    )

    if not comps:
        st.info("Nada para mostrar aqui ainda.")
    for comp in comps:
        st.html(html_da_comp(comp, situacao, catalogo, componentes))


# ---------------------------------------------------------------- abas de ferramentas

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
    nome_de = lambda id_item: catalogo.itens[id_item].nome if id_item in catalogo.itens else ""
    st.dataframe(
        pd.DataFrame(
            [{"Item": i.nome, "Tipo": i.tipo, "Componente 1": nome_de(i.componentes[0]), "Componente 2": nome_de(i.componentes[1])}
             for i in sorted(catalogo.receitas(), key=lambda i: (i.tipo, i.nome))]
        ),
        hide_index=True, width="stretch",
    )


def aba_loja(situacao, catalogo):
    st.markdown(f"**Chance de ver cada campeão numa loja no nível {situacao.nivel}**")
    linhas = []
    for campeao in sorted(catalogo.campeoes.values(), key=lambda c: (c.custo, c.nome)):
        copias = montador.copias_que_voce_tem(campeao, situacao)
        chance = chance_na_loja(campeao, situacao.nivel, catalogo, copias_suas=copias)
        linhas.append({
            "Campeão": campeao.nome, "Custo": campeao.custo, "Você tem (cópias)": copias,
            "Chance por loja (%)": round(chance.chance_por_loja * 100, 1),
            "Rolls esperados": None if chance.chance_por_loja == 0 else round(chance.rolls_esperados, 1),
        })
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")

    st.markdown("**Chance de cada custo por nível (%)**")
    tabela = pd.DataFrame(catalogo.chances_loja).T.sort_index() * 100
    tabela.columns = [f"Custo {c}" for c in tabela.columns]
    tabela.index.name = "Nível"
    st.dataframe(tabela.round(0), width="stretch")


def aba_cadastro(catalogo):
    nome = st.text_input("Nome da comp")
    todos = sorted(catalogo.campeoes.values(), key=lambda c: (c.custo, c.nome))
    escolhidos = st.multiselect(
        "Campeões", todos, format_func=lambda c: f"{c.nome} ({c.custo})", key="nova_comp", placeholder="Escolha os campeões"
    )
    notas = st.text_area("Notas (opcional)")
    if st.button("Salvar comp") and nome and escolhidos:
        cadastro = manuais.ler()
        cadastro.append({"nome": nome, "campeoes": [c.nome for c in escolhidos], "notas": notas})
        manuais.salvar(cadastro)
        st.success("Comp salva em minhas_comps.json.")

    cadastradas = manuais.ler()
    if cadastradas:
        st.markdown("**Cadastradas**")
        for posicao, cadastro in enumerate(cadastradas):
            a, b = st.columns([5, 1])
            a.markdown(f"**{cadastro.get('nome')}** — {', '.join(cadastro.get('campeoes', []))}")
            if b.button("Apagar", key=f"apagar_{posicao}"):
                manuais.salvar([c for i, c in enumerate(cadastradas) if i != posicao])
                st.rerun()


def aba_banco():
    conexao = banco.conectar()
    sets = [linha[0] for linha in conexao.execute("SELECT DISTINCT set_numero || ' / ' || idioma FROM metadados ORDER BY 1 DESC")]
    tabelas = ["campeoes", "tracos", "traco_niveis", "itens", "augments", "charms", "economia_loja", "economia_xp", "pool", "nomes_locais"]
    a, b, c = st.columns(3)
    escolha_set = a.selectbox("Set / idioma", sets)
    tabela = b.selectbox("Tabela", tabelas)
    busca = c.text_input("Filtrar (qualquer coluna)")
    numero_set, idioma = escolha_set.split(" / ")
    if tabela == "nomes_locais":
        dados = pd.read_sql("SELECT * FROM nomes_locais WHERE set_numero=?", conexao, params=(numero_set,))
    else:
        dados = pd.read_sql(f"SELECT * FROM {tabela} WHERE set_numero=? AND idioma=?", conexao, params=(numero_set, idioma))
    conexao.close()
    dados = dados.drop(columns=["set_numero", "idioma"])
    if busca:
        dados = dados[dados.astype(str).apply(lambda col: col.str.contains(busca, case=False)).any(axis=1)]
    st.caption(f"{len(dados)} linhas")
    st.dataframe(dados, hide_index=True, width="stretch")


# ---------------------------------------------------------------- página

st.html(estilo.CSS_GERAL)

if banco_vazio():
    st.warning("O banco ainda está vazio.")
    if st.button("Baixar dados do jogo"):
        with st.status("Baixando...", expanded=True) as status:
            atualizar.atualizar_dados_de_jogo(progresso=status.write)
        st.cache_resource.clear()
        st.rerun()
    st.stop()

catalogo = carregar_catalogo()
st.html(estilo.css_dos_botoes(catalogo))
iniciar_estado()

esquerda, direita = st.columns([2, 3], gap="large")
with esquerda:
    situacao, componentes = coluna_seu_jogo(catalogo)
with direita:
    st.subheader("🧩 Comps")
    coluna_comps(situacao, catalogo, componentes)
    st.divider()
    abas = st.tabs(["🗡️ Itens", "🎲 Loja", "📌 Cadastrar minhas comps", "📚 Banco de dados"])
    with abas[0]:
        aba_itens(catalogo, componentes)
    with abas[1]:
        aba_loja(situacao, catalogo)
    with abas[2]:
        aba_cadastro(catalogo)
    with abas[3]:
        aba_banco()
