from unittest.mock import MagicMock, patch

from bot import (
    should_respond, strip_mention, summary_intent, reaction_delta, parse_period,
    pick_photo, build_search_fn,
)


class _Photo:
    def __init__(self, width):
        self.width = width


def test_pick_photo_prefers_modest_size():
    photos = [_Photo(90), _Photo(320), _Photo(800), _Photo(1280)]
    assert pick_photo(photos).width == 320  # largest <= 768


def test_pick_photo_falls_back_to_smallest():
    photos = [_Photo(1000), _Photo(2000)]
    assert pick_photo(photos).width == 1000


def _photo_msg(caption=None, reply_to_id=None):
    class M:
        pass
    m = M()
    m.text = None
    m.caption = caption
    if reply_to_id is not None:
        r = M(); rf = M(); rf.id = reply_to_id; r.from_user = rf
        m.reply_to_message = r
    else:
        m.reply_to_message = None
    return m


def test_should_respond_photo_caption_mention():
    assert should_respond(_photo_msg(caption="@MycolaBPLABot гляди"), "MycolaBPLABot", 1)


def test_should_respond_photo_no_mention():
    assert not should_respond(_photo_msg(caption="просто фото"), "MycolaBPLABot", 1)

BOT_USERNAME = "MycolaBPLABot"
BOT_ID = 12345


def _msg(text=None, reply_to_id=None):
    class M:
        pass
    m = M()
    m.text = text
    if reply_to_id is not None:
        r = M()
        rf = M()
        rf.id = reply_to_id
        r.from_user = rf
        m.reply_to_message = r
    else:
        m.reply_to_message = None
    return m


def test_responds_on_mention():
    m = _msg(text="@MycolaBPLABot привет")
    assert should_respond(m, BOT_USERNAME, BOT_ID) is True


def test_reply_to_bot_only_when_reply_mode_on():
    m = _msg(text="ответ", reply_to_id=BOT_ID)
    assert should_respond(m, BOT_USERNAME, BOT_ID, reply_mode=True) is True
    assert should_respond(m, BOT_USERNAME, BOT_ID, reply_mode=False) is False


def test_reply_mode_default_off_ignores_reply():
    m = _msg(text="ответ", reply_to_id=BOT_ID)
    assert should_respond(m, BOT_USERNAME, BOT_ID) is False  # default off


def test_mention_responds_regardless_of_reply_mode():
    m = _msg(text="@MycolaBPLABot привет", reply_to_id=BOT_ID)
    assert should_respond(m, BOT_USERNAME, BOT_ID, reply_mode=False) is True


def test_ignores_reply_to_other_user():
    m = _msg(text="ответ", reply_to_id=99999)
    assert should_respond(m, BOT_USERNAME, BOT_ID, reply_mode=True) is False


def test_ignores_plain_message():
    m = _msg(text="просто болтаю")
    assert should_respond(m, BOT_USERNAME, BOT_ID) is False


def test_ignores_empty_text():
    m = _msg(text=None)
    assert should_respond(m, BOT_USERNAME, BOT_ID) is False


def test_strip_mention():
    assert strip_mention("@MycolaBPLABot как дела", BOT_USERNAME) == "как дела"
    assert strip_mention("без упоминания", BOT_USERNAME) == "без упоминания"


def test_summary_intent_true():
    assert summary_intent("сделай саммари последних сообщений")
    assert summary_intent("о чём тут говорили?")
    assert summary_intent("перескажи что было")


def test_summary_intent_false():
    assert not summary_intent("какая погода для дрона")
    assert not summary_intent("привет")


def test_reaction_delta_added():
    assert reaction_delta([], ["🔥"]) == ["🔥"]
    assert reaction_delta(["🔥"], ["🔥", "👍"]) == ["👍"]


def test_reaction_delta_removal_not_counted():
    assert reaction_delta(["🔥", "👍"], ["🔥"]) == []


def test_reaction_delta_no_change():
    assert reaction_delta(["🔥"], ["🔥"]) == []


def test_parse_period():
    assert parse_period("саммари за сегодня") == 24 * 3600
    assert parse_period("о чём за 2 часа") == 7200
    assert parse_period("перескажи за 30 минут") == 1800
    assert parse_period("за неделю что было") == 7 * 24 * 3600
    assert parse_period("за час") == 3600


def test_parse_period_none():
    assert parse_period("сделай саммари") is None
    assert parse_period("о чём тут говорили") is None


def test_build_search_fn_none_when_inactive():
    cfg = MagicMock()
    cfg.web_search_active.return_value = False
    assert build_search_fn(cfg) is None


def test_build_search_fn_uses_tavily_when_active():
    cfg = MagicMock()
    cfg.web_search_active.return_value = True
    cfg.tavily_api_key = "tvly-x"
    with patch("bot.websearch.search", return_value="res") as mk:
        fn = build_search_fn(cfg)
        out = fn("погода Киев")
    assert out == "res"
    mk.assert_called_once_with("погода Киев", api_key="tvly-x")
