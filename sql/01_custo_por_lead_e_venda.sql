-- Parte 2 | Pergunta 1: Custo por lead e custo por venda, por campanha,
-- considerando todo o período disponível. Ordenado do melhor para o pior custo por venda.
--
-- Decisões importantes (ver README/DECISOES_TECNICAS.md para detalhes):
--   1. Cada fato (gasto, leads, vendas) é agregado por campanha SEPARADAMENTE antes de
--      qualquer junção. Isso evita duplicação de valores: se juntássemos
--      investimento_midia (352 linhas diárias) diretamente com leads ou vendas,
--      cada linha de lead/venda seria multiplicada pelo número de linhas de mídia
--      daquela campanha (produto cartesiano), inflando o gasto somado.
--   2. `todas_campanhas` une as campanhas que aparecem em leads e em investimento_midia,
--      preservando: (a) campanhas com mídia mas sem lead ainda (não existe no dataset,
--      mas o UNION cobre o caso), e (b) campanhas com lead mas sem investimento
--      registrado (ex.: cmp_999 no dataset atual).
--   3. Quando não existe NENHUMA linha de investimento para a campanha, `gasto_total`
--      fica NULL (não 0) — um LEFT JOIN sem correspondência produz NULL naturalmente,
--      e não fazemos COALESCE para 0. Gasto ausente é "não sabemos", não "gastou zero".
--   4. Leads/vendas sem campanha atribuída (campanha_id NULL ou vazio em leads.csv)
--      são somados à parte, na linha "(sem campanha atribuída)", e não descartados.
--   5. custo_por_lead e custo_por_venda usam NULLIF para nunca dividir por zero.

WITH leads_norm AS (
    SELECT
        lead_id,
        NULLIF(TRIM(campanha_id), '') AS campanha_id
    FROM leads
),
leads_agg AS (
    SELECT
        COALESCE(campanha_id, '(sem campanha atribuída)') AS campanha_key,
        COUNT(*) AS total_leads
    FROM leads_norm
    GROUP BY campanha_key
),
vendas_agg AS (
    -- join 1:1 (cada venda referencia exatamente um lead) agregado imediatamente após o join,
    -- então não há fan-out possível aqui.
    SELECT
        COALESCE(ln.campanha_id, '(sem campanha atribuída)') AS campanha_key,
        COUNT(*) AS total_vendas,
        SUM(v.valor_contrato) AS receita_total
    FROM vendas v
    JOIN leads_norm ln ON ln.lead_id = v.lead_id
    GROUP BY campanha_key
),
midia_agg AS (
    SELECT
        campanha_id AS campanha_key,
        SUM(gasto) AS gasto_total,
        COUNT(*) AS registros_midia,
        MIN(data) AS periodo_inicio,
        MAX(data) AS periodo_fim
    FROM investimento_midia
    GROUP BY campanha_id
),
nomes_campanha AS (
    SELECT DISTINCT campanha_id AS campanha_key, nome_campanha, plataforma
    FROM investimento_midia
),
todas_campanhas AS (
    SELECT campanha_key FROM leads_agg
    UNION
    SELECT campanha_key FROM midia_agg
)
SELECT
    tc.campanha_key                                        AS campanha_id,
    nc.nome_campanha                                        AS nome_campanha_real,
    nc.plataforma                                           AS plataforma,
    COALESCE(la.total_leads, 0)                             AS total_leads,
    COALESCE(va.total_vendas, 0)                            AS total_vendas,
    ma.gasto_total                                          AS gasto_total,          -- NULL = sem dado de investimento
    ma.registros_midia                                      AS registros_midia,      -- NULL = nenhuma linha de investimento_midia.csv para essa campanha
    ma.periodo_inicio                                       AS periodo_investimento_inicio,
    ma.periodo_fim                                          AS periodo_investimento_fim,
    va.receita_total                                        AS receita_total,
    ROUND(ma.gasto_total * 1.0 / NULLIF(la.total_leads, 0), 2)  AS custo_por_lead,
    ROUND(ma.gasto_total * 1.0 / NULLIF(va.total_vendas, 0), 2) AS custo_por_venda
FROM todas_campanhas tc
LEFT JOIN leads_agg  la ON la.campanha_key = tc.campanha_key
LEFT JOIN vendas_agg va ON va.campanha_key = tc.campanha_key
LEFT JOIN midia_agg  ma ON ma.campanha_key = tc.campanha_key
LEFT JOIN nomes_campanha nc ON nc.campanha_key = tc.campanha_key
ORDER BY
    CASE WHEN custo_por_venda IS NULL THEN 1 ELSE 0 END,  -- campanhas sem custo calculável vão para o final
    custo_por_venda ASC;
