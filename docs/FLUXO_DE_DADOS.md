# Fluxo de dados e como atualizar

```
arquivos de entrada          ingestão Python           SQLite / SQL              saída JSON/CSV                    React
──────────────────           ────────────────          ────────────              ──────────────                    ─────
dados/*.csv, *.json    →     src/parte1_github/   →                        →     data/output/github_*.csv/.json  → web/public/data/*
(originais, intocados)       src/parte2_analise/   →   data/db/comodo.sqlite →   data/output/analise_*.csv/.json → web/public/data/*
                              src/parte3_prevendas/ →   (via SQL em sql/*.sql) →  data/output/classificacoes_*.json → web/public/data/*
```

Cada script Python é a única fonte de verdade dos arquivos em `data/output/` e
`web/public/data/` — nenhum desses arquivos deve ser editado à mão. Rodar os scripts
de novo sempre sobrescreve com o estado atual dos dados de entrada.

## Regra geral para adicionar dados novos

1. **Nunca edite os arquivos em `dados/`** — são os originais do case. Se surgir uma
   nova exportação, adicione como um novo arquivo ou substitua mantendo exatamente os
   mesmos nomes de coluna (isso é o que faz os scripts continuarem funcionando sem
   mudança de código).
2. Rode os scripts de novo (comandos abaixo).
3. Os arquivos em `web/public/data/` são regenerados automaticamente — nenhum
   componente React precisa mudar para refletir os números novos.

## Parte 1 — novos dados do GitHub

A coleta é sempre "do zero" (não incremental) — não há passo manual.

```bash
python -m src.parte1_github.collect_repos --org apache
```

Isso sobrescreve `data/output/github_repos_apache.csv`,
`data/output/github_collection_status.json`, e espelha os dois em
`web/public/data/`. Rodar automaticamente todo dia às 6h é feito pelo workflow
`.github/workflows/coleta-github-diaria.yml` (ver README para detalhes de fuso).

## Parte 2 — novos CSVs de mídia/leads/vendas

Se `dados/investimento_midia.csv`, `dados/leads.csv` ou `dados/vendas.csv` forem
substituídos (mesmo cabeçalho, dados novos ou período maior):

```bash
python -m src.parte2_analise.build_database   # recria o SQLite do zero a partir dos CSVs
python -m src.parte2_analise.export_web       # roda as 3 queries e exporta JSON/CSV
```

Se uma nova campanha aparecer (`cmp_00N` novo), ela aparece automaticamente nas três
seções — a única coisa "hardcoded" é o nome amigável de apresentação
(`NOMES_AMIGAVEIS` em `src/parte2_analise/export_web.py`); sem entrada nesse
dicionário, a campanha aparece com o próprio `campanha_id` no lugar do nome
amigável (não quebra, só fica menos legível até alguém adicionar o nome).

## Parte 3 — novas conversas

```bash
python -m src.parte3_prevendas.classify
```

Por padrão, conversas que já têm checkpoint com `status: "classificado"` em
`data/output/checkpoints/` são puladas — só as novas (ou as que falharam antes) são
enviadas ao modelo. Use `--force` para reclassificar tudo do zero:

```bash
python -m src.parte3_prevendas.classify --force
```

Se o volume crescer para a escala mencionada no case (~4.000 conversas), o mesmo
comando funciona sem mudança — o gargalo passa a ser rate limit da API do Gemini, não
o código (o checkpoint por conversa já existe exatamente para tornar interrupções e
reprocessamento parcial seguros nessa escala).

## Rodando tudo de uma vez

```bash
python -m src.parte1_github.collect_repos --org apache
python -m src.parte2_analise.build_database
python -m src.parte2_analise.export_web
python -m src.parte3_prevendas.classify   # requer GEMINI_API_KEY em .env
```

Depois, `npm --prefix web run dev` (ou `npm run build` para produção) já lê os
arquivos atualizados em `web/public/data/` sem qualquer alteração de código.
