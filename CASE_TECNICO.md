# Case Técnico | Desenvolvedor(a) Python Pleno | Automação, Dados e IA

Olá! Parabéns por avançar no processo.

Este case existe para vermos como você **constrói**. Não esperamos solução perfeita nem arquitetura sofisticada. Esperamos código que funciona, decisões justificadas e honestidade sobre os limites do que você fez.

---

## Escopo e tempo

**Não vamos definir quantas horas você deve gastar.** Decidir o que cabe no tempo disponível faz parte do trabalho, e é parte do que queremos observar.

Duas coisas que valem dizer com clareza:

- **Entrega maior não pontua mais.** Não avaliamos volume de código, quantidade de arquivos nem sofisticação de arquitetura. Um escopo bem cortado, com o que ficou de fora explicado no README, conta a favor;
- Se algum item não couber, **entregue o que tem e diga o que faltou e por quê.** Isso vale mais do que entregar tudo pela metade.

---

## Sobre o uso de IA

**Você pode usar Claude, GPT, Copilot ou qualquer outra ferramenta de IA à vontade.** Nós usamos todos os dias, seria estranho proibir.

Duas condições:

- No README, escreva uma seção curta dizendo **onde você usou IA e o que revisou depois**;
- Na próxima etapa, vamos abrir o seu repositório junto com você e conversar sobre as decisões técnicas em detalhe.

---

## Prazo e entrega

- **Prazo:** 5 dias corridos a partir do recebimento;
- **Formato:** repositório no GitHub (público, ou privado com acesso liberado para nós), contendo o código e um `README.md`;
- **Sem PDF e sem apresentação em slides.** O README é a sua documentação.

Se você não puder usar GitHub por qualquer motivo, envie um `.zip` e explique no e-mail.

---

## Parte 1 | Ingestão via API

A Cômodo consome dados de várias APIs de terceiros todos os dias. Queremos ver como você faz isso.

**Tarefa:** escreva um script Python que consuma a **API pública do GitHub** e extraia, para uma organização à sua escolha com mais de 200 repositórios (sugestões: `microsoft`, `google`, `vercel`, `apache`), os seguintes dados de **todos** os repositórios públicos:

- nome, descrição, linguagem principal, número de estrelas, número de forks, data de criação e data da última atualização.

O resultado deve ser gravado em um arquivo local (`.csv`, `.jsonl` ou SQLite, escolha e justifique no README).

**Contexto de operação, e ele importa para as suas decisões:**

> Considere que esse script vai rodar de forma automática, **todo dia às 6h da manhã, sem ninguém acompanhando a execução**, e que o arquivo gerado alimenta um relatório que alguém vai abrir às 9h.

**Requisitos:**

- O script precisa autenticar na API e trazer **todos** os repositórios da organização, não uma amostra;
- Ao final da execução, precisa ficar claro **quantos registros foram processados e se algo deu errado**.

*Observação sobre credenciais: a API do GitHub exige um token pessoal, que é gerado gratuitamente na sua conta. Se você optar por repositório público, lembre que todo o conteúdo commitado fica visível para qualquer pessoa. O cuidado com a sua própria credencial é de sua responsabilidade.*

---

## Os dados das partes 2 e 3

Junto com este documento você recebeu a pasta `dados/`, com quatro arquivos exportados dos sistemas que a Cômodo usa:

| Arquivo | Conteúdo |
|---|---|
| `investimento_midia.csv` | Gasto diário por campanha em Meta e Google, com impressões e cliques |
| `leads.csv` | Leads gerados, com campanha de origem, data e etapa atual do funil |
| `vendas.csv` | Vendas fechadas, com o lead que originou e o valor do contrato |
| `conversas_prevendas.json` | 15 conversas em formato de WhatsApp entre lead e atendente |

São dados sintéticos, criados para este case, e cobrem maio e junho de 2026.

---

## Parte 2 | SQL sobre os dados de funil

Usando os três CSVs, escreva as queries que respondem às perguntas abaixo. Pode carregar os arquivos em SQLite, DuckDB, Postgres ou o que preferir. **Entregue as queries em arquivo `.sql`** e os resultados no README.

1. **Custo por lead e custo por venda, por campanha**, considerando todo o período. Ordene do melhor para o pior custo por venda.
2. **Funil por campanha:** quantos leads chegaram a cada etapa e qual o percentual de perda entre uma etapa e a seguinte.
3. **Ticket médio e receita total por campanha**, e qual campanha traz o cliente de maior valor.

Considere que **os números que você apresentar serão usados para decidir realocação de verba de mídia entre as campanhas**. No README, explique como você chegou a cada número e o que sustenta a confiança neles.

---

## Parte 3 | Classificação de leads com LLM

O time de pré-vendas quer que a IA leia a conversa e devolva uma leitura estruturada antes do humano abrir o chat.

**Tarefa:** escreva um script Python que, para cada uma das 15 conversas em `conversas_prevendas.json`, chame um LLM (Claude, Gemini, OpenAI, o que você preferir e tenha acesso) e devolva um **JSON válido** por conversa, com no mínimo:

```json
{
  "conversa_id": "CV001",
  "classificacao": "quente | morno | frio | fora_do_perfil",
  "prioridade": 1,
  "sinais": ["...", "..."],
  "proxima_acao": "...",
  "resumo_para_o_vendedor": "..."
}
```

Você define o restante do schema, os critérios de classificação e o que conta como sinal. Justifique as escolhas no README.

**Requisitos:**

- O prompt precisa estar **versionado no repositório como arquivo separado**, não embutido no meio do código;
- A saída precisa ser **JSON válido em todos os casos**, inclusive quando o modelo não colaborar;
- O script precisa lidar com **falha na chamada** do modelo.

No README, responda:

> **Como você saberia, daqui a três meses e com 4.000 conversas processadas, se essa classificação está funcionando bem ou não?**

Seja concreto. O que você mediria, contra o quê, com que frequência, e o que faria disparar um alerta.

---

## O que vamos avaliar

| Peso | Critério |
|---|---|
| Alto | O código funciona, e continua funcionando quando algo dá errado |
| Alto | **Confiabilidade dos números apresentados** e clareza sobre como você chegou neles |
| Alto | Segurança básica no trato de credenciais |
| Alto | Clareza para explicar decisão técnica por escrito |
| Médio | Qualidade das queries SQL |
| Médio | Estruturação do prompt e da saída da IA |
| Médio | Critério para avaliar a qualidade da IA em produção |
| Médio | Organização do repositório e histórico de commits |
| Baixo | Elegância do código, arquitetura, testes automatizados |

**Não** vamos avaliar: front-end, deploy, cobertura de testes, uso de framework específico ou quantidade de linhas escritas.

---

## Próxima etapa

Quem avançar terá uma conversa de **45 minutos** com o time, sem necessidade de preparação prévia. Vamos abrir o seu repositório junto com você, discutir as decisões que você tomou e pensar em um cenário novo ao vivo.

Boa sorte. Estamos genuinamente interessados em ver como você trabalha.
