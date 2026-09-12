"""Validação do JSON devolvido pelo LLM: schema, tipos e evidências reais."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field

CLASSIFICACOES_VALIDAS = {"quente", "morno", "frio", "fora_do_perfil"}

CAMPOS_OBRIGATORIOS = {
    "conversa_id": str,
    "classificacao": str,
    "prioridade": int,
    "resumo_para_o_vendedor": str,
    "sinais": list,
    "evidencias": list,
    "proxima_acao": str,
    "alertas": list,
    "revisao_humana_recomendada": bool,
}


@dataclass
class ResultadoValidacao:
    ok: bool
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _normaliza(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto.lower().strip()


def parse_json_estrito(texto_bruto: str) -> tuple[dict | None, str | None]:
    """Tenta interpretar a resposta do modelo como JSON, tolerando cercas ```json e texto solto."""
    candidato = texto_bruto.strip()
    if candidato.startswith("```"):
        candidato = candidato.strip("`")
        if candidato.lower().startswith("json"):
            candidato = candidato[4:]
        candidato = candidato.strip()

    inicio = candidato.find("{")
    fim = candidato.rfind("}")
    if inicio == -1 or fim == -1 or fim < inicio:
        return None, "Nenhum objeto JSON encontrado na resposta do modelo."
    candidato = candidato[inicio : fim + 1]

    try:
        return json.loads(candidato), None
    except json.JSONDecodeError as exc:
        return None, f"JSON inválido: {exc}"


def valida_schema(dados: dict, conversa_id_esperado: str) -> ResultadoValidacao:
    erros: list[str] = []
    avisos: list[str] = []

    for campo, tipo in CAMPOS_OBRIGATORIOS.items():
        if campo not in dados:
            erros.append(f"Campo obrigatório ausente: '{campo}'")
            continue
        if not isinstance(dados[campo], tipo):
            erros.append(f"Campo '{campo}' deveria ser {tipo.__name__}, veio {type(dados[campo]).__name__}")

    if erros:
        return ResultadoValidacao(ok=False, erros=erros, avisos=avisos)

    if dados["conversa_id"] != conversa_id_esperado:
        erros.append(
            f"conversa_id devolvido ('{dados['conversa_id']}') não bate com o esperado ('{conversa_id_esperado}')"
        )

    if dados["classificacao"] not in CLASSIFICACOES_VALIDAS:
        erros.append(
            f"classificacao '{dados['classificacao']}' inválida — deve ser uma de {sorted(CLASSIFICACOES_VALIDAS)}"
        )

    if not (1 <= dados["prioridade"] <= 4):
        avisos.append(f"prioridade {dados['prioridade']} fora do intervalo esperado (1 a 4)")

    if "motivo_revisao_humana" not in dados:
        erros.append("Campo obrigatório ausente: 'motivo_revisao_humana'")
    elif dados["revisao_humana_recomendada"] and not dados.get("motivo_revisao_humana"):
        avisos.append("revisao_humana_recomendada=true mas motivo_revisao_humana está vazio")

    for i, ev in enumerate(dados.get("evidencias", [])):
        if not isinstance(ev, dict) or "numero_mensagem" not in ev or "trecho" not in ev:
            erros.append(f"evidencias[{i}] mal formada — precisa de 'numero_mensagem' e 'trecho'")

    return ResultadoValidacao(ok=not erros, erros=erros, avisos=avisos)


def valida_evidencias_contra_conversa(dados: dict, mensagens_numeradas: list[dict]) -> ResultadoValidacao:
    """Confirma que cada evidência aponta pra uma mensagem que existe e que o trecho
    citado tem correspondência real no texto daquela mensagem (evita alucinação)."""
    erros: list[str] = []
    avisos: list[str] = []

    por_numero = {m["numero"]: m["texto"] for m in mensagens_numeradas}

    for i, ev in enumerate(dados.get("evidencias", [])):
        numero = ev.get("numero_mensagem")
        trecho = ev.get("trecho", "")

        if numero not in por_numero:
            erros.append(f"evidencias[{i}]: mensagem número {numero} não existe nesta conversa")
            continue

        texto_original = _normaliza(por_numero[numero])
        trecho_normalizado = _normaliza(trecho)

        if not trecho_normalizado:
            avisos.append(f"evidencias[{i}]: trecho vazio para a mensagem {numero}")
        elif trecho_normalizado not in texto_original:
            palavras = [p for p in trecho_normalizado.split() if len(p) > 3]
            sobrepostas = sum(1 for p in palavras if p in texto_original)
            if not palavras or sobrepostas / len(palavras) < 0.5:
                erros.append(
                    f"evidencias[{i}]: trecho citado não corresponde ao texto da mensagem {numero} "
                    f"(possível alucinação)"
                )
            else:
                avisos.append(
                    f"evidencias[{i}]: trecho citado é uma paráfrase da mensagem {numero}, não uma cópia literal"
                )

    return ResultadoValidacao(ok=not erros, erros=erros, avisos=avisos)


def valida_resposta_completa(texto_bruto: str, conversa_id: str, mensagens_numeradas: list[dict]) -> tuple[dict | None, ResultadoValidacao]:
    dados, erro_parse = parse_json_estrito(texto_bruto)
    if dados is None:
        return None, ResultadoValidacao(ok=False, erros=[erro_parse or "falha ao interpretar JSON"])

    r1 = valida_schema(dados, conversa_id)
    if not r1.ok:
        return dados, r1

    r2 = valida_evidencias_contra_conversa(dados, mensagens_numeradas)
    return dados, ResultadoValidacao(ok=r1.ok and r2.ok, erros=r1.erros + r2.erros, avisos=r1.avisos + r2.avisos)
