"""
Configuração central da dondoca.

Mantém aqui tudo o que é "regras da casa" — dias da empregada, etc. —
para não andarmos a caçar valores espalhados pelo código mais tarde.
"""

import os

from dotenv import load_dotenv

# Lê o ficheiro .env e carrega as variáveis automaticamente.
# Isto substitui o comando 'export $(cat .env | xargs)' no terminal —
# já não precisas de o correr, o Python trata disto sozinho.
load_dotenv()

# Chave secreta que colocamos na URL do webhook (?secret=...) para que
# só o IFTTT (que a conhece) consiga escrever nas listas.
WEBHOOK_SECRET = os.getenv("DONDOCA_WEBHOOK_SECRET", "muda-me")

# Dias em que a empregada vem e o que faz em cada um.
# weekday: 0 = segunda, 1 = terça, ..., 6 = domingo (convenção do Python)
EMPREGADA_DIAS = {
    1: "Limpeza geral da casa, tirar nódoas, pôr roupa a lavar e a secar",  # terça
    2: "Passar a roupa a ferro e arrumar",  # quarta
}

# Caminho da base de dados SQLite
DB_PATH = os.getenv("DONDOCA_DB_PATH", "dondoca.db")

# Caminho do ficheiro CSV com as receitas
RECEITAS_PATH = os.getenv("DONDOCA_RECEITAS_PATH", "data/receitas.csv")

# Chave da API da Anthropic, para os filtros inteligentes (validação/duplicados).
# Obtém a tua em https://console.anthropic.com
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# WhatsApp Cloud API (Meta) — para enviar mensagens (lista de compras,
# tarefas, etc.). Ver README para os passos de configuração na Meta for
# Developers (conta, número de testes, token de acesso).
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")

# Números autorizados a receber mensagens (aprovados na Meta enquanto a
# app está em modo de testes). A empregada ainda não está cá — usa-se o
# WHATSAPP_NUMERO_RITA para testar antes de a adicionar.
WHATSAPP_NUMERO_RITA = os.getenv("WHATSAPP_NUMERO_RITA", "")
WHATSAPP_NUMERO_MARIDO = os.getenv("WHATSAPP_NUMERO_MARIDO", "")

# Nomes dos templates (em revisão na Meta), um por lista. Todos têm o
# mesmo formato: uma única variável {{1}} no corpo, com os itens em
# bullet points, um por parágrafo.
WHATSAPP_TEMPLATE_LISTA_MERCADO = os.getenv("WHATSAPP_TEMPLATE_LISTA_MERCADO", "")
WHATSAPP_TEMPLATE_LISTA_CONTINENTE = os.getenv("WHATSAPP_TEMPLATE_LISTA_CONTINENTE", "")
WHATSAPP_TEMPLATE_LISTA_TAREFAS = os.getenv("WHATSAPP_TEMPLATE_LISTA_TAREFAS", "")

# Código de idioma dos templates (o mesmo para todos), tal como escolhido
# ao criá-los na Meta.
WHATSAPP_TEMPLATE_LINGUA = os.getenv("WHATSAPP_TEMPLATE_LINGUA", "pt_PT")
