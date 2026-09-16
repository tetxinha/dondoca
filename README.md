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

## Cardápio semanal (job de sexta-feira às 20h)

O ficheiro `data/receitas.csv` é o livro de receitas da casa. Todas as
sextas-feiras às 20h, o endpoint `POST /job/cardapio-semanal` pede ao
Claude para escolher 5 receitas para a semana, equilibrando proteína
(peixe/carne/vegetariano), hidratos e leguminosas, evitando repetir as da
semana passada e olhando ao histórico da lista de faltas para variar. Este
horário dá tempo de preparar a lista do mercado antes de lá ires no sábado
de manhã.

Como a app não tem nenhum agendador interno, este job precisa de ser
"acionado" de fora, à semelhança dos webhooks de voz. Duas formas simples:

### Opção A — Render Cron Job (se fizeres deploy no Render)
1. No painel do Render, cria um **Cron Job** novo (ou usa `render.yaml`).
2. Comando: um `curl` que chama o endpoint, por exemplo:
   ```bash
   curl -X POST "https://<o-teu-dominio>/job/cardapio-semanal" \
     -H "x-dondoca-secret: <o-mesmo-valor-do-teu-.env>"
   ```
3. Agendamento: `0 20 * * 5` (todas as sextas-feiras às 20h, ajusta ao fuso horário do Render).

### Opção B — Applet de "Date & Time" no IFTTT
1. **If This**: serviço *Date & Time* → trigger **"Every day of the week at"**, escolhe Sexta-feira às 20:00.
2. **Then That**: serviço *Webhooks* → **Make a web request**, igual aos applets de voz:
   - URL: `.../job/cardapio-semanal`
   - Method: `POST`
   - Header: `x-dondoca-secret: <o-mesmo-valor-do-teu-.env>`

### Testar manualmente
O endpoint só corre normalmente à sexta-feira (para não disparares por
engano noutro dia). Para testares agora mesmo, usa `?force=true`:

```bash
curl -X POST "http://localhost:8000/job/cardapio-semanal?force=true" \
  -H "x-dondoca-secret: escolhe-uma-frase-secreta-longa"

curl http://localhost:8000/cardapio-semanal
```

## Próximos passos (fases seguintes)

- Fase 2: já tens o job de sexta-feira que escolhe as 5 receitas — falta ligar
  isto a uma fonte de receitas mais viva que o CSV (ex: Google Sheet), se
  fizer sentido no futuro.
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
│   ├── main.py        # rotas / webhooks / job do cardápio semanal
│   ├── ai.py           # filtros e decisões inteligentes (Claude)
│   ├── receitas.py     # leitura do CSV de receitas
│   ├── database.py    # SQLite
│   └── config.py       # configurações e regras da casa
├── data/
│   └── receitas.csv    # livro de receitas da casa
├── requirements.txt
└── .env.example
```
