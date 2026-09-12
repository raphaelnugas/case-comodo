import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.parte1_github.collect_repos import (
    SingleInstanceLock,
    normalize_repo,
    run,
    sha256_of_file,
)

REPO_AMOSTRA = {
    "name": "airflow",
    "description": "Workflow orchestration",
    "language": "Python",
    "stargazers_count": 100,
    "forks_count": 20,
    "created_at": "2015-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


def test_normalize_repo_extrai_campos_esperados():
    r = normalize_repo(REPO_AMOSTRA)
    assert r == {
        "nome": "airflow",
        "descricao": "Workflow orchestration",
        "linguagem_principal": "Python",
        "estrelas": 100,
        "forks": 20,
        "criado_em": "2015-01-01T00:00:00Z",
        "atualizado_em": "2026-01-01T00:00:00Z",
    }


def test_normalize_repo_lida_com_campos_ausentes():
    r = normalize_repo({"name": "x"})
    assert r["descricao"] == ""
    assert r["linguagem_principal"] == "não informado"
    assert r["estrelas"] == 0


def test_sha256_of_file_e_deterministico(tmp_path: Path):
    f = tmp_path / "a.csv"
    f.write_text("nome,estrelas\nfoo,1\n", encoding="utf-8")
    h1 = sha256_of_file(f)
    h2 = sha256_of_file(f)
    assert h1 == h2
    assert len(h1) == 64


def test_lock_impede_execucao_simultanea(tmp_path: Path):
    lock_path = tmp_path / "lock.pid"
    with SingleInstanceLock(lock_path):
        with pytest.raises(RuntimeError):
            with SingleInstanceLock(lock_path):
                pass
    # depois de sair do primeiro `with`, o lock é liberado
    with SingleInstanceLock(lock_path):
        pass


def test_lock_obsoleto_e_removido_automaticamente(tmp_path: Path):
    lock_path = tmp_path / "lock.pid"
    lock_path.write_text("99999", encoding="utf-8")
    old_time = time.time() - 3600
    import os

    os.utime(lock_path, (old_time, old_time))

    with SingleInstanceLock(lock_path, stale_after=60):
        assert lock_path.exists()


def _resposta(payload, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    return resp


def test_run_pagina_ate_esgotar_e_grava_csv_e_status(tmp_path: Path):
    pagina1 = [dict(REPO_AMOSTRA, name=f"repo{i}") for i in range(100)]
    pagina2 = [dict(REPO_AMOSTRA, name="repo100")]

    with patch("src.parte1_github.collect_repos.build_session") as mock_build_session:
        session = MagicMock()
        mock_build_session.return_value = session

        session.get.side_effect = [
            _resposta({"public_repos": 101}),  # fetch_org_public_repo_count
            _resposta(pagina1),  # página 1
            _resposta(pagina2),  # página 2
            _resposta([]),  # página 3 vazia -> nunca deveria ser chamada pois pagina2 < PER_PAGE
        ]

        status = run(org="apache-teste", output_dir=tmp_path)

    assert status.status == "sucesso"
    assert status.records_collected == 101
    assert status.pages_fetched == 2
    assert status.csv_sha256 is not None

    status_json = json.loads((tmp_path / "github_collection_status.json").read_text(encoding="utf-8"))
    assert status_json["registros_processados"] == 101
    assert status_json["status"] == "sucesso"

    csv_path = tmp_path / "github_repos_apache-teste.csv"
    linhas = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 1 + 101  # cabeçalho + registros


def test_run_limpa_arquivo_temporario_quando_falha_no_meio_da_paginacao(tmp_path: Path):
    pagina1 = [dict(REPO_AMOSTRA, name=f"repo{i}") for i in range(100)]

    with patch("src.parte1_github.collect_repos.build_session") as mock_build_session:
        session = MagicMock()
        mock_build_session.return_value = session
        session.get.side_effect = [
            _resposta({"public_repos": 150}),
            _resposta(pagina1),
            requests.exceptions.ConnectionError("falha simulada de rede na página 2"),
        ]

        status = run(org="apache-teste", output_dir=tmp_path)

    assert status.status == "erro"
    assert not (tmp_path / "github_repos_apache-teste.csv.tmp").exists()
    assert not (tmp_path / "github_repos_apache-teste.csv").exists()


def test_run_registra_erro_quando_org_nao_existe(tmp_path: Path):
    with patch("src.parte1_github.collect_repos.build_session") as mock_build_session:
        session = MagicMock()
        mock_build_session.return_value = session
        resp_404 = MagicMock(status_code=404)
        session.get.side_effect = [_resposta({"public_repos": None}), resp_404]

        status = run(org="org-inexistente-xyz", output_dir=tmp_path)

    assert status.status == "erro"
    assert status.error is not None
    status_json = json.loads((tmp_path / "github_collection_status.json").read_text(encoding="utf-8"))
    assert status_json["status"] == "erro"
