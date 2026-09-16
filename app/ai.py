"""
Filtro inteligente para os itens que dizes por voz.

Antes de gravarmos algo na lista de "faltas" (ou "tarefas"), perguntamos
ao Claude duas coisas:
  1. Isto parece mesmo algo de casa a sério (não ruído, erro de voz, teste)?
  2. Já existe qualquer coisa parecida na lista atual (duplicado)?

Esta é a "Fase C" do roteiro: uma única chamada à API, sem agente nem
ferramentas ainda — o suficiente para resolver 80% do que pediste.
"""

import json

import anthropic

from app.config import ANTHROPIC_API_KEY

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Haiku é o modelo mais rápido e barato da Anthropic — chega perfeitamente
# bem para uma tarefa de classificação simples como esta.
MODELO = "claude-haiku-4-5-20251001"


def _parse_json_resposta(texto_resposta: str) -> dict:
    """
    O Claude às vezes envolve o JSON em blocos de código markdown
    (```json ... ```), mesmo quando lhe pedimos explicitamente para não o
    fazer. Removemos esse invólucro antes de tentar fazer o parse.
    """
    texto_resposta = texto_resposta.strip()
    if texto_resposta.startswith("```"):
        texto_resposta = texto_resposta.strip("`")
        if texto_resposta.startswith("json"):
            texto_resposta = texto_resposta[4:]
        texto_resposta = texto_resposta.strip()
    return json.loads(texto_resposta)


def validar_item(texto_novo: str, itens_existentes: list[str]) -> dict:
    """
    Pergunta ao Claude se o novo item faz sentido e se é duplicado.

    Devolve um dicionário com:
      - valido (bool): parece um item de casa a sério?
      - duplicado (bool): já existe um item parecido na lista?
      - item_duplicado (str | None): qual item existente corresponde, se houver
      - mensagem (str): frase curta para dizer/mostrar ao utilizador
    """
    lista_texto = "\n".join(f"- {item}" for item in itens_existentes) or "(lista vazia)"

    prompt = f"""És o filtro de qualidade de uma lista de compras de casa, dita por voz através da Siri.

Lista atual de itens já pendentes:
{lista_texto}

Novo item dito por voz: "{texto_novo}"

Decide:
1. "valido": é plausível que isto seja mesmo algo que falta em casa (comida, produtos de limpeza, etc.)? Nomes de pessoas (ex: "avó"), texto de teste (ex: "teste-curl", "abc", "xyz") ou frases sem sentido devem ter valido=false.
2. "item_limpo": o nome do item, sem palavras de enchimento como "preciso de", "falta", "adiciona", "à lista". Ex: "preciso de massa" → "massa". Se valido=false, usa o texto original tal como veio.
3. "duplicado": o "item_limpo" já está coberto por algum item existente na lista (ignora maiúsculas/minúsculas, singular/plural, pequenas variações de escrita)?
4. "item_duplicado": se duplicado=true, o texto exato do item existente correspondente. Caso contrário, null.
5. "mensagem": uma frase curta (menos de 15 palavras) em português de Portugal, para dizer ao utilizador — confirmando a adição do "item_limpo", avisando de duplicado, ou perguntando se quer mesmo adicionar algo estranho.

Responde APENAS com JSON válido, sem mais nenhum texto, exatamente neste formato:
{{"valido": true, "item_limpo": "...", "duplicado": false, "item_duplicado": null, "mensagem": "..."}}
"""

    resposta = _client.messages.create(
        model=MODELO,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )

    texto_resposta = resposta.content[0].text
    try:
        return _parse_json_resposta(texto_resposta)
    except json.JSONDecodeError:
        # Se o modelo não devolver JSON limpo por algum motivo, preferimos
        # adicionar o item na mesma (melhor um falso positivo do que perderes
        # um item real de propósito).
        return {
            "valido": True,
            "item_limpo": texto_novo,
            "duplicado": False,
            "item_duplicado": None,
            "mensagem": f"Adicionado: {texto_novo}",
        }


def validar_tarefa(texto_novo: str, itens_existentes: list[str]) -> dict:
    """
    Igual a `validar_item`, mas para tarefas domésticas em vez de itens de
    compras. Aqui o texto não é uma palavra única, mas sim uma frase de ação
    (ex: "lavar roupa de bebé com vómito que está em cima da máquina"), por
    isso a deteção de duplicados tem de olhar para a ação e o assunto de
    fundo, ignorando detalhes descritivos extra (localização, motivo, etc.).

    Devolve um dicionário com:
      - valido (bool): parece mesmo uma tarefa de casa a sério?
      - item_limpo (str): a tarefa reescrita de forma clara e concisa
      - duplicado (bool): já existe uma tarefa parecida na lista?
      - item_duplicado (str | None): qual tarefa existente corresponde, se houver
      - mensagem (str): frase curta para dizer/mostrar ao utilizador
    """
    lista_texto = "\n".join(f"- {item}" for item in itens_existentes) or "(lista vazia)"

    prompt = f"""És o filtro de qualidade de uma lista de tarefas domésticas, ditas por voz através do Google Assistant.

Lista atual de tarefas já pendentes:
{lista_texto}

Nova tarefa dita por voz: "{texto_novo}"

Decide:
1. "valido": é plausível que isto seja mesmo uma tarefa de casa a sério (arrumar, lavar, tratar de algo, marcar algo, etc.)? Nomes de pessoas isolados, texto de teste (ex: "teste-curl", "abc", "xyz") ou frases sem sentido devem ter valido=false.
2. "item_limpo": a tarefa reescrita de forma clara e concisa, removendo palavras de enchimento como "preciso de", "tenho de", "adiciona à lista", mas mantendo a ação e o assunto principal (ex: "preciso de tratar da roupa do bebé que vomitou" → "tratar da roupa do bebé com vómito"). Se valido=false, usa o texto original tal como veio.
3. "duplicado": esta tarefa refere-se à mesma ação/assunto de fundo que alguma tarefa já existente na lista, mesmo que a frase seja diferente ou tenha mais/menos detalhes (ex: "lavar roupa de bebé com vómito que está em cima da máquina de lavar" e "tratar da roupa de bebé com vómito" são a MESMA tarefa)? Foca-te na ação principal e no objeto/assunto, não nos detalhes descritivos (localização exata, motivo, etc.).
4. "item_duplicado": se duplicado=true, o texto exato da tarefa existente correspondente. Caso contrário, null.
5. "mensagem": uma frase curta (menos de 15 palavras) em português de Portugal, para dizer ao utilizador — confirmando a adição da tarefa, avisando de duplicado, ou perguntando se quer mesmo adicionar algo estranho.

Responde APENAS com JSON válido, sem mais nenhum texto, exatamente neste formato:
{{"valido": true, "item_limpo": "...", "duplicado": false, "item_duplicado": null, "mensagem": "..."}}
"""

    resposta = _client.messages.create(
        model=MODELO,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )

    texto_resposta = resposta.content[0].text
    try:
        return _parse_json_resposta(texto_resposta)
    except json.JSONDecodeError:
        return {
            "valido": True,
            "item_limpo": texto_novo,
            "duplicado": False,
            "item_duplicado": None,
            "mensagem": f"Adicionado: {texto_novo}",
        }
