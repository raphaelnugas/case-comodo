"""Cliente Gemini com retry por modelo e fallback entre modelos.

Isolado num módulo próprio para poder ser mockado nos testes sem precisar de rede
nem de GEMINI_API_KEY.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

log = logging.getLogger("gemini_client")


class GeminiIndisponivel(Exception):
    """Levantada quando todos os modelos (principal + fallbacks) falharam em todas as tentativas."""


@dataclass
class RespostaModelo:
    texto: str
    modelo_usado: str
    tentativas_totais: int


def _modelos_configurados() -> list[str]:
    principal = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash").strip()
    fallbacks = [
        m.strip()
        for m in os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash,gemini-2.0-flash").split(",")
        if m.strip()
    ]
    ordem = [principal] + [m for m in fallbacks if m != principal]
    return ordem


def _chamar_modelo(client, modelo: str, prompt: str, timeout_s: int) -> str:
    from google.genai import types  # import local: evita exigir a lib se só rodarmos os testes com mock

    response = client.models.generate_content(
        model=modelo,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
            http_options=types.HttpOptions(timeout=timeout_s * 1000),
        ),
    )
    texto = getattr(response, "text", None)
    if not texto:
        raise RuntimeError(f"Resposta vazia do modelo {modelo}")
    return texto


def gerar_classificacao(
    prompt: str,
    api_key: str,
    max_tentativas_por_modelo: int = 3,
    backoff_inicial_s: float = 2.0,
    timeout_s: int = 30,
    cliente_factory=None,
) -> RespostaModelo:
    """Chama o Gemini com o modelo configurado; em caso de falha, tenta os fallbacks
    (nessa ordem), e dentro de cada modelo tenta `max_tentativas_por_modelo` vezes
    com backoff exponencial. Levanta GeminiIndisponivel só se TUDO falhar."""

    if cliente_factory is None:
        from google import genai

        cliente_factory = lambda: genai.Client(api_key=api_key)  # noqa: E731

    client = cliente_factory()
    erros: list[str] = []
    tentativas_totais = 0

    for modelo in _modelos_configurados():
        for tentativa in range(1, max_tentativas_por_modelo + 1):
            tentativas_totais += 1
            try:
                texto = _chamar_modelo(client, modelo, prompt, timeout_s)
                return RespostaModelo(texto=texto, modelo_usado=modelo, tentativas_totais=tentativas_totais)
            except Exception as exc:  # noqa: BLE001 - qualquer falha de rede/API deve acionar retry/fallback
                msg = f"modelo={modelo} tentativa={tentativa}: {exc}"
                log.warning("Falha ao chamar Gemini (%s)", msg)
                erros.append(msg)
                if tentativa < max_tentativas_por_modelo:
                    time.sleep(backoff_inicial_s * (2 ** (tentativa - 1)))

    raise GeminiIndisponivel(
        f"Todas as tentativas falharam ({tentativas_totais} no total) nos modelos "
        f"{_modelos_configurados()}. Últimos erros: {erros[-3:]}"
    )
