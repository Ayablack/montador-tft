# Montador de comps — TFT

> **Projeto de estudo.** Um experimento pessoal para praticar análise de dados, algoritmos de busca,
> visão computacional e interfaces em Python, usando como tema o *Teamfight Tactics* (TFT), da Riot Games.
> Não é um produto, não tem fins comerciais e não tem ligação com a Riot Games.

Ferramenta que ajuda a decidir **qual composição montar** numa partida de TFT a partir do que você
já tem (campeões, estrelas, itens, nível e ouro), usando o que os melhores jogadores do servidor
brasileiro fazem nas partidas ranqueadas.

## A ideia

No TFT, a cada rodada você compra campeões numa loja aleatória e tenta formar um time cujos
**traços** (sinergias) se ativem juntos. A decisão difícil é: *com o que eu tenho agora, para qual
time eu devo ir?* — e depois: *quando subo de nível, quando gasto ouro rolando a loja, em quem coloco
os itens?*

O estudo foi tentar responder isso de três jeitos e comparar:

1. **Um algoritmo de busca** que monta times do zero e dá nota para cada um (traços ativados,
   campeões que você já tem, chance de achar os que faltam na loja do seu nível).
2. **Dados de alto elo**: baixar as partidas ranqueadas dos jogadores Challenger e Grão-Mestre do BR
   pela API oficial da Riot e descobrir, sem regra escrita à mão, quais comps colocam melhor,
   quais itens cada campeão usa e qual o plano de jogo de cada comp (reroll, jogar no 8, subir para o 9).
3. **Comps cadastradas à mão**, para comparar com as outras duas.

E, para não precisar marcar tudo à mão durante a partida, **ler a tela do jogo** (OCR e comparação
de imagens) e mostrar as sugestões num **overlay** por cima do jogo.

## O que ele faz

- Sugere comps para o que você tem: algoritmo, comps do alto elo do BR e comps suas.
- Mostra, para cada comp: o que você tem, a chance de achar cada campeão que falta por loja,
  os traços, a build de itens do carry e **como jogar** ("Reroll no nível 6 até Kayle e Warwick 3★",
  "Suba para o 8 em 4-1/4-2"...).
- **Lê a tela do jogo** a cada 2 s: estágio, nível, XP, ouro, as 5 cartas da loja, componentes e
  emblemas do banco e os traços do tabuleiro. Detecta as compras (a carta some e o ouro cai).
- **Dicas na hora certa**: "3-2: o normal é estar no nível 6, faltam 14 de XP (16 de ouro)",
  "Hora do rolldown no 8", "Faltam 2 para 40: segure e ganhe +4 de juros".
- **Overlay**: janela transparente por cima do jogo com a comp alvo, as dicas e uma moldura nas
  cartas da loja que valem a compra.
- Aba **Táticas** com o que os dados mostram: nível final x colocação, campeões e traços mais fortes,
  melhores builds de 3 itens por campeão.

## Como funciona

```
 Community Dragon ─┐                      ┌─ logica/montador.py   busca em feixe (beam search)
 (arquivos do jogo)│                      ├─ logica/taticas.py    estatística das partidas
                   ├─> dados/tft.db ──────┤─ logica/meta.py       agrupa tabuleiros em comps
 API da Riot ──────┘   (SQLite)           ├─ logica/dicas.py      nível, rolagem e juros
 (partidas BR1)                           └─ logica/loja.py       probabilidade da loja
                                                    │
 tela do jogo ── visao/ (OCR + template matching) ──┼──> app.py (Streamlit) ──> overlay.py (Tkinter)
```

**Fontes de dados**

