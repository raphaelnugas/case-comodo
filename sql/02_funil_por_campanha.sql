-- Parte 2 | Pergunta 2: Funil por campanha — quantos leads chegaram a cada etapa
-- e qual o percentual de perda entre uma etapa e a seguinte.
--
-- LIMITAÇÃO DE DADOS IMPORTANTE (ver README/DECISOES_TECNICAS.md):
-- `leads.csv` só traz a etapa ATUAL de cada lead (`etapa_atual`), não o histórico de
-- transições. Não sabemos, por exemplo, em qual etapa um lead estava quando passou
-- para "perdido". Por isso este funil faz uma inferência explícita e assumida:
--
--   1. Para leads que NÃO estão em "perdido", tratamos `etapa_atual` como a etapa
--      mais avançada que o lead alcançou (progressão monotônica: novo -> em_atendimento
--      -> qualificado -> briefing_realizado -> proposta -> vendido). É uma suposição
--      razoável para um funil linear, mas é uma suposição, não um fato do dado.
--   2. Leads "perdido" são EXCLUÍDOS do cálculo degrau-a-degrau, porque não sabemos em
--      qual etapa eles pararam — incluí-los em qualquer etapa seria inventar dado.
--      Em vez disso, "perdido" é reportado como uma métrica agregada por campanha,
--      separada do funil (ver última coluna).
--   3. Percentual de perda entre a etapa N e N+1 = (alcançou N - alcançou N+1) / alcançou N.

WITH leads_norm AS (
    SELECT
        lead_id,
        COALESCE(NULLIF(TRIM(campanha_id), ''), '(sem campanha atribuída)') AS campanha_key,
        etapa_atual
    FROM leads
),
alcance AS (
    SELECT
        campanha_key,
        SUM(CASE WHEN etapa_atual != 'perdido' THEN 1 ELSE 0 END) AS alcancou_novo,
        SUM(CASE WHEN etapa_atual IN ('em_atendimento','qualificado','briefing_realizado','proposta','vendido') THEN 1 ELSE 0 END) AS alcancou_em_atendimento,
        SUM(CASE WHEN etapa_atual IN ('qualificado','briefing_realizado','proposta','vendido') THEN 1 ELSE 0 END) AS alcancou_qualificado,
        SUM(CASE WHEN etapa_atual IN ('briefing_realizado','proposta','vendido') THEN 1 ELSE 0 END) AS alcancou_briefing,
        SUM(CASE WHEN etapa_atual IN ('proposta','vendido') THEN 1 ELSE 0 END) AS alcancou_proposta,
        SUM(CASE WHEN etapa_atual = 'vendido' THEN 1 ELSE 0 END) AS alcancou_vendido,
        SUM(CASE WHEN etapa_atual = 'perdido' THEN 1 ELSE 0 END) AS total_perdidos,
        COUNT(*) AS total_leads
    FROM leads_norm
    GROUP BY campanha_key
)
SELECT
    campanha_key AS campanha_id,
    total_leads,
    alcancou_novo,
    alcancou_em_atendimento,
    alcancou_qualificado,
    alcancou_briefing,
    alcancou_proposta,
    alcancou_vendido,
    total_perdidos,
    ROUND(100.0 * total_perdidos / NULLIF(total_leads, 0), 1)                                       AS pct_perdidos_do_total,
    ROUND(100.0 * (alcancou_novo - alcancou_em_atendimento) / NULLIF(alcancou_novo, 0), 1)           AS pct_perda_novo_para_atendimento,
    ROUND(100.0 * (alcancou_em_atendimento - alcancou_qualificado) / NULLIF(alcancou_em_atendimento, 0), 1) AS pct_perda_atendimento_para_qualificado,
    ROUND(100.0 * (alcancou_qualificado - alcancou_briefing) / NULLIF(alcancou_qualificado, 0), 1)   AS pct_perda_qualificado_para_briefing,
    ROUND(100.0 * (alcancou_briefing - alcancou_proposta) / NULLIF(alcancou_briefing, 0), 1)         AS pct_perda_briefing_para_proposta,
    ROUND(100.0 * (alcancou_proposta - alcancou_vendido) / NULLIF(alcancou_proposta, 0), 1)          AS pct_perda_proposta_para_vendido
FROM alcance
ORDER BY campanha_id;
