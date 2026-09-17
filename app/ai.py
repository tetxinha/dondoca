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

# Escolher as receitas da semana envolve equilibrar várias restrições ao
# mesmo tempo (proteína, hidratos, leguminosas, histórico) — um raciocínio
# mais elaborado do que a simples classificação acima, por isso usamos um
# modelo mais capaz. Corre só uma vez por semana, o custo extra é residual.
MODELO_PLANEAMENTO = "claude-sonnet-5"


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


def _fallback_lista_compras(receitas: list[dict], itens_faltas: list[str]) -> dict:
    """
    Se o Claude não devolver JSON válido, não arriscamos classificar
    itens sozinhos (a fronteira mercado/continente não é óbvia por regras
    simples) — juntamos tudo, sem separar por vírgulas nem deduplicar
    variações, e devolvemos como "continente" para nunca perderes um item.
    """
    ingredientes = [
        ingrediente.strip()
        for receita in receitas
        for ingrediente in receita.get("Ingredientes_Principais", "").split(",")
        if ingrediente.strip()
    ]
    todos_itens = list(dict.fromkeys(ingredientes + itens_faltas))
    return {"mercado": [], "continente": todos_itens}


def gerar_lista_compras_semanal(receitas: list[dict], itens_faltas: list[str]) -> dict:
    """
    Junta os ingredientes das receitas escolhidas para a semana com os
    itens ainda por resolver na lista de faltas, remove duplicados e
    variações do mesmo item (ex: "tomate" e "tomates") e classifica cada
    item resultante em "mercado" (fresco) ou "continente" (tudo o resto).

    Devolve um dicionário com:
      - mercado (list[str]): itens frescos — legumes, fruta, carne, peixe, arroz
      - continente (list[str]): tudo o resto — limpeza, higiene, mercearia
        não perecível, iogurtes, leite, massas, condimentos, cereais/aveia
    """
    receitas_texto = "\n".join(
        f"- {receita['Nome']}: {receita['Ingredientes_Principais']}" for receita in receitas
    ) or "(nenhuma receita esta semana)"
    faltas_texto = "\n".join(f"- {item}" for item in itens_faltas) or "(lista de faltas vazia)"

    prompt = f"""És responsável por preparar a lista de compras semanal de uma casa.

Receitas escolhidas para esta semana (nome: ingredientes principais):
{receitas_texto}

Itens ainda por resolver na lista de faltas:
{faltas_texto}

Tarefa:
1. Extrai os itens concretos a comprar a partir dos ingredientes das receitas (ignora quantidades, instruções de confeção e sub-receitas entre parênteses — foca-te só no ingrediente em si).
2. Junta esses itens com os da lista de faltas.
3. Remove duplicados e variações do mesmo item (ex: "tomate" e "tomates" contam como um só; junta pela versão mais natural em português de Portugal, no singular).
4. Classifica cada item resultante em exatamente uma destas duas categorias:
   - "mercado": produtos frescos — legumes, fruta, carne, peixe, arroz.
   - "continente": tudo o resto — produtos de limpeza, higiene, mercearia não perecível, iogurtes, leite, massas, condimentos, cereais/aveia.

Responde APENAS com JSON válido, sem mais nenhum texto, exatamente neste formato:
{{"mercado": ["item1", "item2", "..."], "continente": ["item1", "item2", "..."]}}
"""

    resposta = _client.messages.create(
        model=MODELO_PLANEAMENTO,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": prompt}],
    )

    bloco_texto = next((bloco for bloco in resposta.content if bloco.type == "text"), None)
    if bloco_texto is None:
        return _fallback_lista_compras(receitas, itens_faltas)

    try:
        return _parse_json_resposta(bloco_texto.text)
    except json.JSONDecodeError:
        return _fallback_lista_compras(receitas, itens_faltas)


