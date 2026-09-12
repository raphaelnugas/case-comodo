# Decisões técnicas

Este documento justifica as escolhas de cada parte do case. O README.md tem a visão
geral e o passo a passo de execução — aqui está o "por quê".

---

## Parte 1 — Coleta GitHub

**Formato de saída: CSV.** JSONL seria igualmente válido, mas o consumidor final
("relatório que alguém abre às 9h") é tabular por natureza — estrelas, forks, datas —
e CSV abre direto em Excel/Sheets sem transformação, o que importa para quem vai
olhar isso fora de um contexto técnico.

**Autenticação via variável de ambiente, nunca argumento de CLI.** Argumentos de linha
de comando ficam visíveis em `ps aux`, em histórico de shell e em logs de processo.
Variável de ambiente lida só pelo processo é o mínimo razoável sem envolver um
gerenciador de segredos dedicado (que seria overengineering pra este escopo).

**Lock file em vez de outra estratégia de concorrência.** O cenário descrito é um
cron diário às 6h rodando sem ninguém olhando. Um lock file simples
(criar/checar/remover um arquivo com PID e timestamp) resolve o caso real — "o cron
disparou de novo antes do anterior terminar" — sem precisar de um scheduler externo
ou lock distribuído, que seriam desproporcionais ao problema.

**Validação antes/depois via `public_repos` da própria organização.** A API do GitHub
expõe esse número em `/orgs/{org}`. Comparar contra o total efetivamente paginado é
a validação mais direta disponível sem depender de uma segunda fonte. Quando os
números não batem, o resultado não é descartado — é marcado como
`sucesso_com_divergencia` e o motivo mais provável (repos criados/removidos durante a
coleta, específicos de visibilidade) fica registrado no status.

**Escrita atômica do CSV.** O script escreve em `.csv.tmp` e só substitui o arquivo
final com `Path.replace()` se a coleta terminar sem erro. Isso significa que uma
coleta que falha no meio (como aconteceu de fato durante o desenvolvimento — ver
abaixo) nunca deixa o CSV consumido pelo relatório em um estado parcial/corrompido:
o React continua mostrando os dados da última coleta bem-sucedida, e o arquivo de
status é o único lugar que reporta a falha do dia.

**Rate limit sem token: um caso real, não hipotético.** Rodei o coletor sem
`GITHUB_TOKEN` (não temos um configurado no ambiente de desenvolvimento) contra a
organização `apache` (3.171 repositórios públicos) duas vezes seguidas — a segunda
excedeu o limite de 60 req/hora não-autenticado e retornou 403. O script tratou isso
exatamente como projetado: `status: "erro"`, mensagem clara, CSV anterior preservado
intacto. Isso valida o requisito "precisa ficar claro... se algo deu errado" com um
caso real, não fabricado. Em produção (cron diário), usar `GITHUB_TOKEN` (5.000
req/hora) evita esse cenário quase por completo.

**"Erro" na interface é reservado para a coleta agendada, não para qualquer
tentativa.** A escrita atômica garante que a tabela exibida é sempre a da última
coleta bem-sucedida — então um `status: "erro"` na última tentativa não significa
"os dados na tela estão errados", significa "não consegui atualizar agora". Tratar
os dois casos com o mesmo vermelho alarmante confundiria "dado desatualizado" com
"dado incorreto", que são coisas bem diferentes para quem só quer olhar o relatório
às 9h. Por isso o status carrega também `origem_execucao` (derivado de
`GITHUB_EVENT_NAME`, que o GitHub Actions preenche sozinho: `"schedule"` para o cron,
qualquer outra coisa para disparo manual/local): a interface só usa o vermelho de
"erro" quando quem falhou foi a execução agendada das 6h — o alarme de produção de
verdade. Uma falha manual (um teste local sem token, por exemplo) aparece como
"Desatualizado" em amarelo, com o motivo técnico disponível mas sem alarme.

---

## Parte 2 — Análise comercial

**SQLite em vez de DuckDB/Postgres.** Os três CSVs somados têm menos de 900 linhas.
SQLite é embutido no Python (`sqlite3`, zero dependência extra), suporta janelas
(`RANK() OVER`) e CTEs, e o banco gerado é um arquivo único e descartável — recriar
do zero a cada execução (`build_database.py` apaga e recria as tabelas) é mais simples
e mais seguro contra dado obsoleto do que fazer migração incremental.

