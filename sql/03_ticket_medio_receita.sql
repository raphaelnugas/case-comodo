-- Parte 2 | Pergunta 3: Ticket médio e receita total por campanha,
-- e qual campanha traz o cliente de maior valor.
--
-- "Cliente de maior valor" é interpretado como a campanha com maior TICKET MÉDIO
-- (valor médio de contrato por venda) — não necessariamente a de maior receita total,
-- que pode estar inflada por volume. As duas métricas são reportadas lado a lado
-- para não esconder esse trade-off (uma campanha pode ter poucas vendas de alto valor,
-- outra muitas vendas de valor menor).
--
-- Vendas e leads sem campanha atribuída são preservados na linha "(sem campanha atribuída)".

WITH leads_norm AS (
    SELECT
        lead_id,
        COALESCE(NULLIF(TRIM(campanha_id), ''), '(sem campanha atribuída)') AS campanha_key
    FROM leads
),
vendas_por_campanha AS (
    SELECT
        ln.campanha_key,
        COUNT(*)                    AS total_vendas,
        SUM(v.valor_contrato)       AS receita_total,
        ROUND(AVG(v.valor_contrato), 2) AS ticket_medio,
        MIN(v.valor_contrato)       AS menor_contrato,
        MAX(v.valor_contrato)       AS maior_contrato
    FROM vendas v
    JOIN leads_norm ln ON ln.lead_id = v.lead_id
    GROUP BY ln.campanha_key
)
SELECT
    campanha_key AS campanha_id,
    total_vendas,
    receita_total,
    ticket_medio,
    menor_contrato,
    maior_contrato,
    RANK() OVER (ORDER BY ticket_medio DESC) AS rank_ticket_medio,
    RANK() OVER (ORDER BY receita_total DESC) AS rank_receita_total
FROM vendas_por_campanha
ORDER BY ticket_medio DESC;
