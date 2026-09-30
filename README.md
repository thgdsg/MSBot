# MSBot — Yung Bot

A Discord bot built with Python and `discord.py`, designed for community interaction, server moderation, AI conversations, games, automated advertisements, and chaotic server events. Made for fun.

MSBot, also known as Yung Bot, is currently configured for a specific Discord server. Most commands and automatic behaviors only operate inside that server but can be changed in the source code.

## Features

### AI Conversations

Yung Bot can act as an AI assistant inside Discord using the NVIDIA API.

Users can interact with the bot in two ways:

* mention the bot in a regular message;
* use the `/conversar` slash command.

The AI module includes:

* responses powered by NVIDIA-hosted language models;
* automatic fallback to a secondary model when the primary model reaches its rate limit;
* automatic switch to another listed model if NVIDIA retires a model (HTTP 410);
* retry logic for connection errors and API timeouts;
* support for replying to one of the bot's previous messages to provide additional context;
* automatic splitting of responses longer than Discord's 2,000-character limit;
* interaction logging;
* per-channel persistent memory;
* automatic conversation summarization;
* configurable AI model through an administrator command.

If NVIDIA reports that a model reached end of life, the client skips that model
for future requests, retries with another entry from the supported model list,
and sends one alert per retired model per bot run to `CANAL_BOT`, mentioning `DAFONZ_ID`.
Set both variables in `.env` to enable the alert.

If an AI response is still pending after ten minutes, the bot starts one request
with a second listed model and uses the first successful response. Only the
winning response may run tools. The hedge can result in two billable API calls
when the original model is unusually slow.

The default model is:

```text
deepseek-ai/deepseek-v4.1-flash
```

The default fallback model is:

```text
z-ai/glm-5.3-flash
```

Available models include:

| Model |
| ----- |
| `z-ai/glm-5.3-flash` |
| `moonshotai/kimi-k3` |
| `z-ai/glm-5.3` |
| `deepseek-ai/deepseek-v4.1-flash` |

#### Persistent AI Memory

The bot also tracks its own writing habits in a `WritingStyle` memory section.
An opening becomes a habit after at least three occurrences and 25% of the
last 20 generated responses. This memory guides subsequent replies; repeated
introductory fillers such as `ah,` are removed before sending. Full phrases
are not cut automatically. Observations persist across restarts, age out of
the rolling window, and are cleared by the memory reset command.

Conversations are temporarily buffered per Discord channel, retaining the
author name, Discord user ID and UTC timestamps for each turn.

After enough messages have accumulated, the bot summarizes the conversation and updates a channel-specific section inside:

```text
MEMORY.md
```

This allows the bot to preserve useful facts, recurring context, preferences,
and previous decisions across conversations. Summaries are requested as JSON
operations (`add`, `update`, `delete`, and `ignore`) with scoped memories for
the server, channel, or user. Entries include categories, confidence,
timestamps, optional expiration, and conflict history.

Moderators can use `/adicionamemoria memoria` to append administrator-provided
instructions or facts to a persistent `Custom` section. Discord slash command
names are lowercase, so the registered command is `/adicionamemoria`.

The AI module uses the following files:

| File                        | Purpose                                  |
| --------------------------- | ---------------------------------------- |
| `logs/conversation_history.json` | Stores AI interaction history         |
| `memory_state.json`         | Stores messages waiting to be summarized |
| `MEMORY.md`                 | Stores persistent summarized memory      |
| `memory_backup.md`          | Seed used by the memory reset command    |
| `memory_backups/`           | Versioned backups of `MEMORY.md`         |
| `logs/interactions.json`    | Stores commands and AI interaction logs  |
| `logs/bot.log`              | Runtime output and application logs      |
| `logs/nvidia_errors.log`    | NVIDIA errors and malformed responses    |

---

### Forbidden Word Game

The bot can select a random Portuguese word and make it the server's current **forbidden word**.

When a regular member sends a message containing the forbidden word:

1. the member receives a five-minute Discord timeout;
2. the bot announces that the forbidden word was triggered;
3. the bot can automatically select a new forbidden word.

Members with moderation permissions are not timed out, but the word may still be replaced.

Forbidden words are selected using the `python_pt_dictionary` package.

The system supports:

* random forbidden-word generation;
* manual word selection;
* automatic word replacement after it is triggered;
* automatic replacement after a configurable number of messages;
* enabling or disabling automatic word replacement;
* temporarily disabling the forbidden-word system;
* displaying the current word privately to moderators;
* Portuguese dictionary lookups through `/significado`.

