from datetime import datetime, timezone
import sqlite3
from contextlib import closing


class MessageRepository:
    """Counts observed messages, including deleted ones; never claims full history."""

    def __init__(self, path):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('tracking_since', ?)",
                       (datetime.now(timezone.utc).isoformat(),))
            db.execute("CREATE TABLE IF NOT EXISTS messages (message_id TEXT PRIMARY KEY, guild_id TEXT, user_id TEXT)")
            db.execute("CREATE INDEX IF NOT EXISTS message_author ON messages(guild_id, user_id)")

    def record(self, message_id, guild_id, user_id):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR IGNORE INTO messages VALUES (?, ?, ?)",
                       (str(message_id), str(guild_id), str(user_id)))

    def count(self, guild_id, user_id):
        with closing(sqlite3.connect(self.path)) as db, db:
            count = db.execute("SELECT COUNT(*) FROM messages WHERE guild_id=? AND user_id=?",
                               (str(guild_id), str(user_id))).fetchone()[0]
            since = db.execute("SELECT value FROM metadata WHERE key='tracking_since'").fetchone()[0]
        return {"user_id": str(user_id), "server_id": str(guild_id), "message_count": count,
                "tracking_since": since, "is_lifetime_total": False,
                "limitations": "Conta mensagens humanas recebidas enquanto o bot esta online desde tracking_since; inclui apagadas. Historico anterior nao importado."}
