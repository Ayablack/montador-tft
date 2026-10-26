# Montador de comps — TFT

Ferramenta para montar composições de TFT de acordo com o que você tem no jogo:
campeões (com estrelas), componentes, emblemas e nível.

## Como abrir

Dê dois cliques em **`iniciar.bat`** (ou rode `streamlit run app.py`). O navegador abre sozinho.

A tela tem duas colunas: à esquerda **🎮 Seu jogo** (o que você tem), à direita as comps sugeridas.

- **Retratos**: cada clique soma uma estrela (até 3★); ➖ Remover tira.
- **Mostrar**: Todas · Para você (algoritmo) · Meta (alto elo do BR) · Minhas (`minhas_comps.json`).
- Em cada comp: o que você tem, o que falta com a chance por loja, os traços e os itens do carry
  (🟢 pode montar, 🟡 falta 1 componente, ⚪ faltam 2).
- Abas de baixo: Itens, Loja, Cadastrar minhas comps e Banco de dados.

## Ler a tela do jogo e overlay

- **📷 Ler a tela do jogo**: a cada 2 s o app tira print do monitor do jogo (o maior) e lê nível, ouro,
  loja, componentes e emblemas do banco e os traços do tabuleiro. Os campeões entram quando você compra
  na loja (a carta some e o ouro cai). Venda e carrossel não aparecem: corrija clicando nos retratos.
  Acima das comps aparece a faixa **🛒 Loja agora** com COMPRE / SOBE ★.
- **🖥️ Overlay no jogo**: janela transparente por cima do jogo, que deixa o clique passar. Mostra a primeira
  comp da lista no canto de cima à esquerda e põe moldura nas cartas da loja para comprar.
  Precisa do TFT em **Tela cheia sem bordas**. Não injeta nada no jogo (seguro com o Vanguard).
  Fecha sozinho quando o app fecha.
- Calibrado em 2560x1440 com o jogo em português; outras resoluções 16:9 são convertidas
  (posições em `visao/regioes.py`).

## Comps meta: como pegar a chave da Riot

1. Entre em **https://developer.riotgames.com** e clique em **LOGIN** (é a mesma conta do LoL/TFT).
2. Aceite os termos se ele pedir. Você cai no **Dashboard**.
3. Na parte **DEVELOPMENT API KEY**, clique em **REGENERATE API KEY** (se precisar) e copie a chave
   (começa com `RGAPI-`).
4. No app, aba **🏆 Comps meta** → cole a chave → **Salvar chave** → **Baixar partidas**.

A chave de desenvolvimento vence a cada 24 horas. Quando aparecer "chave inválida ou expirada",
repita o passo 3 e cole a nova. As partidas já baixadas continuam no banco; cada atualização só
baixa as novas. Para não precisar renovar, dá para pedir uma *Personal API Key* no próprio site
(botão **REGISTER PRODUCT** → *Personal API Key*). A aprovação leva alguns dias.

A chave fica no arquivo `.env`, só no seu computador.

## Atualizar os dados

- Dados do jogo (campeões, traços, itens): botão **🔄 Atualizar dados do jogo** no app, ou `python atualizar.py`
- Partidas do alto elo: botão na aba Comps meta, ou `python atualizar.py --meta`

## De onde vêm os dados

- **Dados do jogo**: [datatft.com/database](https://www.datatft.com/database). O site é do 金铲铲
  (TFT mobile chinês). O app usa a versão em inglês do Set 18, que segue os valores do TFT da Riot.
  O banco também guarda os sets antigos em chinês.
- **Partidas**: API oficial da Riot (servidor BR1).

## Organização do código

```
dados/        baixar e guardar dados
  coleta.py     baixa os JSONs do datatft
  banco.py      esquema do SQLite e importação (datatft.db)
  riot.py       API da Riot (partidas de alto elo)
logica/       as contas (não dependem da tela)
  catalogo.py   carrega um set do banco
  tracos.py     traços ativos e breakpoints
  montador.py   algoritmo que sugere comps (os pesos ficam no topo do arquivo)
  loja.py       chance de achar campeões
  itens.py      receitas e itens recomendados
  meta.py       agrupa as partidas da Riot em comps
  manuais.py    lê/salva minhas_comps.json
visao/        leitura da tela do jogo
  captura.py    print do monitor
  regioes.py    onde fica cada parte do HUD
  ocr.py        OCR do Windows (pt-BR)
  leitor.py     lê nível, ouro, loja, traços e itens
  acompanhamento.py  deduz as compras entre uma leitura e outra
  estado_compartilhado.py  o que o app manda para o overlay
interface/    HTML/CSS dos cartões e botões
app.py        a tela (Streamlit)
overlay.py    janela por cima do jogo
atualizar.py  atualiza o banco pela linha de comando
```

Para mudar o jeito como o algoritmo escolhe as comps, ajuste os pesos no topo de `logica/montador.py`
(por exemplo, `BONUS_JA_TEM` faz ele valorizar mais os campeões que você já tem).

## Consultas úteis no banco

Abra `dados/datatft.db` no [DB Browser for SQLite](https://sqlitebrowser.org/) ou use a aba Banco de dados.

```sql
-- Campeões do set 18 com mais vida no 1★
SELECT nome, custo, vida, armadura, resist_magica FROM campeoes
WHERE set_numero='18' AND idioma='en' ORDER BY vida_1 DESC;

-- Campeões de cada traço
SELECT t.nome AS traco, group_concat(c.nome, ', ') AS campeoes
FROM campeao_traco ct
JOIN tracos t   ON t.id = ct.traco_id   AND t.set_numero = ct.set_numero AND t.idioma = ct.idioma
JOIN campeoes c ON c.id = ct.campeao_id AND c.set_numero = ct.set_numero AND c.idioma = ct.idioma
WHERE ct.set_numero='18' AND ct.idioma='en' GROUP BY t.nome;

-- Colocação média por campeão no alto elo (depois de baixar partidas)
SELECT json_extract(u.value, '$.id') AS campeao, COUNT(*) AS jogos, ROUND(AVG(p.colocacao), 2) AS media
FROM participacoes p, json_each(p.unidades) u
GROUP BY campeao HAVING jogos >= 10 ORDER BY media;
```