> The current forbidden word is stored in memory and is not preserved after the bot restarts. Run `/novapalavra` after starting the bot.

---

### Automated Advertisements

The bot can automatically post advertisements after a configurable number of server messages.

Advertisements are loaded from:

```text
propagandas.json
```

Each advertisement may contain:

* text;
* an optional image;
* a numeric identifier for manual selection.

Example:

```json
[
    {
        "numero": 1,
        "texto": "This is the first advertisement.",
        "imagem": "images/ad-1.png"
    },
    {
        "numero": 2,
        "texto": "This advertisement does not contain an image."
    }
]
```

The advertisement system supports:

* random advertisement selection;
* manual advertisement selection by numeric identifier;
* configurable message interval;
* optional image attachments;
* manual advertisement posting;
* optional channel locking after an advertisement;
* configurable number of reactions required to unlock the channel.

#### Reaction-Based Chat Unlocking

When an advertisement is posted with chat locking enabled:

1. the bot saves the channel's current permissions;
2. the advertisement receives a `✅` reaction;
3. the bot disables message sending for the server's default role;
4. members must reach the configured number of `✅` reactions;
5. the original channel permissions are restored.

If the advertisement message is deleted, the bot attempts to restore the previous permissions automatically.

Administrators can also lock or unlock the channel manually.

> The `propagandas.json` file and the `images/` directory are ignored by Git and must be created locally.

---

### Daily “First” Game

The first member to send a message containing `first` after the daily reset receives a special Discord role named:

```text
first
```

The daily reset occurs at midnight using the `America/Sao_Paulo` timezone.

During the reset, the bot:

* removes the `first` role from its current holder;
* makes the role available again;
* clears the temporary AI conversation history.

When a member claims the daily `first`, the bot:

* assigns the `first` role;
* announces the winner;
* increments the member's total count;
* stores the event timestamp in SQLite.

#### Persistent Rankings

First counts are stored in:

```text
discord_bot.db
```

The database contains:

* total first counts per user;
* individual first events and timestamps.

The bot provides:

* an all-time leaderboard;
* paginated ranking navigation;
* a monthly leaderboard;
* navigation between previous months;
* user lookup by Discord name or nickname;
* administrator commands to correct first counts manually.

---

### Moderation Tools

MSBot includes multiple slash commands for server moderation.

Moderators can:

* apply a temporary mute role;
* define mute durations using values such as `1h30m20s`;
* remove the mute role manually;
* send moderation events to a configured log channel;
* make the bot send a custom message;
* make the bot reply to a specific Discord message;
* manually lock or unlock a channel.

The mute system uses the role configured through `MUTE_ROLE_ID`.

> Temporary unmute scheduling runs in the bot process. Restarting the bot before a mute expires may prevent the automatic role removal.

---

### Special Anti-Ping Rule

The bot can protect a specific Discord user from mentions.

When another member mentions the user configured through `TOJAO`, the author receives a one-minute timeout and the bot posts:

```text
NAO. PINGUE. O. TOJAO.
```

Members with moderation permissions are exempt.

---

### Divine Message Generator

The `/mensagemdivina` command generates a sentence containing a configurable number of randomly selected Portuguese words.

The feature is inspired by the random-word behavior associated with TempleOS and uses the same Portuguese dictionary integration as the forbidden-word system.

---

### Layered application architecture

The bot uses explicit dependency injection through `AppContext`; Discord
registration is kept separate from feature logic:

| Package | Responsibility |
| --- | --- |
| `app/config.py`, `app/state.py`, `app/context.py` | Configuration, volatile state, and shared services |
| `app/services/` | AI, memory, NVIDIA, words, advertisements, first, and moderation logic |
| `app/commands/` | Thin slash-command callbacks and the explicit command registry |
| `app/events/` | Message, reaction, deletion, ready, and daily-reset handlers |
| `app/persistence/` | JSON and SQLite repositories |
| `app/views/` | Discord leaderboard views |
| `bot.py` | Client bootstrap and lifecycle integration |

Run the tests with `python -m unittest discover` and start the bot with
`python bot.py`.

---

## Slash Commands

### AI Commands

