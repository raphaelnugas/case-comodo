import json

import pytest

from src.parte3_prevendas.avaliar_qualidade import avaliar_amostra
from src.parte3_prevendas.export_markdown import formatar_conversa
from src.parte3_prevendas.gemini_client import GeminiIndisponivel, gerar_classificacao
from src.parte3_prevendas.validators import (
    parse_json_estrito,
    valida_evidencias_contra_conversa,
    valida_resposta_completa,
    valida_schema,
)

MENSAGENS = [
    {"numero": 1, "de": "lead", "texto": "Oi, vi voces no Google. Peguei as chaves do apto"},
    {"numero": 2, "de": "atendente", "texto": "Que otimo! Voce ja tem a planta?"},
    {"numero": 3, "de": "lead", "texto": "A gente separou uns 60 mil pros planejados"},
]

RESPOSTA_VALIDA = {
    "conversa_id": "CV001",
    "classificacao": "quente",
    "prioridade": 1,
    "resumo_para_o_vendedor": "Lead com orçamento definido e escopo claro.",
    "sinais": ["orçamento de 60 mil mencionado"],
    "evidencias": [{"numero_mensagem": 3, "trecho": "A gente separou uns 60 mil pros planejados"}],
    "proxima_acao": "Ligar hoje para agendar visita",
    "alertas": [],
    "revisao_humana_recomendada": False,
    "motivo_revisao_humana": None,
}


def test_parse_json_estrito_aceita_json_puro():
    dados, erro = parse_json_estrito(json.dumps(RESPOSTA_VALIDA))
    assert erro is None
    assert dados["conversa_id"] == "CV001"


def test_parse_json_estrito_remove_cercas_markdown():
    texto = "```json\n" + json.dumps(RESPOSTA_VALIDA) + "\n```"
    dados, erro = parse_json_estrito(texto)
    assert erro is None
    assert dados["classificacao"] == "quente"


def test_parse_json_estrito_rejeita_lixo():
    dados, erro = parse_json_estrito("isso nao e json de jeito nenhum")
    assert dados is None
    assert erro is not None


def test_valida_schema_aceita_resposta_correta():
    resultado = valida_schema(RESPOSTA_VALIDA, "CV001")
    assert resultado.ok, resultado.erros


def test_valida_schema_rejeita_classificacao_invalida():
    ruim = dict(RESPOSTA_VALIDA, classificacao="super_quente")
    resultado = valida_schema(ruim, "CV001")
    assert not resultado.ok
    assert any("classificacao" in e for e in resultado.erros)


def test_valida_schema_rejeita_campo_ausente():
    ruim = dict(RESPOSTA_VALIDA)
    del ruim["proxima_acao"]
    resultado = valida_schema(ruim, "CV001")
    assert not resultado.ok


def test_valida_schema_rejeita_conversa_id_trocado():
    resultado = valida_schema(RESPOSTA_VALIDA, "CV999")
    assert not resultado.ok


def test_valida_evidencias_aceita_trecho_real():
    resultado = valida_evidencias_contra_conversa(RESPOSTA_VALIDA, MENSAGENS)
    assert resultado.ok, resultado.erros


def test_valida_evidencias_rejeita_mensagem_inexistente():
    ruim = dict(RESPOSTA_VALIDA, evidencias=[{"numero_mensagem": 99, "trecho": "qualquer coisa"}])
    resultado = valida_evidencias_contra_conversa(ruim, MENSAGENS)
    assert not resultado.ok


def test_valida_evidencias_detecta_alucinacao():
    ruim = dict(
        RESPOSTA_VALIDA,
        evidencias=[{"numero_mensagem": 1, "trecho": "cliente disse que tem 500 mil reais disponiveis"}],
    )
    resultado = valida_evidencias_contra_conversa(ruim, MENSAGENS)
    assert not resultado.ok


def test_valida_resposta_completa_fluxo_feliz():
    dados, resultado = valida_resposta_completa(json.dumps(RESPOSTA_VALIDA), "CV001", MENSAGENS)
    assert resultado.ok
    assert dados["classificacao"] == "quente"


class ClienteFalso:
    """Simula o client do google-genai sem chamar rede de verdade."""

    def __init__(self, comportamentos):
        # comportamentos: lista de callables(modelo) -> texto | levanta exceção
        self._comportamentos = list(comportamentos)
        self.chamadas = []
        self.models = self

    def generate_content(self, model, contents, config):
        self.chamadas.append(model)
        comportamento = self._comportamentos.pop(0)
        return comportamento(model)