def _escolha_fallback(receitas: list[dict], evitar: list[str]) -> dict:
    """
    Se o Claude não devolver JSON válido, escolhemos de forma simples: uma
    receita de cada tipo de proteína (peixe, carne, vegetariano) e depois
    completamos até 5, sempre a evitar as da semana passada. Não é tão bom a
    equilibrar hidratos/leguminosas quanto o Claude, mas garante que o job
    nunca fica sem resposta.
    """
    disponiveis = [r for r in receitas if r["Nome"] not in evitar]
    escolhidas: list[str] = []
    for tipo in ("peixe", "carne", "vegetariano"):
        for receita in disponiveis:
            if receita["Tipo_Proteina"] == tipo and receita["Nome"] not in escolhidas:
                escolhidas.append(receita["Nome"])
                break
    for receita in disponiveis:
        if len(escolhidas) >= 5:
            break
        if receita["Nome"] not in escolhidas:
            escolhidas.append(receita["Nome"])
    return {
        "escolhidas": escolhidas[:5],
        "justificacao": "Escolha automática (o filtro inteligente não respondeu em JSON válido).",
    }


def escolher_receitas_semana(
    receitas: list[dict], evitar: list[str], historico_compras: list[str]
) -> dict:
    """
    Pergunta ao Claude quais as 5 receitas a escolher para a semana.

    - receitas: lista de dicionários com as colunas do CSV de receitas
      (Nome, Tipo_Proteina, Tem_Leguminosas, Tem_Hidratos,
      Ingredientes_Principais, Ultima_Vez, ...).
    - evitar: nomes das receitas escolhidas na semana passada (não repetir).
    - historico_compras: textos recentes da lista de faltas, para o Claude
      perceber o que já se tem comprado e ajudar a variar.

    Devolve um dicionário com:
      - escolhidas (list[str]): exatamente 5 nomes de receitas (coluna "Nome")
      - justificacao (str): frase curta a explicar o equilíbrio escolhido
    """
    receitas_texto = json.dumps(receitas, ensure_ascii=False, indent=2)
    evitar_texto = "\n".join(f"- {nome}" for nome in evitar) or "(nenhuma, é a primeira semana)"
    historico_texto = "\n".join(f"- {item}" for item in historico_compras) or "(sem histórico de compras registado)"

    prompt = f"""És o planeador semanal de refeições de uma casa.

Livro de receitas disponível (uma receita por objeto JSON):
{receitas_texto}

Receitas escolhidas na semana passada (NÃO repetir esta semana):
{evitar_texto}

Histórico recente da lista de compras da casa:
{historico_texto}

Escolhe exatamente 5 receitas para esta semana, respeitando:
1. Nunca escolher nenhuma das receitas da semana passada.
2. Equilibrar o tipo de proteína (Tipo_Proteina: peixe, carne, vegetariano) ao longo da semana — evita escolher o mesmo tipo mais de 2-3 vezes em 5.
3. Equilibrar receitas com e sem hidratos (Tem_Hidratos) e com e sem leguminosas (Tem_Leguminosas).
4. Preferir receitas com "Ultima_Vez" mais antiga ou vazia (não repetidas há mais tempo).
5. Usar o histórico de compras como pista de variedade — evita escolher várias receitas seguidas com o mesmo ingrediente principal que já tem sido muito comprado recentemente.

Responde APENAS com JSON válido, sem mais nenhum texto, exatamente neste formato:
{{"escolhidas": ["Nome exato da receita 1", "Nome exato da receita 2", "Nome exato da receita 3", "Nome exato da receita 4", "Nome exato da receita 5"], "justificacao": "frase curta em português de Portugal a explicar o equilíbrio escolhido"}}
"""

    resposta = _client.messages.create(
        model=MODELO_PLANEAMENTO,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": prompt}],
    )

    # Com "thinking" ligado, o primeiro bloco da resposta pode ser um
    # ThinkingBlock em vez de texto — procuramos o bloco de texto em vez de
    # assumir que é sempre o content[0].
    bloco_texto = next((bloco for bloco in resposta.content if bloco.type == "text"), None)
    if bloco_texto is None:
        return _escolha_fallback(receitas, evitar)

    try:
        return _parse_json_resposta(bloco_texto.text)
    except json.JSONDecodeError:
        return _escolha_fallback(receitas, evitar)
