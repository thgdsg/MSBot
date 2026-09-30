from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


class FirstRepository:
    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()

    def setup(self) -> None:
        with self._connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    first_count INTEGER
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS first_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    username TEXT,
                    timestamp TEXT
                )
                """
            )

    def update_user_first_count(self, user_id: str, username: str) -> int:
        with self._connection() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT first_count FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            if result:
                new_count = result[0] + 1
                cursor.execute(
                    "UPDATE users SET first_count = ?, username = ? WHERE user_id = ?",
                    (new_count, username, user_id),
                )
            else:
                new_count = 1
                cursor.execute(
                    "INSERT INTO users (user_id, username, first_count) VALUES (?, ?, ?)",
                    (user_id, username, new_count),
                )
        return new_count

    def log_first_event(self, user_id: str, username: str, timestamp: datetime) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO first_logs (user_id, username, timestamp) VALUES (?, ?, ?)",
                (user_id, username, timestamp.isoformat()),
            )

    def get_user(self, user_id: str) -> tuple[str, int] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT username, first_count FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return row

    def adjust_first_count(self, user_id: str, username: str, amount: int) -> int:
        """Adjust a user's total while keeping the database invariant >= 0."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT first_count FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            new_count = max(0, (int(row[0]) if row else 0) + amount)
            if row:
                connection.execute(
                    "UPDATE users SET first_count = ?, username = ? WHERE user_id = ?",
                    (new_count, username, user_id),
                )
            else:
                connection.execute(
                    "INSERT INTO users (user_id, username, first_count) VALUES (?, ?, ?)",
                    (user_id, username, new_count),
                )
        return new_count

    def get_top_users(self, offset: int, limit_end: int) -> list[tuple[str, int]]:
        with self._connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT username, first_count FROM users "
                "ORDER BY first_count DESC LIMIT ? OFFSET ?",
                (limit_end - offset, offset),
            )
            return cursor.fetchall()

    def get_top_users_with_ids(self, limit: int = 25) -> list[tuple[str, str, int]]:
        with self._connection() as connection:
            return connection.execute(
                "SELECT user_id, username, first_count FROM users "
                "ORDER BY first_count DESC, user_id ASC LIMIT ?",
                (limit,),
            ).fetchall()

    def count_users(self) -> int:
        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def get_top_users_for_month(self, year: int, month: int, limit: int = 10) -> list[tuple[str, int]]:
        month_str = f"{year}-{month:02d}"
        query = """
            SELECT u.username, COUNT(fl.log_id) AS monthly_first_count
            FROM first_logs fl
            JOIN users u ON fl.user_id = u.user_id
            WHERE strftime('%Y-%m', fl.timestamp) = ?
            GROUP BY fl.user_id
            ORDER BY monthly_first_count DESC
            LIMIT ?
        """
        with self._connection() as connection:
            return connection.execute(query, (month_str, limit)).fetchall()

    def get_monthly_firsts(self, year: int, month: int) -> list[tuple[str, str, int]]:
        month_str = f"{year}-{month:02d}"
        query = """
            SELECT fl.user_id, u.username, COUNT(fl.log_id) AS monthly_first_count
            FROM first_logs fl
            LEFT JOIN users u ON fl.user_id = u.user_id
            WHERE strftime('%Y-%m', fl.timestamp) = ?
            GROUP BY fl.user_id
            ORDER BY monthly_first_count DESC, fl.user_id ASC
        """
        with self._connection() as connection:
            return connection.execute(query, (month_str,)).fetchall()
