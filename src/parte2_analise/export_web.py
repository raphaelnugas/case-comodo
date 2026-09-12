"""
Parte 2 | Executa as 3 queries SQL contra o SQLite e exporta:
  - CSVs de cada seção (para o botão de download no React)
  - Um JSON de metadados/auditoria (fórmula, SQL usado, arquivos-fonte, registros
    utilizados) para alimentar o "clique/hover para ver de onde veio o número"
  - Um JSON com os cards de indicadores principais

Reexecutar este script (após reexecutar build_database.py) é o único passo necessário
para refletir novos dados na interface — nenhum componente React precisa mudar.

Uso:
    python -m src.parte2_analise.export_web
"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "db" / "comodo.sqlite"
SQL_DIR = REPO_ROOT / "sql"
OUTPUT_DIR = REPO_ROOT / "data" / "output"
WEB_PUBLIC_DATA_DIR = REPO_ROOT / "web" / "public" / "data"

FONTES = [
    "dados/investimento_midia.csv",
    "dados/leads.csv",
    "dados/vendas.csv",
]

# Nomes amigáveis para apresentação — o nome real (slug) extraído dos dados é sempre
# preservado ao lado, como pede a especificação ("nome amigável ... e, como observação,
# o nome real extraído dos dados").
NOMES_AMIGAVEIS = {
    "cmp_001": "Planejados de Cozinha (público frio)",
    "cmp_002": "Planejados de Dormitório (público frio)",
    "cmp_003": "Remarketing — visitantes do site",
    "cmp_004": "Busca Google — marca",
    "cmp_005": "Busca Google — genérico",
    "cmp_006": "Leads — apartamento novo",
    "cmp_999": "Origem não identificada (sem investimento associado)",
    "(sem campanha atribuída)": "Sem campanha atribuída",
}


def run_query(conn: sqlite3.Connection, sql_path: Path) -> list[dict]:
    sql = sql_path.read_text(encoding="utf-8")
    cur = conn.execute(sql)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def enrich_campanha(row: dict) -> dict:
    key = row.get("campanha_id")
    row["nome_campanha_amigavel"] = NOMES_AMIGAVEIS.get(key, key)
    return row


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_indicadores_principais(custo: list[dict], funil: list[dict], ticket: list[dict]) -> list[dict]:
    campanhas_reais = [r for r in custo if r["campanha_id"] not in ("(sem campanha atribuída)",)]

    total_investido = sum(r["gasto_total"] for r in campanhas_reais if r["gasto_total"] is not None)
    total_leads = sum(r["total_leads"] for r in custo)
    total_vendas = sum(r["total_vendas"] for r in custo)
    total_receita = sum(r["receita_total"] for r in custo if r["receita_total"] is not None)

    com_custo = [r for r in campanhas_reais if r["custo_por_venda"] is not None]
    melhor = min(com_custo, key=lambda r: r["custo_por_venda"]) if com_custo else None

    # Exclui "(sem campanha atribuída)" do ranking de ticket médio: é 1 venda avulsa,
    # sem uma campanha real por trás, e não deve responder "qual CAMPANHA traz o
    # cliente de maior valor" — mas continua visível na tabela detalhada da seção.
    ticket_campanhas_reais = [r for r in ticket if r["campanha_id"] != "(sem campanha atribuída)"]
    maior_ticket = max(ticket_campanhas_reais, key=lambda r: r["ticket_medio"]) if ticket_campanhas_reais else None

    return [
        {
            "label": "Investimento total em mídia",
            "valor": round(total_investido, 2),
            "formato": "moeda",
            "formula": "SOMA(gasto) de investimento_midia.csv em todas as campanhas identificadas",
            "fonte": ["dados/investimento_midia.csv"],
            "sql_arquivo": "sql/01_custo_por_lead_e_venda.sql",
            "registros_utilizados": sum(r["registros_midia"] or 0 for r in campanhas_reais),
        },
        {
            "label": "Total de leads",
            "valor": total_leads,
            "formato": "inteiro",
            "formula": "COUNT(*) de leads.csv, incluindo leads sem campanha atribuída",
            "fonte": ["dados/leads.csv"],
            "sql_arquivo": "sql/01_custo_por_lead_e_venda.sql",
            "registros_utilizados": total_leads,
        },
        {
            "label": "Total de vendas",
            "valor": total_vendas,
            "formato": "inteiro",
            "formula": "COUNT(*) de vendas.csv, ligado a leads.csv por lead_id",
            "fonte": ["dados/vendas.csv", "dados/leads.csv"],
            "sql_arquivo": "sql/01_custo_por_lead_e_venda.sql",
            "registros_utilizados": total_vendas,
        },
        {
            "label": "Receita total",
            "valor": round(total_receita, 2),
            "formato": "moeda",
            "formula": "SOMA(valor_contrato) de vendas.csv em todas as campanhas",
            "fonte": ["dados/vendas.csv"],
            "sql_arquivo": "sql/03_ticket_medio_receita.sql",
            "registros_utilizados": total_vendas,
        },
        {
            "label": "Melhor custo por venda",
            "valor": f"{melhor['nome_campanha_amigavel']} — R$ {melhor['custo_por_venda']:.2f}" if melhor else "sem dado calculável",
            "formato": "texto",
            "formula": "MIN(custo_por_venda) entre campanhas com investimento e vendas registrados",
            "fonte": FONTES,
            "sql_arquivo": "sql/01_custo_por_lead_e_venda.sql",
            "registros_utilizados": melhor["total_vendas"] if melhor else 0,
        },
        {
            "label": "Cliente de maior valor (ticket médio)",
            "valor": f"{maior_ticket['nome_campanha_amigavel'] if maior_ticket else '—'}" if maior_ticket else "—",
            "detalhe": f"ticket médio R$ {maior_ticket['ticket_medio']:.2f}" if maior_ticket else None,
            "formato": "texto",
            "formula": "MAX(AVG(valor_contrato)) por campanha real (exclui vendas sem campanha atribuída)",
            "nota": "Vendas sem campanha atribuída não entram nesse ranking por não terem uma campanha real por trás — aparecem à parte na tabela detalhada.",
            "fonte": ["dados/vendas.csv", "dados/leads.csv"],
            "sql_arquivo": "sql/03_ticket_medio_receita.sql",
            "registros_utilizados": maior_ticket["total_vendas"] if maior_ticket else 0,
        },
    ]


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = None
    try:
        custo_sql_path = SQL_DIR / "01_custo_por_lead_e_venda.sql"
        funil_sql_path = SQL_DIR / "02_funil_por_campanha.sql"
        ticket_sql_path = SQL_DIR / "03_ticket_medio_receita.sql"

        custo = [enrich_campanha(r) for r in run_query(conn, custo_sql_path)]
        funil = [enrich_campanha(r) for r in run_query(conn, funil_sql_path)]
        ticket = [enrich_campanha(r) for r in run_query(conn, ticket_sql_path)]

        contagens_fonte = {
            "investimento_midia": conn.execute("SELECT COUNT(*) FROM investimento_midia").fetchone()[0],
            "leads": conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
            "vendas": conn.execute("SELECT COUNT(*) FROM vendas").fetchone()[0],
        }
    finally:
        conn.close()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(custo, OUTPUT_DIR / "analise_custo_por_campanha.csv")
    write_csv(funil, OUTPUT_DIR / "analise_funil_por_campanha.csv")
    write_csv(ticket, OUTPUT_DIR / "analise_ticket_medio_receita.csv")

    metadata = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fontes_originais": FONTES,
        "contagens_fonte": contagens_fonte,
        "limitacoes": [
            "Os dados cobrem maio e junho de 2026 para investimento em mídia; leads existem "
            "até 02/07/2026 e vendas fecham até 18/09/2026 — leads mais recentes ainda não "
            "tiveram tempo equivalente para converter, o que pode subestimar o desempenho "
            "de campanhas com leads mais novos.",
            "O funil usa apenas a etapa ATUAL do lead (não há histórico de transições). "
            "Assumimos progressão monotônica para leads ativos/vendidos; leads 'perdido' "
            "são excluídos do cálculo degrau-a-degrau porque não sabemos em qual etapa "
            "eles pararam — são reportados como métrica agregada à parte.",
            "'cmp_999' e leads sem campanha_id não têm investimento associado: o custo é "
            "exibido como indisponível (não como zero), pois ausência de registro de "
            "investimento não significa gasto zero.",
            "'Cliente de maior valor' é calculado por ticket médio (valor médio por venda), "
            "não por receita total — campanhas com poucas vendas de alto valor podem ficar "
            "no topo mesmo com receita total menor. A campanha '(sem campanha atribuída)' "
            "tem apenas 1 venda, então seu ticket médio não é estatisticamente robusto.",
        ],
        "secoes": {
            "custo_por_campanha": {
                "titulo": "Custo por lead e custo por venda, por campanha",
                "descricao": "Ordenado do melhor para o pior custo por venda.",
                "formula_custo_por_lead": "gasto_total (SOMA de investimento_midia.gasto) / total_leads (COUNT de leads.csv)",
                "formula_custo_por_venda": "gasto_total / total_vendas (COUNT de vendas.csv ligadas via lead_id)",
                "sql_arquivo": "sql/01_custo_por_lead_e_venda.sql",
                "sql": custo_sql_path.read_text(encoding="utf-8"),
                "fontes": FONTES,
                "registros_utilizados": contagens_fonte,
                "linhas": custo,
            },
            "funil_por_campanha": {
                "titulo": "Funil por campanha: leads por etapa e percentual de perda",
                "descricao": "Quantidade de leads que alcançaram cada etapa e % de perda entre etapas consecutivas.",
                "sql_arquivo": "sql/02_funil_por_campanha.sql",
                "sql": funil_sql_path.read_text(encoding="utf-8"),
                "fontes": ["dados/leads.csv"],
                "registros_utilizados": {"leads": contagens_fonte["leads"]},
                "linhas": funil,
            },
            "ticket_medio_receita": {
                "titulo": "Ticket médio e receita total por campanha",
                "descricao": "Valor médio de contrato e receita somada por campanha, com o rank de cada uma.",
                "sql_arquivo": "sql/03_ticket_medio_receita.sql",
                "sql": ticket_sql_path.read_text(encoding="utf-8"),
                "fontes": ["dados/vendas.csv", "dados/leads.csv"],
                "registros_utilizados": {"vendas": contagens_fonte["vendas"], "leads": contagens_fonte["leads"]},
                "linhas": ticket,
            },
        },
        "indicadores_principais": build_indicadores_principais(custo, funil, ticket),
    }

    (OUTPUT_DIR / "analise_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Espelha os artefatos que o React consome em web/public/data (ver
    # documentacao/FLUXO_DE_DADOS.md) — assim o front-end não precisa de backend rodando.
    WEB_PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name in [
        "analise_metadata.json",
        "analise_custo_por_campanha.csv",
        "analise_funil_por_campanha.csv",
        "analise_ticket_medio_receita.csv",
    ]:
        (WEB_PUBLIC_DATA_DIR / name).write_bytes((OUTPUT_DIR / name).read_bytes())

    print(f"Exportado: {OUTPUT_DIR}")
    print(f"  custo_por_campanha: {len(custo)} linhas")
    print(f"  funil_por_campanha: {len(funil)} linhas")
    print(f"  ticket_medio_receita: {len(ticket)} linhas")


if __name__ == "__main__":
    main()
