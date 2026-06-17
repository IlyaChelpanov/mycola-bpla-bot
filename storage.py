"""SQLite-backed message log + key/value settings.

Telegram's Bot API cannot fetch past history, so the bot logs every group
message as it arrives. Only the last `keep` messages per chat are retained.
"""
import sqlite3


def init_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS messages (
               id        INTEGER PRIMARY KEY AUTOINCREMENT,
               chat_id   INTEGER NOT NULL,
               user_name TEXT    NOT NULL,
               text      TEXT    NOT NULL
           )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat ON messages(chat_id, id)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS settings (
               key   TEXT PRIMARY KEY,
               value TEXT
           )"""
    )
    conn.commit()
    return conn


def log_message(conn: sqlite3.Connection, chat_id: int, user_name: str,
                text: str, keep: int = 500) -> None:
    conn.execute(
        "INSERT INTO messages (chat_id, user_name, text) VALUES (?, ?, ?)",
        (chat_id, user_name, text),
    )
    # Prune everything older than the most recent `keep` rows for this chat.
    conn.execute(
        """DELETE FROM messages
           WHERE chat_id = ?
             AND id NOT IN (
                 SELECT id FROM messages WHERE chat_id = ?
                 ORDER BY id DESC LIMIT ?
             )""",
        (chat_id, chat_id, keep),
    )
    conn.commit()


def get_recent(conn: sqlite3.Connection, chat_id: int, n: int):
    """Return up to the last `n` messages for a chat, oldest first."""
    rows = conn.execute(
        "SELECT user_name, text FROM messages WHERE chat_id = ? "
        "ORDER BY id DESC LIMIT ?",
        (chat_id, n),
    ).fetchall()
    return list(reversed(rows))


def get_setting(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
