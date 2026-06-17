"""SQLite-backed message log + key/value settings.

Telegram's Bot API cannot fetch past history, so the bot logs every group
message as it arrives. Only the last `keep` messages per chat are retained.
"""
import sqlite3
import time


def init_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS messages (
               id        INTEGER PRIMARY KEY AUTOINCREMENT,
               chat_id   INTEGER NOT NULL,
               user_name TEXT    NOT NULL,
               text      TEXT    NOT NULL,
               ts        REAL    NOT NULL DEFAULT 0
           )"""
    )
    # Migrate older DBs that predate the ts column.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(messages)")]
    if "ts" not in cols:
        conn.execute("ALTER TABLE messages ADD COLUMN ts REAL NOT NULL DEFAULT 0")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat ON messages(chat_id, id)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS settings (
               key   TEXT PRIMARY KEY,
               value TEXT
           )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS reactions (
               id        INTEGER PRIMARY KEY AUTOINCREMENT,
               chat_id   INTEGER NOT NULL,
               user_name TEXT    NOT NULL,
               emoji     TEXT    NOT NULL
           )"""
    )
    conn.commit()
    return conn


def log_message(conn: sqlite3.Connection, chat_id: int, user_name: str,
                text: str, keep: int = 500, ts: float = None) -> None:
    if ts is None:
        ts = time.time()
    conn.execute(
        "INSERT INTO messages (chat_id, user_name, text, ts) VALUES (?, ?, ?, ?)",
        (chat_id, user_name, text, ts),
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


def get_since(conn: sqlite3.Connection, chat_id: int, since_ts: float):
    """Return messages for a chat with ts >= since_ts, oldest first."""
    return conn.execute(
        "SELECT user_name, text FROM messages WHERE chat_id = ? AND ts >= ? "
        "ORDER BY id ASC",
        (chat_id, since_ts),
    ).fetchall()


def log_reaction(conn: sqlite3.Connection, chat_id: int, user_name: str,
                 emoji: str) -> None:
    conn.execute(
        "INSERT INTO reactions (chat_id, user_name, emoji) VALUES (?, ?, ?)",
        (chat_id, user_name, emoji),
    )
    conn.commit()


def reaction_counts(conn: sqlite3.Connection, chat_id: int):
    """Per-user total reactions placed, most first: [(user_name, count), ...]."""
    return conn.execute(
        "SELECT user_name, COUNT(*) c FROM reactions WHERE chat_id = ? "
        "GROUP BY user_name ORDER BY c DESC",
        (chat_id,),
    ).fetchall()


def reaction_counts_by_emoji(conn: sqlite3.Connection, chat_id: int, emoji: str):
    """Per-user count of a specific emoji, most first."""
    return conn.execute(
        "SELECT user_name, COUNT(*) c FROM reactions WHERE chat_id = ? AND emoji = ? "
        "GROUP BY user_name ORDER BY c DESC",
        (chat_id, emoji),
    ).fetchall()


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


def bump_daily_image(conn: sqlite3.Connection, day: str, limit: int) -> bool:
    """Increment today's image counter. Return False if the daily limit is hit."""
    cur_day = get_setting(conn, "img_day", "")
    cnt = int(get_setting(conn, "img_count", "0"))
    if cur_day != day:
        cur_day, cnt = day, 0
    if cnt >= limit:
        set_setting(conn, "img_day", cur_day)
        set_setting(conn, "img_count", str(cnt))
        return False
    set_setting(conn, "img_day", day)
    set_setting(conn, "img_count", str(cnt + 1))
    return True