def _resposta_ok(texto):
    def _f(modelo):
        class R:
            pass

        r = R()
        r.text = texto
        return r

    return _f


def _falha(msg="erro simulado"):
    def _f(modelo):
        raise RuntimeError(msg)

    return _f


def test_gerar_classificacao_usa_modelo_principal_quando_funciona(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash")

    cliente = ClienteFalso([_resposta_ok('{"ok": true}')])
    resposta = gerar_classificacao(
        prompt="p", api_key="fake", cliente_factory=lambda: cliente, max_tentativas_por_modelo=2, backoff_inicial_s=0
    )
    assert resposta.modelo_usado == "gemini-3.6-flash"
    assert resposta.texto == '{"ok": true}'
    assert cliente.chamadas == ["gemini-3.6-flash"]


def test_gerar_classificacao_cai_para_fallback_quando_principal_falha(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash")

    cliente = ClienteFalso([_falha(), _falha(), _resposta_ok('{"ok": true}')])
    resposta = gerar_classificacao(
        prompt="p", api_key="fake", cliente_factory=lambda: cliente, max_tentativas_por_modelo=2, backoff_inicial_s=0
    )
    assert resposta.modelo_usado == "gemini-2.5-flash"
    assert cliente.chamadas == ["gemini-3.6-flash", "gemini-3.6-flash", "gemini-2.5-flash"]


def test_gerar_classificacao_levanta_gemini_indisponivel_quando_tudo_falha(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash")

    cliente = ClienteFalso([_falha(), _falha()])
    with pytest.raises(GeminiIndisponivel):
        gerar_classificacao(
            prompt="p", api_key="fake", cliente_factory=lambda: cliente, max_tentativas_por_modelo=1, backoff_inicial_s=0
        )


def test_avaliar_amostra_calcula_concordancia_e_matriz():
    humanos = [
        {"conversa_id": "CV001", "classificacao": "quente"},
        {"conversa_id": "CV002", "classificacao": "frio"},
        {"conversa_id": "CV003", "classificacao": "quente"},
    ]
    modelo = [
        {"conversa_id": "CV001", "classificacao": "quente"},
        {"conversa_id": "CV002", "classificacao": "frio"},
        {"conversa_id": "CV003", "classificacao": "frio"},  # erro crítico: quente -> frio
    ]

    metricas = avaliar_amostra(humanos, modelo)
    assert metricas.total_avaliado == 3
    assert round(metricas.concordancia_geral, 3) == round(2 / 3, 3)
    assert metricas.matriz_confusao["quente"]["frio"] == 1
    assert len(metricas.casos_criticos) == 1
    assert metricas.casos_criticos[0]["conversa_id"] == "CV003"


def test_avaliar_amostra_ignora_conversas_sem_classificacao_do_modelo():
    humanos = [{"conversa_id": "CV001", "classificacao": "quente"}]
    modelo = []  # ex.: falha técnica, não entrou na métrica
    metricas = avaliar_amostra(humanos, modelo)
    assert metricas.total_avaliado == 0
    assert metricas.concordancia_geral == 0.0


CONVERSA_CV001 = {"conversa_id": "CV001", "campanha_id": "cmp_004", "mensagens": MENSAGENS}


def test_formatar_conversa_inclui_evidencias_e_dialogo_original():
    resultado = dict(
        RESPOSTA_VALIDA,
        status="classificado",
        modelo_usado="gemini-3.6-flash",
        classificado_em="2026-09-12T21:01:32.890078+00:00",
    )
    md = formatar_conversa(resultado, CONVERSA_CV001)

    assert "CV001" in md
    assert "QUENTE" in md
    assert "gemini-3.6-flash" in md
    assert "orçamento de 60 mil mencionado" in md
    assert "[3]` \"A gente separou uns 60 mil pros planejados\"" in md
    assert "Diálogo original completo" in md
    assert "A gente separou uns 60 mil pros planejados" in md  # mensagem 3 no diálogo


def test_formatar_conversa_falha_tecnica_nao_mostra_classificacao():
    resultado = {
        "conversa_id": "CV001",
        "status": "falha_tecnica",
        "erro": "todas as tentativas falharam",
        "motivo_revisao_humana": "falha técnica na classificação automática",
    }
    md = formatar_conversa(resultado, CONVERSA_CV001)

    assert "falha técnica" in md.lower()
    assert "QUENTE" not in md and "FRIO" not in md
    assert "todas as tentativas falharam" in md
