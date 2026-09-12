"""
Parte 1 | Coleta automática de repositórios públicos de uma organização no GitHub.

Uso:
    python -m src.parte1_github.collect_repos
    python -m src.parte1_github.collect_repos --org apache

Variáveis de ambiente (ver .env.example):
    GITHUB_TOKEN            Personal Access Token (opcional, mas recomendado).
    GITHUB_ORG              Organização alvo (default: "apache").

Este script:
    1. Autentica via variável de ambiente (nunca via argumento de linha de comando
       ou valor hardcoded — evita o token aparecer em `ps`, histórico de shell ou logs).
    2. Pagina a API pública do GitHub até esgotar os resultados.
    3. Extrai nome, descrição, linguagem principal, estrelas, forks,
       data de criação e data de atualização de cada repositório.
    4. Valida a quantidade de repositórios antes (campo `public_repos` da org)
       e depois da coleta (linhas efetivamente escritas), registrando divergências.
    5. Grava os dados em CSV e um arquivo de status (JSON) com hash SHA-256 do CSV.
    6. Usa um lock file para impedir execuções simultâneas (ex.: cron + disparo manual).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "data" / "output"
WEB_PUBLIC_DATA_DIR = REPO_ROOT / "web" / "public" / "data"
LOCK_PATH = OUTPUT_DIR / ".collect_github.lock"
STALE_LOCK_SECONDS = 30 * 60  # trava considerada travada (processo morto) após 30 min

GITHUB_API = "https://api.github.com"
PER_PAGE = 100
REQUEST_TIMEOUT = 15  # segundos
MAX_RETRIES = 4

CSV_FIELDS = [
    "nome",
    "descricao",
    "linguagem_principal",
    "estrelas",
    "forks",
    "criado_em",
    "atualizado_em",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("collect_github_repos")


class SingleInstanceLock:
    """Impede duas execuções simultâneas do script (ex.: cron atrasado + disparo manual)."""

    def __init__(self, path: Path, stale_after: int = STALE_LOCK_SECONDS):
        self.path = path
        self.stale_after = stale_after
        self._acquired = False

    def __enter__(self) -> "SingleInstanceLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            age = time.time() - self.path.stat().st_mtime
            if age < self.stale_after:
                raise RuntimeError(
                    f"Já existe uma coleta em andamento (lock criado há {age:.0f}s "
                    f"em {self.path}). Aguarde terminar ou remova o arquivo se ele "
                    f"estiver travado por um processo morto."
                )
            log.warning("Lock encontrado com %.0fs de idade — considerado obsoleto, removendo.", age)
            self.path.unlink(missing_ok=True)

        self.path.write_text(str(os.getpid()), encoding="utf-8")
        self._acquired = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._acquired and self.path.exists():
            self.path.unlink(missing_ok=True)


def determinar_origem_execucao() -> str:
    """Distingue o disparo agendado (cron 6h) de um disparo manual, via a variável
    que o GitHub Actions preenche automaticamente (`GITHUB_EVENT_NAME`). Rodando
    localmente (sem essa variável), é sempre 'manual_local'. Isso é o que permite à
    interface tratar um erro do cron das 6h como algo a alarmar de verdade, e um erro
    de uma execução manual (ex.: um teste local sem token) como algo bem menos grave."""
    evento = os.environ.get("GITHUB_EVENT_NAME")
    if evento == "schedule":
        return "agendado"
    if evento:
        return "manual_actions"  # workflow_dispatch, ou outro evento do Actions
    return "manual_local"


@dataclass
class CollectionStatus:
    org: str
    started_at: str
    finished_at: str | None = None
    duration_seconds: float | None = None
    pages_fetched: int = 0
    records_expected: int | None = None
    records_collected: int = 0
    status: str = "em_andamento"  # sucesso | erro | sucesso_com_divergencia
    error: str | None = None
    csv_path: str | None = None
    csv_sha256: str | None = None
    execution_origin: str = field(default_factory=determinar_origem_execucao)

    def to_json(self) -> dict:
        return {
            "organizacao": self.org,
            "inicio": self.started_at,
            "fim": self.finished_at,
            "duracao_segundos": self.duration_seconds,
            "paginas_percorridas": self.pages_fetched,
            "registros_esperados": self.records_expected,
            "registros_processados": self.records_collected,
            "status": self.status,
            "erro": self.error,
            "arquivo_csv": self.csv_path,
            "sha256_csv": self.csv_sha256,
            "origem_execucao": self.execution_origin,
        }


def build_session(token: str | None) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=1.5,
        status_forcelist=[403, 429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "case-comodo-github-collector",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    session.headers.update(headers)
    return session


def fetch_org_public_repo_count(session: requests.Session, org: str) -> int | None:
    """Consulta o total de repositórios públicos declarado pela própria org (para validação)."""
    try:
        resp = session.get(f"{GITHUB_API}/orgs/{org}", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("public_repos")
    except requests.RequestException as exc:
        log.warning("Não foi possível obter contagem oficial de repositórios da org: %s", exc)
        return None


def iter_org_repos(session: requests.Session, org: str, status: CollectionStatus) -> Iterator[dict]:
    """Percorre todas as páginas de /orgs/{org}/repos até a última página vazia."""
    page = 1
    while True:
        resp = session.get(
            f"{GITHUB_API}/orgs/{org}/repos",
            params={"type": "public", "per_page": PER_PAGE, "page": page, "sort": "full_name"},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 404:
            raise RuntimeError(f"Organização '{org}' não encontrada (404).")
        resp.raise_for_status()

        batch = resp.json()
        status.pages_fetched = page
        if not batch:
            break

        for repo in batch:
            yield repo

        log.info("Página %d: %d repositórios coletados nesta página.", page, len(batch))

        if len(batch) < PER_PAGE:
            break
        page += 1


def normalize_repo(repo: dict) -> dict:
    return {
        "nome": repo.get("name", ""),
        "descricao": (repo.get("description") or "").replace("\n", " ").strip(),
        "linguagem_principal": repo.get("language") or "não informado",
        "estrelas": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "criado_em": repo.get("created_at", ""),
        "atualizado_em": repo.get("updated_at", ""),
    }


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_status(status: CollectionStatus, status_path: Path) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        json.dumps(status.to_json(), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def run(org: str, output_dir: Path = OUTPUT_DIR) -> CollectionStatus:
    token = os.environ.get("GITHUB_TOKEN") or None
    if not token:
        log.warning(
            "GITHUB_TOKEN não definido — a coleta seguirá sem autenticação "
            "(limite de 60 req/hora em vez de 5000). Nunca hardcode o token no código."
        )

    started_at = datetime.now(timezone.utc)
    status = CollectionStatus(org=org, started_at=started_at.isoformat())

    csv_path = output_dir / f"github_repos_{org}.csv"
    status_path = output_dir / "github_collection_status.json"

    session = build_session(token)

    try:
        status.records_expected = fetch_org_public_repo_count(session, org)

        output_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = csv_path.with_suffix(".csv.tmp")
        collected = 0
        with tmp_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for repo in iter_org_repos(session, org, status):
                writer.writerow(normalize_repo(repo))
                collected += 1

        tmp_path.replace(csv_path)
        status.records_collected = collected
        try:
            status.csv_path = csv_path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            status.csv_path = csv_path.as_posix()
        status.csv_sha256 = sha256_of_file(csv_path)

        if status.records_expected is not None and status.records_expected != collected:
            status.status = "sucesso_com_divergencia"
            status.error = (
                f"A org relata {status.records_expected} repositórios públicos, "
                f"mas {collected} foram coletados. Pode ser diferença momentânea "
                f"(repos criados/removidos durante a coleta) ou repositórios que "
                f"exigem condições especiais de visibilidade."
            )
            log.warning(status.error)
        else:
            status.status = "sucesso"

        log.info(
            "Coleta concluída: %d repositórios em %d página(s) — hash %s",
            collected,
            status.pages_fetched,
            status.csv_sha256[:12] + "...",
        )

    except Exception as exc:  # noqa: BLE001 - queremos registrar qualquer falha no status
        status.status = "erro"
        status.error = str(exc)
        log.error("Falha na coleta: %s", exc)
        tmp_path = output_dir / f"github_repos_{org}.csv.tmp"
        tmp_path.unlink(missing_ok=True)

    finally:
        finished_at = datetime.now(timezone.utc)
        status.finished_at = finished_at.isoformat()
        status.duration_seconds = round((finished_at - started_at).total_seconds(), 2)
        write_status(status, status_path)
        if output_dir == OUTPUT_DIR:
            _espelhar_para_web(status_path, csv_path if csv_path.exists() else None)

    return status


def _espelhar_para_web(status_path: Path, csv_path: Path | None) -> None:
    """Copia os artefatos para web/public/data, para o React consumir sem backend rodando."""
    try:
        WEB_PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
        (WEB_PUBLIC_DATA_DIR / status_path.name).write_bytes(status_path.read_bytes())
        if csv_path is not None:
            (WEB_PUBLIC_DATA_DIR / csv_path.name).write_bytes(csv_path.read_bytes())
    except OSError as exc:
        log.warning("Não foi possível espelhar artefatos para %s: %s", WEB_PUBLIC_DATA_DIR, exc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--org",
        default=os.environ.get("GITHUB_ORG", "apache"),
        help="Organização do GitHub a coletar (default: variável GITHUB_ORG ou 'apache').",
    )
    args = parser.parse_args()

    try:
        with SingleInstanceLock(LOCK_PATH):
            status = run(args.org)
    except RuntimeError as exc:
        log.error(str(exc))
        return 1

    if status.status == "erro":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
