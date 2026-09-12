# Roteiro de apresentação

Escrito em primeira pessoa, como guia para a conversa de 45 minutos. Não é um roteiro
decorado — é a ordem em que eu tomei as decisões, então é também a ordem mais natural
de explicar.

---

## 1. Por onde comecei: lendo o case antes de escrever código

Antes de tocar em código, li o `CASE_TECNICO.md` inteiro e separei o que era
**requisito** do que era **critério de avaliação** — porque o peso dado a cada coisa
("Alto: confiabilidade dos números", "Baixo: elegância do código") deveria decidir
onde eu gastava tempo. Isso me levou a uma decisão logo de cara: cortar qualquer
ambição de arquitetura sofisticada e investir o tempo em três lugares — os dados
estarem certos, os erros serem visíveis, e eu conseguir explicar cada número por
escrito.

## 2. Parte 1 — comecei pela coleta porque é a peça mais isolada

Escolhi a organização `apache` (tem mais de 3.100 repositórios públicos, bem acima do
mínimo de 200 pedido). Escrevi o script pensando no cenário descrito no case — "roda
sozinho às 6h, sem ninguém olhando" — não como um script de teste. Isso significa:
paginação até o fim de verdade (32 páginas na primeira execução), retry com backoff,
lock contra execução duplicada, e principalmente: **um jeito de saber depois se deu
certo sem precisar reler logs manualmente** (o `github_collection_status.json`).

Um detalhe que uso na conversa: rodei o coletor duas vezes durante o desenvolvimento
sem `GITHUB_TOKEN`, e a segunda vez estourou o limite de 60 requisições/hora da API
não-autenticada. Isso não foi um teste que eu montei — foi o script se comportando
exatamente como eu queria diante de uma falha real: gravou `status: "erro"` com a
mensagem exata da exceção, e manteve intacto o CSV da coleta anterior (porque a
escrita é atômica — só troca o arquivo final se tudo terminar sem erro). É o tipo de
coisa que só se vê rodando de verdade, não simulando.

## 3. Parte 2 — a parte que mais me fez parar para pensar antes de escrever SQL

Antes de escrever qualquer query, abri os três CSVs e fui atrás de onde os dados
quebravam a expectativa ingênua de "todo lead tem campanha, toda campanha tem
investimento":

- 6 leads sem `campanha_id` (um deles gerou uma venda de quase R$ 45 mil — não dava
  pra simplesmente descartar);
- uma campanha (`cmp_999`) com 4 leads mas nenhum registro de investimento;
- o período de mídia (maio–junho) mais curto que o período de leads (até julho) e
  bem mais curto que o de vendas (até setembro, inclusive com fechamentos "no
  futuro" em relação à data do ambiente — claramente um artefato do dado sintético).

Essas três coisas viraram decisões de design das queries antes de eu escrever a
primeira linha de SQL: agregar cada fato separadamente antes de qualquer join (pra
não duplicar valores), nunca converter "sem investimento" em zero, e nunca descartar
uma linha só porque falta uma chave de campanha.

O resultado que eu destacaria: `PESQUISA_MOVEIS_PLANEJADOS_MARCA` (busca paga por
marca no Google) tem o melhor custo por venda (R$ 283,01) *e* o maior ticket médio
entre campanhas reais (R$ 39.784,90) — ou seja, não é só a mais barata, é a que traz
o cliente mais valioso. Isso é o tipo de leitura que uma tabela de custo por lead
sozinha não mostra, e é exatamente o que a pergunta do case pede (decisão de
realocação de verba).

## 4. Parte 3 — onde passei mais tempo pensando em "o que pode dar errado" antes de "o que a IA deveria responder"

Fiz o caminho inverso do óbvio: escrevi o schema de validação
(`validators.py`) antes de escrever o prompt final. Motivo: se eu não decidisse
primeiro o que conta como uma resposta inválida (evidência que não bate com o texto
real da mensagem, classificação fora do enum, campo faltando), eu ia acabar
ajustando o prompt reativamente toda vez que o modelo "quase" acertasse o formato.

A parte que eu mais defendo em conversa: uma "evidência" só é aceita se o trecho
citado realmente aparece (ou é uma paráfrase muito próxima, com aviso) na mensagem
numerada que o modelo apontou. Isso pega alucinação de citação, que é um jeito comum
de um LLM parecer mais confiável do que é.

E a decisão que eu diria que mais reflete como penso sobre sistemas em produção:
falha técnica (API fora do ar, JSON que não valida nem depois de uma correção) nunca
vira "frio" por omissão. Um "frio" tem que significar sempre a mesma coisa: o modelo
avaliou e concluiu baixo interesse. Se eu deixasse falha técnica cair no mesmo balde
que "frio" por conveniência de schema, eu estaria escondendo problema de
infraestrutura dentro de um dado de negócio — e ninguém ia notar até alguém perguntar
por que tantos leads "frios" apareceram numa hora em que a API estava instável.

## 5. O que eu decidi deixar de fora, e por quê

- **Não implementei um dashboard de custo de API do Gemini.** Seria natural pra
  produção, mas não muda nenhuma decisão que o case pede pra eu justificar agora.
- **Não fiz deploy do React** — o case é explícito que deploy não é avaliado, e o
  front-end aqui existe por escolha minha (organização e apresentação), não porque
  foi pedido. Rodo local (`npm run dev`) para esta conversa.
- **Não tratei o funil como se tivesse histórico de transição de etapa** — porque não
  tem. Preferi ser explícito sobre o que dá pra inferir com segurança (progressão
  monotônica pra quem não foi perdido) do que fingir uma granularidade que os dados
  não sustentam.

## 6. Se a pergunta for "e daqui a três meses, com 4.000 conversas?"

Resposta curta, que eu detalho em `DECISOES_TECNICAS.md`: amostra humana semanal
(~5%, viável em volume) comparada contra a classificação do modelo via
`avaliar_qualidade.py` (já no código, não é só uma promessa em texto) — com atenção
especial para confusão quente↔frio, que é o erro caro. Cruzamento mensal com o funil
real da Parte 2 pra pegar deriva sem depender só de revisão humana. Gatilho de
alerta: concordância abaixo de ~80%, ou qualquer caso quente↔frio na amostra semanal.

## 7. Se sobrar tempo / se perguntarem "o que você faria diferente com mais uma semana"

Eu investigaria se dá pra recuperar sinal de "em qual etapa o lead foi perdido" a
partir de outro sistema de origem (CRM, se existir) em vez de aceitar a limitação do
funil como definitiva. E rodaria a Parte 3 numa amostra bem maior que 15 conversas
antes de confiar no prompt como está — 15 é o suficiente pra validar que o pipeline
funciona ponta a ponta, não pra validar que os critérios de classificação generalizam.
