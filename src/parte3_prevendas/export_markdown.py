"""
Gera docs/RESULTADOS_PREVENDAS.md a partir de data/output/classificacoes_prevendas.json
— o resultado completo e legível de uma execução real da Parte 3, para quem só vai ler
o README e não vai abrir o React. Nunca escreva esse arquivo à mão: rode este script
de novo sempre que `classify.py` gerar um novo resultado.

Uso:
    python -m src.parte3_prevendas.export_markdown
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLASSIFICACOES_PATH = REPO_ROOT / "data" / "output" / "classificacoes_prevendas.json"
CONVERSAS_PATH = REPO_ROOT / "dados" / "conversas_prevendas.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "RESULTADOS_PREVENDAS.md"

EMOJI_CLASSIFICACAO = {
    "quente": "🔴",
    "morno": "🟡",
    "frio": "🔵",
    "fora_do_perfil": "⚪",
}


def formatar_conversa(item: dict, conversa: dict) -> str:
    if item["status"] == "falha_tecnica":
        linhas = [
            f"## {item['conversa_id']} — ⚠️ falha técnica (NÃO classificada como frio)",
            "",
            f"**Erro:** {item['erro']}",
            "",
            f"**Revisão humana recomendada:** sim — {item['motivo_revisao_humana']}",
            "",
        ]
        return "\n".join(linhas)

    emoji = EMOJI_CLASSIFICACAO.get(item["classificacao"], "")
    mensagens = conversa["mensagens"]

    linhas = [
        f"## {item['conversa_id']} — {emoji} {item['classificacao'].upper()} (prioridade {item['prioridade']})",
        "",
        f"*Campanha de origem: `{conversa.get('campanha_id', '—')}` · "
        f"classificado por `{item['modelo_usado']}` em {item['classificado_em'][:16].replace('T', ' ')} UTC*",
        "",
        f"**Resumo para o vendedor:** {item['resumo_para_o_vendedor']}",
        "",
        f"**Próxima ação recomendada:** {item['proxima_acao']}",
        "",
        "**Sinais observados:**",
    ]
    linhas += [f"- {s}" for s in item.get("sinais", [])]

    if item.get("alertas"):
        linhas += ["", "**Alertas:**"]
        linhas += [f"- ⚠️ {a}" for a in item["alertas"]]

    if item.get("revisao_humana_recomendada"):
        linhas += ["", f"**Revisão humana recomendada:** sim — {item.get('motivo_revisao_humana')}"]

    linhas += ["", "**Evidências (número da mensagem → trecho citado):**"]
    for ev in item.get("evidencias", []):
        linhas.append(f"- `[{ev['numero_mensagem']}]` \"{ev['trecho']}\"")

    linhas += ["", "<details>", "<summary>Diálogo original completo</summary>", ""]
    for i, m in enumerate(mensagens, start=1):
        linhas.append(f"`[{i}]` **{m['de']}:** {m['texto']}  ")
    linhas += ["", "</details>", ""]

    return "\n".join(linhas)


def main() -> None:
    classificacoes = json.loads(CLASSIFICACOES_PATH.read_text(encoding="utf-8"))
    conversas = {c["conversa_id"]: c for c in json.loads(CONVERSAS_PATH.read_text(encoding="utf-8"))}

    contagem = {}
    for item in classificacoes:
        chave = "falha_tecnica" if item["status"] == "falha_tecnica" else item["classificacao"]
        contagem[chave] = contagem.get(chave, 0) + 1

    cabecalho = [
        "# Resultados da Parte 3 — classificação de pré-vendas",
        "",
        "Saída completa e real de uma execução de "
        f"[`classify.py`](../src/parte3_prevendas/classify.py) contra o Gemini "
        "(`gemini-3.6-flash`) sobre as 15 conversas de `dados/conversas_prevendas.json`. "
        "Gerado automaticamente por "
        "[`export_markdown.py`](../src/parte3_prevendas/export_markdown.py) a partir de "
        "`data/output/classificacoes_prevendas.json` — **não é editado à mão**; para "
        "atualizar, rode `classify.py` e depois `export_markdown.py` de novo.",
        "",
        "As conversas são sintéticas e não têm vínculo individual garantido com "
        "`leads.csv`/`vendas.csv` — têm `campanha_id`, não `lead_id`. Ver "
        "[`README.md`](../README.md#parte-3--classificação-de-pré-vendas) e "
        "[`DECISOES_TECNICAS.md`](../DECISOES_TECNICAS.md#parte-3--classificação-de-pré-vendas) "
        "para os critérios de classificação e as garantias de validação.",
        "",
        "## Distribuição",
        "",
        "| Classificação | Conversas |",
        "|---|--:|",
    ]
    rotulos = {"quente": "🔴 Quente", "morno": "🟡 Morno", "frio": "🔵 Frio",
               "fora_do_perfil": "⚪ Fora do perfil", "falha_tecnica": "⚠️ Falha técnica"}
    for chave in ["quente", "morno", "frio", "fora_do_perfil", "falha_tecnica"]:
        if chave in contagem:
            cabecalho.append(f"| {rotulos[chave]} | {contagem[chave]} |")
    cabecalho += ["", "---", ""]

    corpo = [formatar_conversa(item, conversas[item["conversa_id"]]) for item in classificacoes]

    OUTPUT_PATH.write_text("\n".join(cabecalho) + "\n" + "\n\n---\n\n".join(corpo), encoding="utf-8")
    print(f"Gerado {OUTPUT_PATH.relative_to(REPO_ROOT)} com {len(classificacoes)} conversas.")


if __name__ == "__main__":
    main()