| Command                 | Access    | Description                                  |
| ----------------------- | --------- | -------------------------------------------- |
| `/conversar mensagem`   | Everyone  | Sends a message to the AI assistant          |
| `/adicionamemoria memoria` | Moderator | Adds content to the persistent `Custom` memory section |
| `/enviarmsgllm prompt [modelo]` | Moderator | Sends an LLM-generated message to the channel |
| `/alterarmodelo modelo` | Moderator | Changes the primary AI model                 |
| `/vermemoria`           | Moderator | Displays the current contents of `MEMORY.md` |

The bot can also be used by mentioning it in a normal server message.

---

### Forbidden Word Commands

| Command                                | Access    | Description                                     |
| -------------------------------------- | --------- | ----------------------------------------------- |
| `/novapalavra`                         | Moderator | Selects a new random forbidden word             |
| `/redefinepalavra`                     | Moderator | Disables the current forbidden word             |
| `/mostrapalavra`                       | Moderator | Privately displays the current forbidden word   |
| `/escolhepalavra novapalavra`          | Moderator | Sets the forbidden word manually                |
| `/escolhenummensagens numeromensagens` | Moderator | Changes the automatic word replacement interval |
| `/mantempalavra`                       | Moderator | Enables or disables automatic word replacement  |
| `/significado palavra`                 | Everyone  | Searches for the meaning of a Portuguese word   |

---

### Advertisement Commands

| Command                                               | Access    | Description                                                     |
| ----------------------------------------------------- | --------- | --------------------------------------------------------------- |
| `/mudaconfigpropaganda numeromsgslidas numeroreacoes` | Moderator | Configures the advertisement interval and unlock reaction count |
| `/enviapropaganda bloqueiachat [escolha]`             | Moderator | Posts an advertisement, optionally locking the channel          |
| `/bloqueiachat`                                       | Moderator | Prevents the default role from sending messages                 |
| `/desbloqueiachat`                                    | Moderator | Restores channel messaging permissions                          |

---

### First Commands

| Command                        | Access    | Description                                        |
| ------------------------------ | --------- | -------------------------------------------------- |
| `/top10first [mensal]`         | Everyone  | Displays the all-time or monthly first leaderboard |
| `/buscafirsts username`        | Everyone  | Looks up a member's total first count              |
| `/adicionafirst user_id count` | Bot owner | Adds first entries manually                        |
| `/removefirst user_id count`   | Bot owner | Removes first entries manually                     |

The owner-only commands use the account configured through `DAFONZ_ID`.

---

### Moderation and Miscellaneous Commands

| Command                              | Access    | Description                               |
| ------------------------------------ | --------- | ----------------------------------------- |
| `/mutar membro duracao motivo`       | Moderator | Assigns the mute role temporarily         |
| `/desmutar membro`                   | Moderator | Removes the mute role                     |
| `/enviarmsg mensagemescrita`         | Moderator | Makes the bot send a custom message       |
| `/respondermsg mensagem_id resposta` | Moderator | Makes the bot reply to a specific message |
| `/mensagemdivina numeropalavras`     | Moderator | Generates a random Portuguese sentence    |

---

## Requirements

* Python 3.10 or newer;
* a Discord bot application;
* a Discord server;
* an NVIDIA API key for AI features;
* a role named `first`;
* a role used for muting members;
* the required Discord permissions and privileged intents.

Install the Python dependencies with:

```bash
pip install -r requirements.txt
```

Main dependencies include:

* `discord.py`;
* `python-dotenv`;
* `requests`;
* `python_pt_dictionary`;
* `Unidecode`;
* `peewee`.

---

## Discord Bot Configuration

Create an application in the Discord Developer Portal and add a bot to it.

Because the bot uses:

```python
discord.Intents.all()
```

enable the required privileged gateway intents:

* Server Members Intent;
* Message Content Intent;
* Presence Intent, when required by your bot configuration.

Recommended bot permissions include:

* View Channels;
* Send Messages;
* Read Message History;
* Add Reactions;
* Attach Files;
* Manage Roles;
* Moderate Members;
* Manage Channels.

The bot's role must be placed above the `first` and mute roles in the server role hierarchy.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/thgdsg/MSBot.git
cd MSBot
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
DISCORD_TOKEN=your_discord_bot_token
MENES_SUECOS=your_discord_server_id

NVIDIA_API_KEY=your_nvidia_api_key

LOG_CHANNEL_ID=your_moderation_log_channel_id
MUTE_ROLE_ID=your_mute_role_id