| Dado | De onde vem |
|---|---|
| Campeões, traços, itens, augments (em português) | [Community Dragon](https://www.communitydragon.org/), que extrai os arquivos do cliente do jogo |
| Partidas ranqueadas de alto elo | [API oficial da Riot](https://developer.riotgames.com/) (servidor BR1) |
| Chances da loja, pool, XP, juros | `dados/economia.py`, conferido com guias do Set 18 e com prints do próprio jogo |

A API da Riot só tem partidas, ranking e jogadores; os dados do jogo em si vêm do Community Dragon.

## Coisas que aprendi no caminho

- **Nomes escondidos por hash.** Muitas variáveis nos textos do jogo aparecem como `{a9a813e7}`.
  São hashes FNV-1a do nome em minúsculas (`BonusDamagePercentBase`); calculando o hash dá para
  preencher os valores nos textos dos traços e habilidades (`dados/cdragon.py`).
- **Busca incremental.** A primeira versão do algoritmo recalculava o time inteiro a cada candidato
  e levava 1,9 s por clique. Guardando a contagem de traços em cada time do feixe e somando só o
  ganho do campeão novo, caiu para 0,17 s (`logica/montador.py`).
- **Imagens servidas como arquivo.** Os ícones iam embutidos em base64 em cada atualização da página
  (730 KB por clique). Servindo a pasta `static/` pelo Streamlit, o navegador guarda em cache e
  cada atualização caiu para 60 KB.
- **Média ajustada.** Um campeão com 2 jogos e 2 vitórias não é o melhor do jogo: toda média de
  colocação é puxada para 4,5 com peso de 10 jogos (média bayesiana simples).
- **Viés de sobrevivência.** Os dados mostram que quem termina no nível 9 coloca em média 3,5 e
  quem termina no 8 coloca 4,8 — mas parte disso é porque quem é eliminado cedo nem chega ao 9.
  Os números ajudam, mas não provam causa.
- **Conferir os dados com o jogo.** A primeira fonte de dados (um site de estatísticas do TFT mobile)
  tinha a tabela de chances da loja deslocada em um nível; só apareceu comparando com o que o HUD
  do jogo mostra.
- **Overlay sem mexer no jogo.** Programas como o RivaTuner desenham *dentro* do jogo; isso arrisca
  banimento pelo anti-cheat (Vanguard). Aqui o overlay é uma janela comum do Windows, transparente,
  sempre por cima e que deixa o clique passar — por isso exige o jogo em "tela cheia sem bordas".

## Como rodar

Precisa de **Windows 10/11** (a leitura de tela usa o OCR do Windows e o overlay usa a API do Windows)
e **Python 3.12+**.

```
pip install -r requirements.txt
python atualizar.py          # baixa os dados do set e os ícones
streamlit run app.py         # ou dois cliques em iniciar.bat
```

Para as comps do alto elo, é preciso uma chave da Riot:

1. Entre em **https://developer.riotgames.com** com a sua conta da Riot.
2. Copie a **Development API Key** (começa com `RGAPI-`). Ela vence a cada 24 horas.
3. No app, abra **⚙️ Dados e chave da Riot**, cole a chave e clique em **Baixar partidas**
   (15 a 20 minutos: a chave gratuita permite 100 pedidos a cada 2 minutos).
   Pela linha de comando: `python atualizar.py --meta`.

A chave fica no arquivo `.env`, que não vai para o repositório.

**Leitura da tela e overlay:** jogo em português, 16:9 (calibrado em 2560x1440; outras resoluções
16:9 são convertidas) e em **tela cheia sem bordas**. Ligue **📷 Ler a tela do jogo** e
**🖥️ Overlay no jogo** no app.

## Organização do código

```
dados/        baixar e guardar dados
  cdragon.py    campeões, traços, itens e ícones do Community Dragon
  riot.py       API da Riot (partidas de alto elo)
  economia.py   chances da loja, pool, XP, juros
  banco.py      esquema do SQLite (dados/tft.db)
logica/       as contas (não dependem da tela)
  catalogo.py   carrega o set do banco
  montador.py   algoritmo que sugere comps (os pesos ficam no topo do arquivo)
  taticas.py    estatística das partidas: força, builds, plano de jogo
  meta.py       agrupa os tabuleiros de alto elo em comps
  dicas.py      quando subir de nível, rolar e guardar ouro
  tracos.py, loja.py, itens.py, manuais.py, tradutor.py
visao/        leitura da tela do jogo
  captura.py, regioes.py, ocr.py, leitor.py, acompanhamento.py, estado_compartilhado.py
interface/    HTML/CSS dos cartões e botões
app.py        a tela (Streamlit)
overlay.py    janela por cima do jogo (Tkinter)
atualizar.py  atualiza o banco pela linha de comando
```

## Consultas no banco

Abra `dados/tft.db` no [DB Browser for SQLite](https://sqlitebrowser.org/) ou use a aba **Banco de dados**.

```sql
-- Campeões de cada traço
SELECT t.nome AS traco, group_concat(c.nome, ', ') AS campeoes
FROM campeao_traco ct
JOIN tracos t   ON t.chave = ct.traco
JOIN campeoes c ON c.chave = ct.campeao
GROUP BY t.nome;

-- Colocação média por campeão no alto elo
SELECT json_extract(u.value, '$.id') AS campeao, COUNT(*) AS jogos, ROUND(AVG(p.colocacao), 2) AS media
FROM participacoes p JOIN partidas m USING (match_id), json_each(p.unidades) u
WHERE m.fila = 1100
GROUP BY campeao HAVING jogos >= 30 ORDER BY media;

-- Nível final x colocação
SELECT nivel, COUNT(*) AS jogadores, ROUND(AVG(colocacao), 2) AS media
FROM participacoes GROUP BY nivel ORDER BY nivel;
```

## Limitações

- A API da Riot mostra só o **tabuleiro final** de cada jogador e não traz mais os augments;
  o plano de jogo é deduzido do final da partida (nível, estrelas, itens), não do caminho.
- A tela não mostra o nome dos campeões do tabuleiro: eles são deduzidos pelas compras.
  Venda e carrossel precisam ser corrigidos à mão.
- As regiões da tela foram medidas num monitor QHD com o jogo em português.

## Aviso legal

Montador TFT isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or
anyone officially involved in producing or managing Riot Games properties. Riot Games, and all
associated properties are trademarks or registered trademarks of Riot Games, Inc.

Este projeto não é endossado pela Riot Games. Os ícones e textos do jogo não ficam no repositório:
são baixados do Community Dragon na sua máquina, ao rodar `atualizar.py`.

Código sob a licença [MIT](LICENSE).

## Créditos e licença

Este projeto é baseado no [montador-tft original](https://github.com/joaoploliveira/montador-tft), desenvolvido por [joaoploliveira](https://github.com/joaoploliveira).

Esta versão é mantida por [Ayablack](https://github.com/Ayablack) e poderá incluir modificações e melhorias próprias.

O projeto original é distribuído sob a licença MIT. Consulte o arquivo `LICENSE` para conhecer os termos aplicáveis.

