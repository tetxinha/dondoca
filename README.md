# dondoca

Assistente doméstico pessoal. Esta é a Fase 1: os webhooks de voz (Função 1
e Função 4). As funções 2 (receitas), 3 (lista de compras) e o envio por
WhatsApp para a empregada vêm nas próximas fases, construídas em cima desta
mesma base (SQLite + FastAPI).

## Correr localmente

```bash
python3 -m venv venv
source venv/bin/activate        # no Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edita o .env e escolhe um DONDOCA_WEBHOOK_SECRET só teu
# (o ficheiro .env é lido automaticamente, não precisas de mais nenhum comando)

uvicorn app.main:app --reload
```

O servidor fica em `http://localhost:8000`. Confirma no terminal que aparece uma
linha do tipo `Uvicorn running on http://127.0.0.1:8000` — só depois disso
é que faz sentido abrir o browser ou testar com curl. Testa:

```bash
curl -X POST http://localhost:8000/webhook/falta \
  -H "Content-Type: application/json" \
  -H "x-dondoca-secret: escolhe-uma-frase-secreta-longa" \
  -d '{"texto": "ovos"}'

curl http://localhost:8000/faltas
```

Se vires `ovos` na lista, está a funcionar.

## Configurar o IFTTT (a parte da voz)

Precisas de 2 applets (o plano gratuito do IFTTT permite isto):

### Applet 1 — Faltas
1. **If This**: serviço *Google Assistant* → escolhe o trigger **"Say a
   phrase with a text ingredient"**.
2. Configura as frases, por exemplo:
   - `Adiciona $ à falta`
   - `Falta $`
   - (o `$` é o texto que dizes, ex: "leite")
3. **Then That**: serviço *Webhooks* → **Make a web request**.
   - URL: `https://<o-teu-dominio-quando-fizeres-deploy>/webhook/falta`
   - Method: `POST`
   - Content Type: `application/json`
   - Body: `{"texto": "{{TextField}}"}`
   - Em "Advanced options" consegues adicionar um **header** customizado:
     `x-dondoca-secret: <o-mesmo-valor-do-teu-.env>`

### Applet 2 — Tarefas
Igual ao Applet 1, mas:
- Frases tipo `Adiciona $ às tarefas` / `Tarefa $`
- URL: `.../webhook/tarefa`

> Nota: enquanto testas localmente, o IFTTT não consegue chegar ao teu
> `localhost` (é preciso um URL público). Para testar já com o Google
> Nest Mini antes de fazeres deploy definitivo, podes usar o `ngrok`
> (`ngrok http 8000`) que te dá um URL público temporário.

## Próximos passos (fases seguintes)

- Fase 2: ligar a Google Sheet de receitas e o job de domingo que escolhe as 5.
- Fase 3: juntar receitas + faltas e enviar a lista consolidada por WhatsApp
  (com links de pesquisa do Continente).
- Fase 4: job que, à segunda (para terça) e à terça (para quarta), lê as
  tarefas da semana e envia o WhatsApp com as prioridades por dia
  (ver `EMPREGADA_DIAS` em `app/config.py` — já está preparado para isso).
- Deploy: Railway, Render ou Fly.io — basta ligar o repositório GitHub.

## Estrutura

```
dondoca/
├── app/
│   ├── main.py        # rotas / webhooks
│   ├── database.py    # SQLite
│   └── config.py       # configurações e regras da casa
├── requirements.txt
└── .env.example
```
