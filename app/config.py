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

# Chave da API da Anthropic, para os filtros inteligentes (validação/duplicados).
# Obtém a tua em https://console.anthropic.com
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
