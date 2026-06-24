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
    # Migrate older DBs that predate later columns.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(messages)")]
    if "ts" not in cols:
        conn.execute("ALTER TABLE messages ADD COLUMN ts REAL NOT NULL DEFAULT 0")
    if "message_id" not in cols:
        conn.execute("ALTER TABLE messages ADD COLUMN message_id INTEGER NOT NULL DEFAULT 0")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat ON messages(chat_id, id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_msgid ON messages(chat_id, message_id)"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS settings (
               key   TEXT PRIMARY KEY,
               value TEXT
           )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS reactions (
               id          INTEGER PRIMARY KEY AUTOINCREMENT,
               chat_id     INTEGER NOT NULL,
               user_name   TEXT    NOT NULL,
               emoji       TEXT    NOT NULL,
               target_user TEXT    NOT NULL DEFAULT ''
           )"""
    )
    rcols = [r[1] for r in conn.execute("PRAGMA table_info(reactions)")]
    if "target_user" not in rcols:
        conn.execute("ALTER TABLE reactions ADD COLUMN target_user TEXT NOT NULL DEFAULT ''")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS gifs (
               id      INTEGER PRIMARY KEY AUTOINCREMENT,
               pool    TEXT NOT NULL,
               file_id TEXT NOT NULL
           )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS aliases (
               alias  TEXT PRIMARY KEY,
               target TEXT NOT NULL
           )"""
    )
    conn.commit()
    return conn


def log_message(conn: sqlite3.Connection, chat_id: int, user_name: str,
                text: str, keep: int = 500, ts: float = None,
                message_id: int = 0) -> None:
    if ts is None:
        ts = time.time()
    conn.execute(
        "INSERT INTO messages (chat_id, user_name, text, ts, message_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (chat_id, user_name, text, ts, message_id),
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


def set_alias(conn: sqlite3.Connection, alias: str, target: str) -> None:
    conn.execute(
        "INSERT INTO aliases (alias, target) VALUES (?, ?) "
        "ON CONFLICT(alias) DO UPDATE SET target = excluded.target",
        (alias.lower(), target),
    )
    conn.commit()


def get_alias(conn: sqlite3.Connection, alias: str):
    row = conn.execute(
        "SELECT target FROM aliases WHERE alias = ?", (alias.lower(),)
    ).fetchone()
    return row[0] if row else None


def list_aliases(conn: sqlite3.Connection):
    return conn.execute("SELECT alias, target FROM aliases ORDER BY alias").fetchall()


def del_alias(conn: sqlite3.Connection, alias: str) -> int:
    cur = conn.execute("DELETE FROM aliases WHERE alias = ?", (alias.lower(),))
    conn.commit()
    return cur.rowcount


def get_recent_by_user(conn: sqlite3.Connection, chat_id: int, name: str, n: int):
    """Last `n` messages whose author name contains `name` (case-insensitive).

    Filtering is done in Python because SQLite's LOWER() only handles ASCII,
    not Cyrillic.
    """
    needle = name.lower()
    rows = conn.execute(
        "SELECT user_name, text FROM messages WHERE chat_id = ? ORDER BY id DESC",
        (chat_id,),
    ).fetchall()
    matched = [(u, t) for (u, t) in rows if needle in u.lower()][:n]
    return list(reversed(matched))


def get_since(conn: sqlite3.Connection, chat_id: int, since_ts: float):
    """Return messages for a chat with ts >= since_ts, oldest first."""
    return conn.execute(
        "SELECT user_name, text FROM messages WHERE chat_id = ? AND ts >= ? "
        "ORDER BY id ASC",
        (chat_id, since_ts),
    ).fetchall()


def author_by_message(conn: sqlite3.Connection, chat_id: int, message_id: int):
    """Who wrote a given message, or None if it isn't in our log."""
    if not message_id:
        return None
    row = conn.execute(
        "SELECT user_name FROM messages WHERE chat_id = ? AND message_id = ? "
        "ORDER BY id DESC LIMIT 1",
        (chat_id, message_id),
    ).fetchone()
    return row[0] if row else None


def log_reaction(conn: sqlite3.Connection, chat_id: int, user_name: str,
                 emoji: str, target_user: str = "") -> None:
    conn.execute(
        "INSERT INTO reactions (chat_id, user_name, emoji, target_user) "
        "VALUES (?, ?, ?, ?)",
        (chat_id, user_name, emoji, target_user),
    )
    conn.commit()


def received_counts(conn: sqlite3.Connection, chat_id: int):
    """Per-author total reactions their messages received, most first."""
    return conn.execute(
        "SELECT target_user, COUNT(*) c FROM reactions "
        "WHERE chat_id = ? AND target_user <> '' AND target_user <> '?' "
        "GROUP BY target_user ORDER BY c DESC",
        (chat_id,),
    ).fetchall()


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


def add_gif(conn: sqlite3.Connection, pool: str, file_id: str) -> int:
    """Add a gif to a pool; return the pool's new size."""
    conn.execute("INSERT INTO gifs (pool, file_id) VALUES (?, ?)", (pool, file_id))
    conn.commit()
    return conn.execute(
        "SELECT COUNT(*) FROM gifs WHERE pool = ?", (pool,)
    ).fetchone()[0]


def random_gif(conn: sqlite3.Connection, pool: str):
    """A random file_id from the pool, or None if empty."""
    row = conn.execute(
        "SELECT file_id FROM gifs WHERE pool = ? ORDER BY RANDOM() LIMIT 1",
        (pool,),
    ).fetchone()
    return row[0] if row else None


def gif_pools(conn: sqlite3.Connection):
    """List of (pool, count), most populated first."""
    return conn.execute(
        "SELECT pool, COUNT(*) c FROM gifs GROUP BY pool ORDER BY c DESC"
    ).fetchall()


def delete_pool(conn: sqlite3.Connection, pool: str) -> int:
    """Delete all gifs in a pool; return how many were removed."""
    cur = conn.execute("DELETE FROM gifs WHERE pool = ?", (pool,))
    conn.commit()
    return cur.rowcount


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
