from bot import should_respond, strip_mention

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


def test_responds_on_reply_to_bot():
    m = _msg(text="ответ", reply_to_id=BOT_ID)
    assert should_respond(m, BOT_USERNAME, BOT_ID) is True


def test_ignores_reply_to_other_user():
    m = _msg(text="ответ", reply_to_id=99999)
    assert should_respond(m, BOT_USERNAME, BOT_ID) is False


def test_ignores_plain_message():
    m = _msg(text="просто болтаю")
    assert should_respond(m, BOT_USERNAME, BOT_ID) is False


def test_ignores_empty_text():
    m = _msg(text=None)
    assert should_respond(m, BOT_USERNAME, BOT_ID) is False


def test_strip_mention():
    assert strip_mention("@MycolaBPLABot как дела", BOT_USERNAME) == "как дела"
    assert strip_mention("без упоминания", BOT_USERNAME) == "без упоминания"
