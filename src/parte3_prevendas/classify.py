"""
Parte 3 | Classifica as conversas de pré-vendas com o Gemini.

Uso:
    python -m src.parte3_prevendas.classify
    python -m src.parte3_prevendas.classify --force   # ignora checkpoints e reclassifica tudo

Cada conversa é salva como checkpoint individual em data/output/checkpoints/{id}.json
assim que processada — se o script cair no meio (ou for interrompido), rodar de novo
retoma de onde parou em vez de gastar chamadas de API repetindo o que já deu certo.

Importante: falha técnica (erro de rede, API fora do ar, JSON que não valida mesmo
após correção) NUNCA é gravada como classificação "frio" — vira um registro com
status "falha_tecnica", sinalizado para revisão humana. Ver DECISOES_TECNICAS.md.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from src.parte3_prevendas.gemini_client import GeminiIndisponivel, gerar_classificacao
from src.parte3_prevendas.validators import valida_resposta_completa

REPO_ROOT = Path(__file__).resolve().parents[2]
DADOS_PATH = REPO_ROOT / "dados" / "conversas_prevendas.json"
PROMPT_PATH = REPO_ROOT / "prompts" / "prompt_classificacao_prevendas.txt"
CHECKPOINTS_DIR = REPO_ROOT / "data" / "output" / "checkpoints"
OUTPUT_PATH = REPO_ROOT / "data" / "output" / "classificacoes_prevendas.json"
WEB_PUBLIC_DATA_DIR = REPO_ROOT / "web" / "public" / "data"

MAX_RODADAS_VALIDACAO = 2  # 1 tentativa + 1 correção

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stdout)
log = logging.getLogger("classify_prevendas")


def numerar_mensagens(conversa: dict) -> list[dict]:
    return [
        {"numero": i + 1, "de": m["de"], "texto": m["texto"]}
        for i, m in enumerate(conversa["mensagens"])
    ]


def formatar_conversa(mensagens_numeradas: list[dict]) -> str:
    linhas = []
    for m in mensagens_numeradas:
        linhas.append(f"[{m['numero']}] {m['de'].upper()}: {m['texto']}")
    return "\n".join(linhas)


def montar_prompt(template: str, conversa_id: str, conversa_formatada: str) -> str:
    return template.replace("{conversa_id}", conversa_id).replace("{conversa_formatada}", conversa_formatada)


def classificar_conversa(conversa: dict, template: str, api_key: str) -> dict:
    conversa_id = conversa["conversa_id"]
    mensagens_numeradas = numerar_mensagens(conversa)
    conversa_formatada = formatar_conversa(mensagens_numeradas)
    prompt = montar_prompt(template, conversa_id, conversa_formatada)

    ultimo_erro_tecnico: str | None = None
    ultimo_resultado_validacao = None
    ultimo_dados_brutos = None
    modelo_usado = None
    tentativas_totais = 0

    for rodada in range(1, MAX_RODADAS_VALIDACAO + 1):
        try:
            resposta = gerar_classificacao(prompt=prompt, api_key=api_key)
        except GeminiIndisponivel as exc:
            ultimo_erro_tecnico = str(exc)
            break

        modelo_usado = resposta.modelo_usado
        tentativas_totais += resposta.tentativas_totais

        dados, validacao = valida_resposta_completa(resposta.texto, conversa_id, mensagens_numeradas)
        ultimo_resultado_validacao = validacao
        ultimo_dados_brutos = dados

        if validacao.ok:
            return {
                "conversa_id": conversa_id,
                "status": "classificado",
                "avisos_validacao": validacao.avisos,
                "modelo_usado": modelo_usado,
                "tentativas_totais": tentativas_totais,
                "classificado_em": datetime.now(timezone.utc).isoformat(),
                **dados,
            }

        log.warning("Conversa %s: validação falhou na rodada %d: %s", conversa_id, rodada, validacao.erros)
        prompt = (
            prompt
            + "\n\nSUA RESPOSTA ANTERIOR FOI REJEITADA PELOS SEGUINTES MOTIVOS:\n- "
            + "\n- ".join(validacao.erros)
            + "\n\nCorrija e responda de novo APENAS com o objeto JSON correto, seguindo o schema."
        )

    erro_final = ultimo_erro_tecnico or (
        f"JSON retornado não passou na validação após {MAX_RODADAS_VALIDACAO} rodada(s): "
        f"{ultimo_resultado_validacao.erros if ultimo_resultado_validacao else 'erro desconhecido'}"
    )
    return {
        "conversa_id": conversa_id,
        "status": "falha_tecnica",
        "classificacao": None,
        "erro": erro_final,
        "resposta_bruta_ultima_tentativa": ultimo_dados_brutos,
        "revisao_humana_recomendada": True,
        "motivo_revisao_humana": "Falha técnica na classificação automática — ver campo 'erro'. NÃO tratar como lead frio.",
        "modelo_usado": modelo_usado,
        "tentativas_totais": tentativas_totais,
        "classificado_em": datetime.now(timezone.utc).isoformat(),
    }


def carregar_checkpoint(conversa_id: str) -> dict | None:
    path = CHECKPOINTS_DIR / f"{conversa_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def salvar_checkpoint(resultado: dict) -> None:
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHECKPOINTS_DIR / f"{resultado['conversa_id']}.json"
    path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")


def run(forcar: bool = False) -> list[dict]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit(
            "GEMINI_API_KEY não definido. Copie .env.example para .env e preencha a chave "
            "(https://aistudio.google.com/apikey)."
        )

    conversas = json.loads(DADOS_PATH.read_text(encoding="utf-8"))
    template = PROMPT_PATH.read_text(encoding="utf-8")

    resultados = []
    for conversa in conversas:
        conversa_id = conversa["conversa_id"]

        if not forcar:
            existente = carregar_checkpoint(conversa_id)
            if existente and existente.get("status") == "classificado":
                log.info("Conversa %s já classificada (checkpoint) — pulando.", conversa_id)
                resultados.append(existente)
                continue

        log.info("Classificando %s...", conversa_id)
        resultado = classificar_conversa(conversa, template, api_key)
        salvar_checkpoint(resultado)
        resultados.append(resultado)

        if resultado["status"] == "falha_tecnica":
            log.error("Conversa %s: falha técnica — %s", conversa_id, resultado["erro"])
        else:
            log.info(
                "Conversa %s: %s (prioridade %s, modelo %s)",
                conversa_id,
                resultado["classificacao"],
                resultado.get("prioridade"),
                resultado.get("modelo_usado"),
            )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")

    WEB_PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (WEB_PUBLIC_DATA_DIR / "classificacoes_prevendas.json").write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (WEB_PUBLIC_DATA_DIR / "conversas_prevendas.json").write_text(
        DADOS_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )

    sucesso = sum(1 for r in resultados if r["status"] == "classificado")
    falhas = sum(1 for r in resultados if r["status"] == "falha_tecnica")
    log.info("Concluído: %d classificadas, %d com falha técnica, de %d conversas.", sucesso, falhas, len(resultados))

    return resultados


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Ignora checkpoints e reclassifica tudo.")
    args = parser.parse_args()
    run(forcar=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