TOJAO=protected_user_id
DAFONZ_ID=bot_owner_user_id
CANAL_BOT=channel_for_bot_alerts
```

### Variable Reference

| Variable         | Required                 | Description                                           |
| ---------------- | ------------------------ | ----------------------------------------------------- |
| `DISCORD_TOKEN`  | Yes                      | Discord bot token                                     |
| `MENES_SUECOS`   | Yes                      | Discord server in which the bot is allowed to operate |
| `NVIDIA_API_KEY` | For AI features          | NVIDIA API key used by the LLM integration            |
| `LOG_CHANNEL_ID` | For moderation logs      | Channel that receives mute and unmute logs            |
| `MUTE_ROLE_ID`   | For mute commands        | Discord role assigned to muted members                |
| `TOJAO`          | For anti-ping protection | User protected by the automatic anti-ping timeout     |
| `DAFONZ_ID`      | For owner commands       | User allowed to modify first counts manually          |
| `CANAL_BOT`      | For model alerts         | Channel where deprecated-model alerts are sent          |

### Web search tool

As respostas da LLM podem usar automaticamente a ferramenta `web_search` quando
a pergunta depender de informacoes atuais ou desconhecidas. A ferramenta usa
exclusivamente a API publica de respostas instantaneas do DuckDuckGo, limita a
consulta a cinco resultados e devolve titulo, URL e resumo para a LLM.

Nenhuma chave de busca adicional e necessaria. Como essa API e baseada em
respostas instantaneas, ela pode nao encontrar resultados para todas as
consultas.

---

## Ferramentas de contexto da LLM

A ferramenta `web_search` continua usando exclusivamente DuckDuckGo. O bot
tambem pode escolher estas ferramentas, na ordem de registro:

1. `memory_search`: pesquisa memorias por usuario, canal ou servidor, excluindo
   entradas expiradas; inclui a secao Custom no escopo servidor.
2. `recent_messages`: recupera as ultimas cinco mensagens em ordem cronologica.
3. `fetch_url`: extrai ate 8.000 caracteres de paginas publicas HTTP/HTTPS,
   valida redirecionamentos e limita o download a 512 KB.
4. `weather`: consulta cidade, clima atual e previsao do dia na
   [Open-Meteo](https://open-meteo.com/en/docs), sem chave de API.
5. `first_count`: consulta o placar existente em `discord_bot.db` por ID de
   usuario; sem cadastro, retorna zero. O banco pertence ao servidor configurado.
6. `top_firsts`: retorna o top 25 geral com posição, username, apelido atual no
   servidor e quantidade de firsts.
7. `monthly_firsts`: recebe ano e mês e retorna cada pessoa única que conseguiu
   firsts naquele período, com posição, username, apelido e quantidade mensal.
8. `user_profile`: busca o perfil do usuário da conversa, com IDs, username,
   display name, avatar/banner, data de criação da conta, apelido, data de
   entrada no servidor, cargos, permissões relevantes, timeout e uma amostra
   limitada de mensagens em canais que o bot e o usuário podem ler.
9. `get_message`: recupera uma mensagem pelo ID, no canal informado ou atual.
10. `dictionary`: consulta definicoes na biblioteca `python_pt_dictionary`.
   Sinonimos e traducoes usam resultados do DuckDuckGo como complemento; para
   traducao e necessario informar o idioma de destino. A biblioteca nao possui
   campos separados de sinonimos ou traducoes, e a busca pode nao retornar dados.
11. `calculator`: calcula expressoes aritmeticas localmente, permitindo somente
    numeros, parenteses e `+`, `-`, `*`, `/`, `//`, `%` e `**`.

O `user_profile` não inventa campos que a API não entrega: bio, pronomes e uma
contagem histórica total de mensagens são retornados como indisponíveis. A
atividade de mensagens é apenas uma janela limitada pelo histórico acessível e
pelas permissões do Discord.

Os IDs de usuario e canal usam o contexto da pergunta quando omitidos. Consultas
Discord verificam o servidor e as permissoes do autor e do bot; canais restritos
so podem ser consultados a partir do proprio canal, evitando expor seu conteudo
em outro. As ferramentas de consulta sao somente de leitura. Cada rodada executa no maximo
cinco ferramentas, por ate tres rodadas.

## Respostas espontaneas

### Contagem de mensagens e cargos da LLM

