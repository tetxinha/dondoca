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

## Lista de compras semanal

Depois de o job de sexta-feira escolher as receitas, `GET
/lista-compras-semanal` junta os ingredientes principais dessas 5 receitas
com os itens ainda por resolver na lista de faltas, remove duplicados e
variações do mesmo item (ex: "tomate" e "tomates" contam como um só) e
separa tudo em duas listas — cada uma já com um campo `texto` pronto a
colar numa conversa de WhatsApp:

- **`mercado`**: produtos frescos — legumes, fruta, carne, peixe, arroz.
- **`continente`**: tudo o resto — limpeza, higiene, mercearia não
  perecível, iogurtes, leite, massas, condimentos, cereais/aveia.

```bash
curl http://localhost:8000/lista-compras-semanal
```

Não precisa de secret (é só leitura, como `/faltas` ou `/cardapio-semanal`),
mas dá erro `404` se ainda não tiver corrido nenhum `/job/cardapio-semanal`.
Não tem agendamento próprio — corre-o quando precisares (ex: no sábado de
manhã antes de saíres de casa), depois do job de sexta-feira já ter gerado
o cardápio.

## Enviar por WhatsApp (WhatsApp Cloud API da Meta)

`app/whatsapp.py` envia mensagens usando a WhatsApp Cloud API da Meta.
Passos manuais na [Meta for Developers](https://developers.facebook.com)
(não há como automatizar isto — é tudo feito na conta da Meta):

1. Cria uma conta de developer e uma App do tipo **Business**.
2. Na App, adiciona o produto **WhatsApp**. A Meta atribui logo um número
   de testes grátis.
3. Na página **"API Setup"** da App encontras o `Temporary access token`
   (24h) e o `Phone number ID` — copia-os para `WHATSAPP_TOKEN` e
   `WHATSAPP_PHONE_NUMBER_ID` no teu `.env`. Para um token que não expire,
   cria um **System User** em Business Settings → Users → System Users,
   com a permissão `whatsapp_business_messaging`.
4. Enquanto a app está em modo de testes, só consegues enviar para números
   que adicionares e verificares (por SMS) na secção "API Setup" → "To".
   Guarda esses números em `WHATSAPP_NUMERO_RITA` / `WHATSAPP_NUMERO_MARIDO`
   no `.env` (formato internacional, só dígitos: ex. `351912345678`).

### Texto livre vs. templates
- `enviar_mensagem(numero, texto)` manda texto livre, mas só é entregue se
  o destinatário te tiver escrito nas últimas 24h (a "janela de
  atendimento" da Meta). Serve para testar rapidamente:
  ```bash
  python3 -c "
  from app.config import WHATSAPP_NUMERO_RITA
  from app.whatsapp import enviar_mensagem
  print(enviar_mensagem(WHATSAPP_NUMERO_RITA, 'teste'))
  "
  ```
- Fora dessa janela (ex: enviar a lista sem a pessoa ter escrito primeiro),
  a Meta só entrega mensagens de **template pré-aprovado**. Temos três
  templates em revisão na Meta — `lista_mercado`, `lista_continente` e
  `lista_tarefas` — todos com uma única variável `{{1}}` no corpo, onde
  entra a lista em bullet points (um item por parágrafo). Os nomes vão
  para `WHATSAPP_TEMPLATE_LISTA_MERCADO` / `_CONTINENTE` / `_TAREFAS` no
  `.env`, e `WHATSAPP_TEMPLATE_LINGUA` (o mesmo para os três).
- `enviar_lista_mercado(numero, itens)`, `enviar_lista_continente(numero,
  itens)` e `enviar_lista_tarefas(numero, itens)` usam esses templates.
  **Não funcionam enquanto a Meta não aprovar os templates** — até lá, a
  chamada à API é recusada mesmo com o nome certo configurado.

## Próximos passos (fases seguintes)

- Fase 2: já tens o job de sexta-feira que escolhe as 5 receitas — falta ligar
  isto a uma fonte de receitas mais viva que o CSV (ex: Google Sheet), se
  fizer sentido no futuro.
- Fase 3: já tens receitas + faltas juntas numa lista de compras consolidada
  (`/lista-compras-semanal`) e o envio por WhatsApp pronto
  (`app/whatsapp.py`) — falta a Meta aprovar os templates e ligar tudo a
  um endpoint/job que envie automaticamente.
- Fase 4: job que, à segunda (para terça) e à terça (para quarta), lê as
  tarefas da semana e envia o WhatsApp com as prioridades por dia (já tens
  `enviar_lista_tarefas()` pronta e `EMPREGADA_DIAS` em `app/config.py`).
- Deploy: Railway, Render ou Fly.io — basta ligar o repositório GitHub.

## Estrutura

```
dondoca/
├── app/
│   ├── main.py        # rotas / webhooks / job do cardápio semanal
│   ├── ai.py           # filtros e decisões inteligentes (Claude)
│   ├── receitas.py     # leitura do CSV de receitas
│   ├── whatsapp.py     # envio de mensagens (WhatsApp Cloud API)
│   ├── database.py    # SQLite
│   └── config.py       # configurações e regras da casa
├── data/
│   └── receitas.csv    # livro de receitas da casa
├── requirements.txt
└── .env.example
```