**Nomes de coluna preservados 1:1 com os CSVs originais.** Isso é o que permite ao
fluxo "novo CSV entra → rodar os scripts de novo → números atualizam" funcionar sem
tocar em código, contanto que o novo arquivo mantenha o mesmo cabeçalho.

**Por que não uso `pandas`.** Com essa quantidade de dados, `pandas` só adicionaria
uma dependência pesada sem ganho de legibilidade sobre `csv` + `sqlite3` da biblioteca
padrão. Numa base maior, migraria para DuckDB (SQL igual, zero servidor) antes de ir
para pandas puro.

**Agregar antes de juntar — a decisão que evita duplicação.** `investimento_midia.csv`
tem uma linha por dia por campanha (352 linhas). Se eu juntasse essa tabela direto
com `leads` ou `vendas` por `campanha_id` sem agregar antes, cada linha de lead seria
multiplicada pelo número de linhas de mídia daquela campanha (produto cartesiano),
inflando qualquer `SUM(gasto)` calculado depois do join. As três queries em `sql/`
agregam cada fato (`leads_agg`, `vendas_agg`, `midia_agg`) em CTEs separados e só
depois fazem `LEFT JOIN` dos agregados — nunca das linhas brutas. Os testes em
`tests/test_parte2_analise.py` verificam isso explicitamente (a soma de receita por
campanha bate com `SUM(valor_contrato)` direto na tabela `vendas`).

**Ausência de investimento ≠ investimento zero.** `cmp_999` tem 4 leads mas nenhuma
linha em `investimento_midia.csv`. Um `COALESCE(gasto_total, 0)` teria feito o custo
por lead dessa campanha parecer "grátis" — o que é um erro de dado, não um resultado.
A query deixa `gasto_total`, `custo_por_lead` e `custo_por_venda` como `NULL` nesse
caso, e o React exibe explicitamente "sem dado" em vez de "R$ 0,00".

**Leads e vendas sem campanha são preservados, não descartados.** 6 leads (e 1 venda
de R$ 44.909,27) não têm `campanha_id` preenchido. Aparecem como
"(sem campanha atribuída)" em todas as três análises — descartar essas linhas seria
esconder receita real do relatório usado pra decisão de verba.

**Funil: a limitação mais importante do case.** `leads.csv` só tem `etapa_atual` — a
etapa em que o lead está *agora*, não o histórico de transições. Isso significa que,
para um lead marcado como `perdido`, não há como saber em qual etapa ele estava
quando foi perdido. Duas opções: (a) inventar uma suposição sobre em qual etapa cada
lead perdido "provavelmente" parou, ou (b) ser explícito sobre o que os dados não
permitem responder. Escolhi (b): o funil degrau-a-degrau (`sql/02_funil_por_campanha.sql`)
usa só os leads que não estão em `perdido`, assumindo progressão monotônica
(a etapa atual é a mais avançada que o lead alcançou — razoável para um funil linear,
mas é uma suposição declarada, não um fato do dado). `perdido` é reportado à parte,
como métrica agregada por campanha (`total_perdidos`, `pct_perdidos_do_total`), nunca
encaixado num degrau específico do funil.

**"Cliente de maior valor" = ticket médio, não receita total.** Receita total
recompensa volume; ticket médio isola o valor médio por venda, que é a leitura mais
direta de "que tipo de campanha traz o cliente que fecha o contrato mais caro,
independente de quantas vendas ela trouxe". As duas métricas ficam lado a lado na
seção 3 do React para não esconder o trade-off. A campanha "(sem campanha atribuída)"
é excluída desse ranking especificamente — 1 venda isolada não é uma campanha, e
misturá-la no ranking colocaria uma amostra de N=1 no topo por acaso (o que
efetivamente aconteceu na primeira versão do cálculo, antes dessa correção).

**Cobertura de datas desalinhada entre os três arquivos.** Investimento em mídia
cobre maio–junho/2026; leads existem até 02/07/2026; vendas fecham até 18/09/2026
(inclusive depois da "data atual" do ambiente, 12/09/2026 — indicativo de dado
sintético com fechamentos "no futuro" em vez de um limite real). Isso significa que
leads mais recentes tiveram menos tempo para converter em venda, o que pode
subestimar o desempenho de campanhas com leads mais novos no cálculo de custo por
venda. Está documentado como limitação explícita no `analise_metadata.json` e exibido
na interface, não escondido.

---

## Parte 3 — Classificação de pré-vendas

