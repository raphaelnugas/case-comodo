import csv
import sqlite3
from pathlib import Path

import pytest

from src.parte2_analise.build_database import build

REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = REPO_ROOT / "sql"
DADOS_DIR = REPO_ROOT / "dados"


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "comodo_teste.sqlite"
    build(db_path=path)
    return path


def _run_sql(db_path: Path, nome_arquivo: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    try:
        sql = (SQL_DIR / nome_arquivo).read_text(encoding="utf-8")
        cur = conn.execute(sql)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def test_build_database_carrega_contagens_iguais_aos_csvs(db_path):
    conn = sqlite3.connect(db_path)
    try:
        n_leads = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        n_vendas = conn.execute("SELECT COUNT(*) FROM vendas").fetchone()[0]
        n_midia = conn.execute("SELECT COUNT(*) FROM investimento_midia").fetchone()[0]
    finally:
        conn.close()

    with (DADOS_DIR / "leads.csv").open(encoding="utf-8") as f:
        assert n_leads == sum(1 for _ in csv.DictReader(f))
    with (DADOS_DIR / "vendas.csv").open(encoding="utf-8") as f:
        assert n_vendas == sum(1 for _ in csv.DictReader(f))
    with (DADOS_DIR / "investimento_midia.csv").open(encoding="utf-8") as f:
        assert n_midia == sum(1 for _ in csv.DictReader(f))


def test_custo_por_campanha_nao_transforma_ausencia_de_investimento_em_zero(db_path):
    linhas = _run_sql(db_path, "01_custo_por_lead_e_venda.sql")
    por_id = {r["campanha_id"]: r for r in linhas}

    # cmp_999 tem leads mas nenhuma linha em investimento_midia.csv
    assert "cmp_999" in por_id
    assert por_id["cmp_999"]["gasto_total"] is None
    assert por_id["cmp_999"]["custo_por_lead"] is None
    assert por_id["cmp_999"]["custo_por_venda"] is None
    assert por_id["cmp_999"]["total_leads"] == 4  # não deve ser descartado


def test_custo_por_campanha_preserva_leads_sem_campanha(db_path):
    linhas = _run_sql(db_path, "01_custo_por_lead_e_venda.sql")
    sem_campanha = [r for r in linhas if r["campanha_id"] == "(sem campanha atribuída)"]
    assert len(sem_campanha) == 1
    assert sem_campanha[0]["total_leads"] > 0


def test_custo_por_campanha_esta_ordenado_do_melhor_pro_pior(db_path):
    linhas = _run_sql(db_path, "01_custo_por_lead_e_venda.sql")
    com_valor = [r["custo_por_venda"] for r in linhas if r["custo_por_venda"] is not None]
    assert com_valor == sorted(com_valor)


def test_soma_de_leads_por_campanha_bate_com_total_de_leads(db_path):
    linhas = _run_sql(db_path, "01_custo_por_lead_e_venda.sql")
    conn = sqlite3.connect(db_path)
    try:
        total_real = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    finally:
        conn.close()
    assert sum(r["total_leads"] for r in linhas) == total_real


def test_funil_e_monotonicamente_decrescente_por_campanha(db_path):
    linhas = _run_sql(db_path, "02_funil_por_campanha.sql")
    etapas = [
        "alcancou_novo",
        "alcancou_em_atendimento",
        "alcancou_qualificado",
        "alcancou_briefing",
        "alcancou_proposta",
        "alcancou_vendido",
    ]
    for r in linhas:
        valores = [r[e] for e in etapas]
        assert valores == sorted(valores, reverse=True), f"funil não monotônico em {r['campanha_id']}: {valores}"


def test_funil_nao_atribui_perdidos_a_uma_etapa_especifica(db_path):
    linhas = _run_sql(db_path, "02_funil_por_campanha.sql")
    for r in linhas:
        # alcancou_novo conta todo mundo que não está "perdido"; perdidos ficam de fora
        assert r["alcancou_novo"] + r["total_perdidos"] == r["total_leads"]


def test_ticket_medio_nao_duplica_receita_por_join(db_path):
    linhas = _run_sql(db_path, "03_ticket_medio_receita.sql")
    conn = sqlite3.connect(db_path)
    try:
        receita_real_total = conn.execute("SELECT SUM(valor_contrato) FROM vendas").fetchone()[0]
    finally:
        conn.close()
    assert round(sum(r["receita_total"] for r in linhas), 2) == round(receita_real_total, 2)
