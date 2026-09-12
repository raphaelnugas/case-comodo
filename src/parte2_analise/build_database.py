"""
Parte 2 | Carrega os três CSVs brutos (dados/) em um banco SQLite, preservando
os nomes de colunas originais — para que uma futura atualização dos CSVs baste
substituir os arquivos em `dados/` e rodar este script novamente.

Uso:
    python -m src.parte2_analise.build_database
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DADOS_DIR = REPO_ROOT / "dados"
DB_PATH = REPO_ROOT / "data" / "db" / "comodo.sqlite"

SCHEMA = """
DROP TABLE IF EXISTS investimento_midia;
DROP TABLE IF EXISTS leads;
DROP TABLE IF EXISTS vendas;

CREATE TABLE investimento_midia (
    data          TEXT NOT NULL,
    campanha_id   TEXT NOT NULL,
    plataforma    TEXT NOT NULL,
    nome_campanha TEXT NOT NULL,
    gasto         REAL NOT NULL,
    impressoes    INTEGER NOT NULL,
    cliques       INTEGER NOT NULL
);

CREATE TABLE leads (
    lead_id       TEXT PRIMARY KEY,
    nome          TEXT,
    telefone      TEXT,
    criado_em     TEXT NOT NULL,
    campanha_id   TEXT,          -- pode ser NULL/vazio: lead sem campanha atribuída
    etapa_atual   TEXT NOT NULL
);

CREATE TABLE vendas (
    venda_id        TEXT PRIMARY KEY,
    lead_id         TEXT NOT NULL REFERENCES leads(lead_id),
    data_fechamento TEXT NOT NULL,
    valor_contrato  REAL NOT NULL
);

CREATE INDEX idx_leads_campanha ON leads(campanha_id);
CREATE INDEX idx_midia_campanha ON investimento_midia(campanha_id);
CREATE INDEX idx_vendas_lead ON vendas(lead_id);
"""


def _load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build(db_path: Path = DB_PATH) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)

        midia = _load_csv(DADOS_DIR / "investimento_midia.csv")
        leads = _load_csv(DADOS_DIR / "leads.csv")
        vendas = _load_csv(DADOS_DIR / "vendas.csv")

        conn.executemany(
            "INSERT INTO investimento_midia "
            "(data, campanha_id, plataforma, nome_campanha, gasto, impressoes, cliques) "
            "VALUES (:data, :campanha_id, :plataforma, :nome_campanha, :gasto, :impressoes, :cliques)",
            [
                {**m, "gasto": float(m["gasto"]), "impressoes": int(m["impressoes"]), "cliques": int(m["cliques"])}
                for m in midia
            ],
        )
        conn.executemany(
            "INSERT INTO leads (lead_id, nome, telefone, criado_em, campanha_id, etapa_atual) "
            "VALUES (:lead_id, :nome, :telefone, :criado_em, :campanha_id, :etapa_atual)",
            [{**l, "campanha_id": l["campanha_id"] or None} for l in leads],
        )
        conn.executemany(
            "INSERT INTO vendas (venda_id, lead_id, data_fechamento, valor_contrato) "
            "VALUES (:venda_id, :lead_id, :data_fechamento, :valor_contrato)",
            [{**v, "valor_contrato": float(v["valor_contrato"])} for v in vendas],
        )
        conn.commit()

        counts = {
            "investimento_midia": conn.execute("SELECT COUNT(*) FROM investimento_midia").fetchone()[0],
            "leads": conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
            "vendas": conn.execute("SELECT COUNT(*) FROM vendas").fetchone()[0],
        }

        assert counts["investimento_midia"] == len(midia), "divergência ao carregar investimento_midia.csv"
        assert counts["leads"] == len(leads), "divergência ao carregar leads.csv"
        assert counts["vendas"] == len(vendas), "divergência ao carregar vendas.csv"

        return counts
    finally:
        conn.close()


if __name__ == "__main__":
    result = build()
    print(f"Banco criado em {DB_PATH.relative_to(REPO_ROOT)}")
    for table, n in result.items():
        print(f"  {table}: {n} linhas")
