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
* retry logic for connection errors and API timeouts;
* support for replying to one of the bot's previous messages to provide additional context;
* automatic splitting of responses longer than Discord's 2,000-character limit;
* interaction logging;
* per-channel persistent memory;
* automatic conversation summarization;
* configurable AI model through an administrator command.

The default model is:

```text
minimaxai/minimax-m2.7
```

The default fallback model is:

```text
moonshotai/kimi-k2-thinking
```

Available models include:

| Model                         |
| ----------------------------- |
| `minimaxai/minimax-m2.7`      |
| `z-ai/glm4.7`                 |
| `deepseek-ai/deepseek-v3_2`   |
| `moonshotai/kimi-k2-thinking` |

#### Persistent AI Memory

Conversations are temporarily buffered per Discord channel.

After enough messages have accumulated, the bot summarizes the conversation and updates a channel-specific section inside:

```text
MEMORY.md
```

This allows the bot to preserve useful facts, recurring context, preferences, and previous decisions across conversations.

The AI module uses the following files:

| File                        | Purpose                                  |
| --------------------------- | ---------------------------------------- |
| `conversation_history.json` | Stores AI interaction history            |
| `memory_state.json`         | Stores messages waiting to be summarized |
| `MEMORY.md`                 | Stores persistent summarized memory      |
| `logs.json`                 | Stores commands and AI interaction logs  |

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

### Modular Cog Architecture

The bot is divided into Discord cogs:

| File                | Responsibility                                                       |
| ------------------- | -------------------------------------------------------------------- |
| `bot.py`            | Main bot, events, shared state, database setup and extension loading |
| `llm_cog.py`        | AI conversations, models, retries and persistent memory              |
| `palavra_cog.py`    | Forbidden-word game and dictionary lookup                            |
| `propaganda_cog.py` | Advertisements and channel locking                                   |
| `first_cog.py`      | Daily first game, rankings and database commands                     |
| `caoticos_cog.py`   | Moderation and miscellaneous commands                                |

This structure keeps each feature group isolated and makes the bot easier to maintain and extend.

---

## Slash Commands

### AI Commands

| Command                 | Access    | Description                                  |
| ----------------------- | --------- | -------------------------------------------- |
| `/conversar mensagem`   | Everyone  | Sends a message to the AI assistant          |
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

---

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
| `logs.json`                 | Slash command and AI interaction logs     |
| `conversation_history.json` | AI interaction history                    |
| `memory_state.json`         | Pending AI memory buffers                 |
| `MEMORY.md`                 | Persistent summarized AI memory           |
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
├── llm_cog.py
├── palavra_cog.py
├── propaganda_cog.py
├── first_cog.py
├── caoticos_cog.py
├── requirements.txt
├── propagandas.json         # Local file, ignored by Git
├── images/                  # Local directory, ignored by Git
├── MEMORY.md                # Generated at runtime
├── memory_state.json        # Generated at runtime
├── conversation_history.json
├── discord_bot.db
└── logs.json
```