`message_count` retorna a quantidade de mensagens do autor registradas no
servidor desde `tracking_since`, persistidas em `message_counts.db`. Inclui
menções ao bot e mensagens posteriormente apagadas; eventos repetidos não
duplicam a contagem. Não importa histórico anterior nem conta mensagens
enviadas enquanto o bot estava offline. Não armazena o conteúdo das mensagens.

`give_platelminto` atribui o cargo `1194700649301020763` quando a LLM gosta muito
da mensagem dirigida a ela. `give_homunco` (`1194723205022232637`) e
`give_quarentena` (`1194720159416467527`) são usados quando ela considera a
mensagem claramente ofensiva. A decisão é feita pelo modelo conforme o prompt.
As ferramentas só podem agir no autor atual e nesses IDs fixos; não removem
outros cargos. O bot precisa de Gerenciar Cargos e de um cargo acima deles.
O motivo fica no registro de auditoria do Discord. Falhas são retornadas à LLM.

As ferramentas `remove_platelminto`, `remove_homunco` e `remove_quarentena`
retiram apenas o cargo indicado do autor atual, com as mesmas verificações de
permissão e hierarquia. Os critérios são inversos aos de atribuição: uma mensagem
muito ofensiva pode retirar Platelminto; uma mensagem muito apreciada pode retirar
Homunco e Quarentena. Se o cargo já estiver ausente, retornam `already_absent`
sem alterar o membro. Uma remoção concluída retorna `removed`.


Mensagens de usuarios no servidor configurado, sem mencao ao bot, participam de
um sorteio independente de 1 em 100. O bot comenta em forma de opiniao propria,
sabendo que nao foi chamado; imagens passam pelo reconhecimento ja existente.
Mencoes recebem a resposta normal e nao participam do sorteio. Mensagens de bots
e mensagens fora do servidor configurado sao ignoradas. Os demais eventos
(palavra proibida, propagandas e firsts) continuam sendo processados.

## Advertisement Configuration

Create `propagandas.json` in the project root:

```json
[
    {
        "numero": 1,
        "texto": "Example advertisement",
        "imagem": "images/example.png"
    },
    {
        "numero": 2,
        "texto": "Text-only advertisement"
    }
]
```

Create the image directory when using attachments:

```bash
mkdir -p images
```

The `imagem` property is optional.

The `numero` property can be passed to the optional `escolha` argument of `/enviapropaganda`.

---

## Running the Bot

Start the bot with:

```bash
python bot.py
```

After startup:

1. verify that the slash commands were synchronized;
2. run `/novapalavra` to initialize the forbidden-word game;
3. verify that the bot can manage the `first` and mute roles;
4. test the advertisement reaction unlock system in a private channel;
5. test `/conversar` to verify the NVIDIA API configuration.

---

## Persistent and Runtime Data

The following files are generated during execution and are ignored by Git:

| File                        | Description                               |
| --------------------------- | ----------------------------------------- |
| `.env`                      | Secrets and server configuration          |
| `discord_bot.db`            | SQLite database for first counts and logs |
| `logs/`                     | Runtime, command, AI interaction, and NVIDIA error logs |
| `memory_state.json`         | Pending AI memory buffers                 |
| `MEMORY.md`                 | Persistent summarized AI memory           |
| `memory_backup.md`          | Initial memory snapshot used for reset    |
| `memory_backups/`           | Rotating versioned memory snapshots      |
| `propagandas.json`          | Local advertisement configuration         |
| `images/`                   | Advertisement image files                 |

Some settings are only stored in memory and reset when the bot restarts, including:

* the current forbidden word;
* message counters;
* automatic advertisement counters;
* active advertisement lock state;
* custom message and reaction limits;
* the currently selected AI model.

---

## Project Structure

```text
MSBot/
├── bot.py
├── app/
│   ├── commands/
│   ├── events/
│   ├── persistence/
│   ├── services/
│   ├── views/
│   └── config.py, context.py, state.py
├── tests/
├── requirements.txt
├── propagandas.json         # Local file, ignored by Git
├── images/                  # Local directory, ignored by Git
├── MEMORY.md                # Generated at runtime
├── memory_state.json        # Generated at runtime
├── logs/                    # Runtime, interaction, and NVIDIA error logs
└── discord_bot.db
```
The executable source now lives under `app/`, with commands in
`app/commands/`, event handlers in `app/events/`, persistence adapters in
`app/persistence/`, domain services in `app/services/`, and Discord UI views
in `app/views/`. `bot.py` remains the entry point.
