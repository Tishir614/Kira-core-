from pathlib import Path


def test_callback_responses_do_not_assume_accessible_message():
    source = Path("app/bot/main.py").read_text(encoding="utf-8")
    review = source[source.index("async def review") : source.index("async def cancel")]
    assert "query.message.answer" not in review
    assert "query.bot.send_message" in review


def test_optional_message_user_is_checked_before_revision():
    source = Path("app/bot/main.py").read_text(encoding="utf-8")
    correction = source[source.index("async def correction") :]
    assert "if message.from_user is None:" in correction
    assert correction.index("if message.from_user is None:") < correction.index("message.from_user.id")
