# Case técnico — Cômodo Planejados

Solução para o case de Desenvolvedor(a) Python Pleno (`CASE_TECNICO.md`): ingestão via
API, análise SQL sobre dados comerciais, e classificação de conversas de pré-vendas
com LLM. Documentação técnica completa; sem PDF nem slides, como pedido.

Um front-end em React acompanha o projeto **por escolha própria, não porque foi
pedido** — o case é explícito que front-end não é critério de avaliação. Construí-o
para organizar a apresentação dos três resultados numa única tela navegável, com
rastreabilidade de onde cada número vem. Os três entregáveis reais do case (scripts
Python, queries `.sql`, prompt versionado) funcionam de ponta a ponta sem o React.

## Índice

- [Arquitetura e fluxo de dados](#arquitetura-e-fluxo-de-dados)
- [Como rodar do zero](#como-rodar-do-zero)
- [Parte 1 — Coleta GitHub](#parte-1--coleta-github)
- [Parte 2 — Análise comercial](#parte-2--análise-comercial-resultados)
- [Parte 3 — Classificação de pré-vendas](#parte-3--classificação-de-pré-vendas)
- [O que ficou de fora, e por quê](#o-que-ficou-de-fora-e-por-quê)
- [Uso de IA neste case](#uso-de-ia-neste-case)
- [Testes](#testes)
- [Segurança de credenciais](#segurança-de-credenciais)

Decisões técnicas detalhadas: [`DECISOES_TECNICAS.md`](DECISOES_TECNICAS.md).
Como atualizar os dados no futuro: [`docs/FLUXO_DE_DADOS.md`](docs/FLUXO_DE_DADOS.md).
Roteiro para a conversa de 45 min: [`docs/ROTEIRO_APRESENTACAO.md`](docs/ROTEIRO_APRESENTACAO.md).

---

## Arquitetura e fluxo de dados

```
dados/ (originais, intocados)  →  scripts Python  →  SQLite / SQL  →  data/output (CSV/JSON)  →  web/public/data  →  React
```

```
.
├── dados/                        # arquivos originais do case — NUNCA editados
├── src/
│   ├── parte1_github/            # coleta da API do GitHub
│   ├── parte2_analise/           # SQLite + export dos resultados
│   └── parte3_prevendas/         # classificação com Gemini
├── sql/                          # as 3 queries pedidas pelo case, arquivo separado
├── prompts/                      # prompt da Parte 3, versionado, fora do código
├── data/
│   ├── db/                       # SQLite gerado (não versionado — reproduzível)
│   └── output/                   # CSV/JSON gerados (fonte do React)
├── web/                          # front-end React (Vite) — as 3 páginas
├── tests/                        # pytest
└── .github/workflows/            # CI + coleta automática às 6h
```

Ver [`docs/FLUXO_DE_DADOS.md`](docs/FLUXO_DE_DADOS.md) para o passo a passo de como
atualizar quando novos CSVs ou conversas chegarem.

## Como rodar do zero

```bash
python -m venv .venv && source .venv/bin/activate   # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt
cp .env.example .env   # preencha GITHUB_TOKEN (opcional) e GEMINI_API_KEY (obrigatório p/ Parte 3)

# Parte 1
python -m src.parte1_github.collect_repos --org apache

# Parte 2
python -m src.parte2_analise.build_database
python -m src.parte2_analise.export_web

# Parte 3 (requer GEMINI_API_KEY em .env)
python -m src.parte3_prevendas.classify

# Testes
python -m pytest -q

# Front-end (opcional — organização/apresentação, não avaliado pelo case)
npm --prefix web install
npm --prefix web run dev
```

---

## Parte 1 — Coleta GitHub

**Script:** [`src/parte1_github/collect_repos.py`](src/parte1_github/collect_repos.py)

Coleta **todos** os repositórios públicos da organização `apache` (3.171 no momento
da última execução — acima do mínimo de 200 pedido pelo case) via
`GET /orgs/{org}/repos`, paginando até a última página vazia. Para cada repositório:
nome, descrição, linguagem principal, estrelas, forks, data de criação e de última
atualização.

Pensado para o cenário descrito no case — "roda sozinho às 6h, ninguém acompanha":

| Requisito | Como foi resolvido |
|---|---|
| Autenticação | `GITHUB_TOKEN` via variável de ambiente (nunca hardcoded, nunca em log) |
| Paginação completa | Itera até a página vazia; valida contagem esperada vs. coletada |
| Timeout / retry | `requests` com `Retry` (backoff exponencial) em 403/429/5xx, timeout de 15s |
| Execução concorrente | Lock file com PID e expiração (30 min) |
| Validação antes/depois | Compara `public_repos` da API da org com o total paginado |
| Log da execução | `data/output/github_collection_status.json`: início, fim, duração, páginas, registros, status, erro, SHA-256 |
| Agendamento 6h | `.github/workflows/coleta-github-diaria.yml` (cron `0 9 * * *` UTC = 6h BRT) |
| Execução manual | `workflow_dispatch` no mesmo workflow, ou rodar o script direto |

**Caso real de falha, não simulado:** sem `GITHUB_TOKEN` configurado neste ambiente
de desenvolvimento, a segunda execução em sequência excedeu o limite de 60
requisições/hora da API não-autenticada e retornou 403. O status ficou:

```json
{
  "status": "erro",
  "erro": "HTTPSConnectionPool(...): too many 403 error responses",
  "registros_processados": 0
}
```

E o CSV da coleta anterior (3.171 registros, íntegro) permaneceu intacto — a escrita
é atômica (`.csv.tmp` → replace só em caso de sucesso total). Ver
[`DECISOES_TECNICAS.md`](DECISOES_TECNICAS.md#parte-1--coleta-github) para o
raciocínio completo.

---

## Parte 2 — Análise comercial (resultados)

**Queries:** [`sql/01_custo_por_lead_e_venda.sql`](sql/01_custo_por_lead_e_venda.sql) ·
[`sql/02_funil_por_campanha.sql`](sql/02_funil_por_campanha.sql) ·
[`sql/03_ticket_medio_receita.sql`](sql/03_ticket_medio_receita.sql)

Fontes: `dados/investimento_midia.csv` (352 linhas), `dados/leads.csv` (478 linhas),
`dados/vendas.csv` (49 linhas). Carregados em SQLite via
[`build_database.py`](src/parte2_analise/build_database.py), consultados e exportados
via [`export_web.py`](src/parte2_analise/export_web.py).

### 1. Custo por lead e por venda, por campanha (todo o período, melhor → pior)

| Campanha | Plataforma | Leads | Vendas | Investimento | Custo/lead | Custo/venda |
|---|---|--:|--:|--:|--:|--:|
| Busca Google — marca (`cmp_004`) | Google | 40 | 13 | R$ 3.679,14 | R$ 91,98 | **R$ 283,01** |
| Leads — apartamento novo (`cmp_006`) | Meta | 71 | 11 | R$ 7.357,81 | R$ 103,63 | R$ 668,89 |
| Remarketing — visitantes do site (`cmp_003`) | Meta | 71 | 8 | R$ 7.062,61 | R$ 99,47 | R$ 882,83 |
| Planejados de Dormitório (`cmp_002`) | Meta | 96 | 7 | R$ 11.260,30 | R$ 117,29 | R$ 1.608,61 |
| Busca Google — genérico (`cmp_005`) | Google | 95 | 5 | R$ 11.596,14 | R$ 122,06 | R$ 2.319,23 |
| Planejados de Cozinha (`cmp_001`) | Meta | 95 | 4 | R$ 10.689,91 | R$ 112,53 | R$ 2.672,48 |
| (sem campanha atribuída) | — | 6 | 1 | *sem dado* | — | — |
| `cmp_999` (sem investimento associado) | — | 4 | 0 | *sem dado* | — | — |

`cmp_999` e a linha "sem campanha atribuída" mostram *sem dado*, não R$ 0,00 — não há
registro de investimento associado a eles, e isso é uma informação diferente de gasto
zero (ver decisão detalhada no link acima).

### 2. Funil por campanha (leads por etapa, % de perda entre etapas)

Cada campanha, do total de leads que **não** foram perdidos, quantos alcançaram cada
etapa (novo → em atendimento → qualificado → briefing → proposta → vendido) e o % de
perda entre uma etapa e a seguinte. Leads "perdido" são reportados à parte
(`% perdidos do total`), não encaixados num degrau específico — o dado não diz em
qual etapa eles pararam. Exemplo (campanha com melhor conversão, `cmp_004`):

| Etapa | Leads | Perda para a próxima |
|---|--:|--:|
| Novo | 34 | −14,7% |
| Em atendimento | 29 | −6,9% |
| Qualificado | 27 | −33,3% |
| Briefing | 18 | −11,1% |
| Proposta | 16 | −18,8% |
| Vendido | 13 | — |

(15% dos 40 leads dessa campanha foram perdidos — a menor taxa entre todas.) Tabela
completa das 8 campanhas na interface (Parte 2) ou rodando a query direto.

### 3. Ticket médio e receita total por campanha

| # | Campanha | Vendas | Ticket médio | Receita total |
|--:|---|--:|--:|--:|
| 1 | (sem campanha atribuída)* | 1 | R$ 44.909,27 | R$ 44.909,27 |
| — | **Busca Google — marca** | 13 | **R$ 39.784,90** | R$ 517.203,67 |
| — | Busca Google — genérico | 5 | R$ 38.406,96 | R$ 192.034,78 |
| — | Planejados de Cozinha | 4 | R$ 38.145,29 | R$ 152.581,16 |
| — | Leads — apartamento novo | 11 | R$ 36.733,26 | R$ 404.065,89 |
| — | Planejados de Dormitório | 7 | R$ 35.948,24 | R$ 251.637,65 |
| — | Remarketing — visitantes do site | 8 | R$ 29.443,97 | R$ 235.551,73 |

\* excluída do ranking de "cliente de maior valor" — é uma única venda avulsa sem
campanha real por trás, não uma campanha comparável.

**Cliente de maior valor entre campanhas reais: "Busca Google — marca"** — e é
também a de melhor custo por venda. Essa é a leitura que eu levaria para a decisão de
realocação de verba: não é só a mais barata por venda, é a que também traz o
contrato médio mais alto.

**Confiabilidade dos números:** cada valor acima é rastreável até a query SQL exata
que o gerou, os arquivos de origem e a contagem de registros usados — visível ao
clicar em qualquer indicador na interface, ou lendo os comentários no topo de cada
arquivo `.sql`. As limitações e inferências assumidas (cobertura de datas
desalinhada entre os 3 CSVs, ausência de histórico de etapa no funil) estão
documentadas em detalhe em
[`DECISOES_TECNICAS.md`](DECISOES_TECNICAS.md#parte-2--análise-comercial) e expostas
também na interface (seção "Limitações dos dados").

---

## Parte 3 — Classificação de pré-vendas

**Script:** [`src/parte3_prevendas/classify.py`](src/parte3_prevendas/classify.py) ·
**Prompt:** [`prompts/prompt_classificacao_prevendas.txt`](prompts/prompt_classificacao_prevendas.txt)

Classifica as 15 conversas de `dados/conversas_prevendas.json` com o Gemini
(modelo configurável via `GEMINI_MODEL`, com fallback automático em
`GEMINI_FALLBACK_MODELS` se o principal falhar). Schema de saída por conversa:

```json
{
  "conversa_id": "CV001",
  "classificacao": "quente | morno | frio | fora_do_perfil",
  "prioridade": 1,
  "resumo_para_o_vendedor": "...",
  "sinais": ["..."],
  "evidencias": [{"numero_mensagem": 5, "trecho": "..."}],
  "proxima_acao": "...",
  "alertas": ["..."],
  "revisao_humana_recomendada": false,
  "motivo_revisao_humana": null
}
```

Critérios de classificação, escala de prioridade e regras de evidência estão no
próprio prompt (versionado, arquivo separado do código). Resumo das garantias:

- **JSON sempre válido:** parsing tolerante a cercas markdown, validação de schema e
  de tipos (`src/parte3_prevendas/validators.py`).
- **Evidência é verificada contra o texto real da mensagem citada** — uma citação que
  não bate com a mensagem numerada é tratada como alucinação e rejeitada.
- **Falha técnica nunca vira "frio":** se todas as tentativas (modelo principal +
  fallbacks, com retry) falharem, ou se o JSON não passar na validação mesmo após uma
  rodada de correção, o registro final é `status: "falha_tecnica"` — nunca uma
  classificação fabricada.
- **Checkpoint por conversa** (`data/output/checkpoints/{id}.json`): rodar de novo
  pula o que já foi classificado com sucesso, importante pensando em escala.
- **As conversas não têm vínculo individual garantido com `leads.csv`/`vendas.csv`**
  — têm `campanha_id`, mas não `lead_id`. A interface e este README tratam essa
  ausência de vínculo como fato, não como suposição a ser preenchida.

**Resultado de uma execução real** (`gemini-3.6-flash`, 15/15 conversas classificadas,
0 falhas técnicas, 0 rodadas de correção necessárias — toda resposta passou na
validação de schema e de evidência na primeira tentativa):

| Classificação | Conversas |
|---|--:|
| Quente | 8 |
| Morno | 1 |
| Frio | 5 |
| Fora do perfil | 1 |

Um exemplo (`CV012`) mostra o pipeline reagindo a um caso ambíguo por conta própria:
o lead abre a conversa com "MUITO CARO" e some antes de informar escopo — o modelo
classificou como `frio`, mas marcou `revisao_humana_recomendada: true` com o motivo
"conversa muito curta e ambígua, sem resposta do lead à tentativa do atendente de dar
continuidade". Nenhuma dessas conversas teve `lead_id`/vínculo com `leads.csv` no
dado de origem — a leitura acima é só sobre o conteúdo da conversa em si.

**Como eu avaliaria a qualidade disso daqui a 3 meses, com 4.000 conversas
processadas** — resposta completa e concreta (métrica, contra o quê, frequência,
gatilho de alerta) em
[`DECISOES_TECNICAS.md`](DECISOES_TECNICAS.md#parte-3--classificação-de-pré-vendas).
O suporte de código para isso já existe:
[`src/parte3_prevendas/avaliar_qualidade.py`](src/parte3_prevendas/avaliar_qualidade.py).

---

## O que ficou de fora, e por quê

- **Deploy do React.** O case exclui deploy dos critérios de avaliação; o front-end
  em si já é um adicional por escolha própria (ver topo deste README).
- **Histórico de transição de etapa no funil.** Os dados não têm essa granularidade
  (`leads.csv` só traz a etapa atual) — inventar isso seria pior do que não ter.
- **Avaliação de qualidade da Parte 3 com dado real.** Só 15 conversas existem neste
  case; o módulo de avaliação (`avaliar_qualidade.py`) está pronto e testado, mas
  precisa de rótulos humanos reais para produzir uma métrica real — não fabriquei
  rótulos humanos falsos só para popular um número.
- **Dashboard de custo/latência da API do Gemini.** Relevante em produção, mas não
  muda nenhuma decisão que este case pede para justificar.

## Uso de IA neste case

Usei Claude (via Claude Code) para gerar a estrutura inicial dos scripts, das queries
SQL e dos componentes React a partir de decisões que tomei antes de escrever qualquer
código (critério de classificação, tratamento de NULL vs. zero nas agregações, o que
preservar/descartar em cada junção) — e para escrever esta documentação. Revisei
manualmente rodando cada parte contra dado real (incluindo um rate-limit real na
Parte 1, não simulado), conferindo os números da Parte 2 na mão antes de aceitar, e
travando as invariantes mais importantes em testes automatizados. Detalhes em
[`DECISOES_TECNICAS.md`](DECISOES_TECNICAS.md#sobre-o-uso-de-ia-neste-case).

## Testes

```bash
python -m pytest -q
```

32 testes cobrindo: paginação/erro/lock/limpeza de arquivo temporário da Parte 1 (com API mockada), invariantes de
agregação e preservação de dado da Parte 2 (contra o banco real gerado dos CSVs do
case), e validação de schema/evidência/retry-fallback da Parte 3 (com cliente Gemini
mockado — não depende de rede nem de API key para rodar).

CI (`.github/workflows/ci.yml`): roda os testes, valida que as queries SQL executam
contra os dados reais, builda o front-end, e falha se algum `.env` for encontrado
versionado no repositório.

## Segurança de credenciais

- `.env` está no `.gitignore`; só `.env.example` (sem valores reais) é versionado.
- Tokens são lidos exclusivamente de variável de ambiente — nunca aparecem em
  argumento de CLI, log, ou mensagem de erro.
- O workflow de coleta diária usa o `GITHUB_TOKEN` automático do GitHub Actions
  (não é um secret que precisa ser cadastrado manualmente).
- `data/db/*.sqlite` e `data/output/checkpoints/*.json` não são versionados — são
  artefatos reproduzíveis a partir dos scripts, não fonte de verdade.
