"""
Ferramenta de avaliação de qualidade da classificação — pensada para o cenário descrito
no case: "daqui a três meses, com 4.000 conversas processadas, como saber se a
classificação está funcionando bem?"

A resposta operacional está no README/DECISOES_TECNICAS.md. Este módulo é a peça de
código que sustenta essa resposta: dado um lote de conversas onde um humano também
classificou uma amostra (ex.: 5% de 4.000 = ~200 conversas revisadas por semana),
calcula taxa de concordância, matriz de confusão por classe e destaca os casos de
maior risco (o modelo disse "frio" e o humano disse "quente", ou vice-versa).

Uso típico (fora deste case, quando houver rótulos humanos reais):
    from src.parte3_prevendas.avaliar_qualidade import avaliar_amostra
    metricas = avaliar_amostra(rotulos_humanos, classificacoes_modelo)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

CLASSES = ["quente", "morno", "frio", "fora_do_perfil"]

# Confundir "quente" com "frio" (ou vice-versa) custa uma venda perdida ou um vendedor
# perdendo tempo — é o erro que mais importa monitorar de perto.
PARES_CRITICOS = {("quente", "frio"), ("frio", "quente"), ("quente", "fora_do_perfil")}


@dataclass
class MetricasAvaliacao:
    total_avaliado: int
    concordancia_geral: float
    concordancia_por_classe: dict[str, float]
    matriz_confusao: dict[str, dict[str, int]]
    casos_criticos: list[dict] = field(default_factory=list)


def avaliar_amostra(rotulos_humanos: list[dict], classificacoes_modelo: list[dict]) -> MetricasAvaliacao:
    """
    rotulos_humanos / classificacoes_modelo: listas de dicts com pelo menos
    {"conversa_id": str, "classificacao": str}. São casadas por conversa_id.
    """
    modelo_por_id = {c["conversa_id"]: c["classificacao"] for c in classificacoes_modelo}

    matriz: dict[str, dict[str, int]] = {c: {c2: 0 for c2 in CLASSES} for c in CLASSES}
    acertos_por_classe: Counter = Counter()
    total_por_classe: Counter = Counter()
    casos_criticos: list[dict] = []
    total = 0
    acertos = 0

    for rotulo in rotulos_humanos:
        conversa_id = rotulo["conversa_id"]
        verdade = rotulo["classificacao"]
        predito = modelo_por_id.get(conversa_id)

        if predito is None or verdade not in CLASSES or predito not in CLASSES:
            continue  # conversa sem classificação do modelo (ex.: falha técnica) fica fora da métrica de acurácia

        total += 1
        total_por_classe[verdade] += 1
        matriz[verdade][predito] += 1

        if predito == verdade:
            acertos += 1
            acertos_por_classe[verdade] += 1
        elif (verdade, predito) in PARES_CRITICOS:
            casos_criticos.append({"conversa_id": conversa_id, "verdade": verdade, "predito": predito})

    concordancia_por_classe = {
        c: round(acertos_por_classe[c] / total_por_classe[c], 3) if total_por_classe[c] else None
        for c in CLASSES
    }

    return MetricasAvaliacao(
        total_avaliado=total,
        concordancia_geral=round(acertos / total, 3) if total else 0.0,
        concordancia_por_classe=concordancia_por_classe,
        matriz_confusao=matriz,
        casos_criticos=casos_criticos,
    )
