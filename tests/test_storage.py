import storage


def _db():
    return storage.init_db(":memory:")


def test_log_and_get_recent_order():
    conn = _db()
    for i in range(3):
        storage.log_message(conn, chat_id=1, user_name="u", text=f"m{i}")
    rows = storage.get_recent(conn, 1, 10)
    assert [r[1] for r in rows] == ["m0", "m1", "m2"]  # oldest first


def test_get_recent_limit():
    conn = _db()
    for i in range(10):
        storage.log_message(conn, 1, "u", f"m{i}")
    rows = storage.get_recent(conn, 1, 3)
    assert [r[1] for r in rows] == ["m7", "m8", "m9"]


def test_prune_keeps_last_n():
    conn = _db()
    for i in range(10):
        storage.log_message(conn, 1, "u", f"m{i}", keep=5)
    rows = storage.get_recent(conn, 1, 100)
    assert len(rows) == 5
    assert [r[1] for r in rows] == ["m5", "m6", "m7", "m8", "m9"]


def test_messages_isolated_per_chat():
    conn = _db()
    storage.log_message(conn, 1, "a", "chat1")
    storage.log_message(conn, 2, "b", "chat2")
    assert [r[1] for r in storage.get_recent(conn, 1, 10)] == ["chat1"]
    assert [r[1] for r in storage.get_recent(conn, 2, 10)] == ["chat2"]


def test_get_since_filters_by_ts():
    conn = _db()
    storage.log_message(conn, 1, "u", "old", ts=100.0)
    storage.log_message(conn, 1, "u", "new", ts=200.0)
    rows = storage.get_since(conn, 1, since_ts=150.0)
    assert [r[1] for r in rows] == ["new"]


def test_reaction_counts_per_user_sorted():
    conn = _db()
    storage.log_reaction(conn, 1, "Олег", "🔥")
    storage.log_reaction(conn, 1, "Олег", "👍")
    storage.log_reaction(conn, 1, "Аня", "🔥")
    rows = storage.reaction_counts(conn, 1)
    assert rows == [("Олег", 2), ("Аня", 1)]


def test_reaction_counts_isolated_per_chat():
    conn = _db()
    storage.log_reaction(conn, 1, "Олег", "🔥")
    storage.log_reaction(conn, 2, "Аня", "🔥")
    assert storage.reaction_counts(conn, 1) == [("Олег", 1)]


def test_reaction_counts_by_emoji():
    conn = _db()
    storage.log_reaction(conn, 1, "Олег", "💊")
    storage.log_reaction(conn, 1, "Олег", "💊")
    storage.log_reaction(conn, 1, "Аня", "💊")
    storage.log_reaction(conn, 1, "Аня", "🔥")
    assert storage.reaction_counts_by_emoji(conn, 1, "💊") == [("Олег", 2), ("Аня", 1)]
    assert storage.reaction_counts_by_emoji(conn, 1, "🔥") == [("Аня", 1)]


def test_bump_daily_image_limit_and_reset():
    conn = _db()
    assert storage.bump_daily_image(conn, "2026-06-17", limit=2) is True
    assert storage.bump_daily_image(conn, "2026-06-17", limit=2) is True
    assert storage.bump_daily_image(conn, "2026-06-17", limit=2) is False  # over
    # new day resets the counter
    assert storage.bump_daily_image(conn, "2026-06-18", limit=2) is True


def test_gif_add_random_pools_delete():
    conn = _db()
    assert storage.random_gif(conn, "ignore") is None
    assert storage.add_gif(conn, "ignore", "fid1") == 1
    assert storage.add_gif(conn, "ignore", "fid2") == 2
    assert storage.add_gif(conn, "greet", "fid3") == 1
    assert storage.random_gif(conn, "ignore") in ("fid1", "fid2")
    assert storage.gif_pools(conn) == [("ignore", 2), ("greet", 1)]
    assert storage.delete_pool(conn, "ignore") == 2
    assert storage.random_gif(conn, "ignore") is None
    assert storage.gif_pools(conn) == [("greet", 1)]


def test_settings_get_set_default():
    conn = _db()
    assert storage.get_setting(conn, "k", "def") == "def"
    storage.set_setting(conn, "k", "v1")
    assert storage.get_setting(conn, "k", "def") == "v1"
    storage.set_setting(conn, "k", "v2")  # upsert
    assert storage.get_setting(conn, "k") == "v2"