**Por que Gemini com fallback de modelo.** O pedido original especificava um modelo
que não existe no catálogo público no momento em que este código foi escrito. Em vez
de travar nisso, o cliente (`gemini_client.py`) tenta o modelo configurado em
`GEMINI_MODEL` e, se falhar (nome inválido, indisponibilidade, erro de rede), cai
para a lista em `GEMINI_FALLBACK_MODELS`, nessa ordem — com retry e backoff
exponencial dentro de cada modelo antes de desistir dele. Isso é literalmente o
requisito do case ("o script precisa lidar com falha na chamada do modelo") aplicado
também à hipótese de o próprio nome do modelo estar errado.

**Prompt em arquivo separado (`prompts/prompt_classificacao_prevendas.txt`).** Não é só
o requisito explícito — também é o que torna possível ajustar critério de
classificação sem tocar em código Python, e versionar essa mudança no git com um
diff legível.

**Validação em duas camadas.** `validators.py` primeiro confere o schema (campos
obrigatórios, tipos, `classificacao` num dos 4 valores válidos) e só depois confere
se cada evidência (`numero_mensagem` + `trecho`) realmente existe na conversa — o
trecho citado é comparado (normalizado, sem acento/case) contra o texto real daquela
mensagem numerada. Uma citação que não bate — nem por paráfrase (checada por
sobreposição de palavras) — é tratada como alucinação e rejeita a resposta. Isso é o
que garante que "evidência com número da mensagem" seja uma evidência de verdade, não
um número que o modelo inventou.

**Falha técnica nunca vira "frio".** Isso é tratado em dois pontos: (1) se todas as
tentativas de todos os modelos falharem (`GeminiIndisponivel`), ou (2) se o JSON
retornado não passar na validação mesmo depois de uma rodada de correção — em ambos
os casos o registro final tem `status: "falha_tecnica"`, `classificacao: null`, e
`revisao_humana_recomendada: true`. Um "frio" no output significa sempre "o modelo
classificou como frio", nunca "algo deu errado e o padrão calhou de ser frio".

**Checkpoint por conversa, não por lote.** Cada conversa processada grava seu próprio
arquivo em `data/output/checkpoints/{id}.json` imediatamente. Rodar o script de novo
pula quem já foi classificado com sucesso — importante pensando em escala (a pergunta
do case sobre 4.000 conversas): reprocessar do zero a cada nova leva de dados
desperdiçaria chamadas de API pagas em conversas que já deram certo.

A resposta para "como eu saberia, com 4.000 conversas e três meses depois, se a
classificação está funcionando" está no README (pergunta explícita do case) — aqui
fica só o suporte de código para isso:
`src/parte3_prevendas/avaliar_qualidade.py` já implementa o cruzamento entre uma
amostra rotulada por humano e a classificação do modelo (concordância geral, por
classe, e matriz de confusão), pronto para ser usado quando essa amostra existir.

---

## Sobre o uso de IA neste case

Usei IA (Claude, via Claude Code) para:
- Gerar a estrutura inicial dos três scripts Python e das queries SQL a partir das
  decisões descritas acima (que foram minhas — critério de classificação, tratamento
  de NULL vs. zero, o que preservar/excluir em cada agregação).
- Redigir os componentes React a partir de uma especificação visual e funcional que
  eu detalhei (paleta de cores, as 3 páginas, o que cada seção deveria mostrar).
- Escrever esta documentação.

O que revisei/validei manualmente depois:
- Rodei o coletor da Parte 1 de verdade contra a API pública do GitHub (não é
  simulação) e conferi o resultado — inclusive o caso de rate limit real, que não foi
  fabricado, aconteceu durante o desenvolvimento.
- Rodei as três queries SQL contra o banco gerado a partir dos CSVs reais do case e
  conferi manualmente os números de 2-3 campanhas na mão antes de aceitar os
  resultados (ex.: `cmp_999` e leads sem campanha aparecendo com custo `NULL`, não 0).
- Escrevi os testes (`tests/`) para travar as invariantes que mais importavam para a
  confiabilidade dos números: nenhuma duplicação por join, nenhum "zero" fantasma,
  nenhuma evidência de IA aceita sem bater com o texto real da conversa.
- A classificação da Parte 3 só é aceita como resultado real quando rodada com uma
  `GEMINI_API_KEY` de verdade — não há números "de exemplo" inventados no lugar de
  uma execução real do modelo. O resultado no README (15/15 classificadas, 0 falhas
  técnicas) é dessa execução real contra `gemini-3.6-flash`, não uma simulação.
