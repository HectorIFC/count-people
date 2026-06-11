"""Tests for bot.py: authorization, localization and the Telegram handlers
(with the Telegram API and the model fully mocked)."""

import asyncio
import logging
from collections import Counter
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

import bot
from analysis import CountResult, VideoStats
from conftest import make_update, make_video_attachment
from messages import format_summary, message

RESULT = CountResult("input.jpg", 13, 12, Counter({"adult_M": 4, "adult_F": 8}))
ANNOTATED = np.zeros((8, 8, 3), dtype=np.uint8)


@pytest.fixture
def allowlist(monkeypatch):
    monkeypatch.setattr(bot, "ALLOWED_USER_IDS", frozenset({111}))


@pytest.fixture
def history_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(bot, "append_to_history",
                        lambda result, label: calls.append((result, label)))
    return calls


# ------------------------------ configuration ------------------------------

def test_parse_allowed_user_ids(monkeypatch):
    monkeypatch.setenv("ALLOWED_USER_IDS", "1, 2,3")
    assert bot.parse_allowed_user_ids() == frozenset({1, 2, 3})


def test_parse_allowed_user_ids_empty(monkeypatch):
    monkeypatch.delenv("ALLOWED_USER_IDS", raising=False)
    assert bot.parse_allowed_user_ids() == frozenset()
    monkeypatch.setenv("ALLOWED_USER_IDS", "   ")
    assert bot.parse_allowed_user_ids() == frozenset()


# ------------------------------ authorization ------------------------------

def test_authorized_user(allowlist):
    assert bot.is_authorized(make_update(user_id=111)) is True


def test_unknown_user_is_rejected_and_logged(allowlist, caplog):
    with caplog.at_level(logging.WARNING, logger="people_counter_bot"):
        assert bot.is_authorized(make_update(user_id=222)) is False
    assert "222" in caplog.text


def test_missing_user_is_rejected(allowlist):
    assert bot.is_authorized(make_update(user_id=None)) is False


# ------------------------------ localization ------------------------------

@pytest.mark.parametrize("lang, expected", [
    ("pt-br", "pt"), ("es-ES", "es"), ("fr", "en"),
])
def test_language_of(lang, expected):
    assert bot.language_of(make_update(lang=lang)) == expected


@pytest.mark.parametrize("caption, lang, expected", [
    (None, "pt", "Evento"),
    (None, "en", "Event"),
    ("   ", "en", "Event"),
    ("=Festa", "pt", "Festa"),
    ("Sunday meeting", "en", "Sunday meeting"),
])
def test_event_label_from(caption, lang, expected):
    assert bot.event_label_from(make_update(caption=caption), lang) == expected


# ------------------------------ /start ------------------------------

def test_start_replies_in_sender_language(allowlist):
    update = make_update(user_id=111, lang="es")
    asyncio.run(bot.handle_start(update, None))
    update.message.reply_text.assert_awaited_once_with(message("start", "es"))


def test_start_ignores_unauthorized(allowlist):
    update = make_update(user_id=999)
    asyncio.run(bot.handle_start(update, None))
    update.message.reply_text.assert_not_awaited()


# ------------------------------ photos ------------------------------

def test_photo_happy_path(allowlist, history_calls, monkeypatch):
    monkeypatch.setattr(bot, "people_counter",
                        SimpleNamespace(analyze=lambda path: (RESULT, ANNOTATED)))
    update = make_update(user_id=111, lang="en", caption="Party", with_photo=True)

    asyncio.run(bot.handle_photo(update, None))

    replies = [call.args[0] for call in update.message.reply_text.await_args_list]
    assert replies == [
        message("photo_received", "en"),
        format_summary(RESULT, "Party", "en"),
    ]
    assert history_calls == [(RESULT, "Party")]
    update.message.reply_photo.assert_not_awaited()

    downloaded_path = update.message.photo[-1].get_file.return_value \
        .download_to_drive.await_args.args[0]
    assert downloaded_path.name == "input_photo.jpg"


def test_photo_failure_replies_error(allowlist, history_calls, monkeypatch):
    def boom(path):
        raise RuntimeError("inference exploded")

    monkeypatch.setattr(bot, "people_counter", SimpleNamespace(analyze=boom))
    update = make_update(user_id=111, lang="pt", with_photo=True)

    asyncio.run(bot.handle_photo(update, None))

    replies = [call.args[0] for call in update.message.reply_text.await_args_list]
    assert replies == [message("photo_received", "pt"),
                       message("photo_failed", "pt")]
    assert history_calls == []


def test_photo_annotated_preview(allowlist, history_calls, monkeypatch):
    monkeypatch.setattr(bot, "people_counter",
                        SimpleNamespace(analyze=lambda path: (RESULT, ANNOTATED)))
    monkeypatch.setattr(bot, "SEND_ANNOTATED_PREVIEW", True)
    update = make_update(user_id=111, lang="es", with_photo=True)

    asyncio.run(bot.handle_photo(update, None))

    update.message.reply_photo.assert_awaited_once()
    assert update.message.reply_photo.await_args.kwargs["caption"] == \
        message("annotated_caption", "es")


def test_photo_ignores_unauthorized(allowlist, history_calls):
    update = make_update(user_id=999, with_photo=True)
    asyncio.run(bot.handle_photo(update, None))
    update.message.reply_text.assert_not_awaited()
    assert history_calls == []


# ------------------------------ videos ------------------------------

def test_video_too_large_is_refused(allowlist, history_calls):
    attachment = make_video_attachment(file_size=21 * 1024 * 1024)
    update = make_update(user_id=111, lang="en", video=attachment)

    asyncio.run(bot.handle_video(update, None))

    update.message.reply_text.assert_awaited_once_with(
        message("video_too_large", "en"))
    attachment.get_file.assert_not_awaited()
    assert history_calls == []


def test_video_happy_path(allowlist, history_calls, monkeypatch):
    monkeypatch.setattr(bot, "probe_video_stats",
                        lambda path: VideoStats(frame_count=343, fps=25.0))
    monkeypatch.setattr(bot, "people_counter",
                        SimpleNamespace(analyze_video=lambda path: RESULT))
    attachment = make_video_attachment(file_size=1024)
    update = make_update(user_id=111, lang="pt", caption="Show", video=attachment)

    asyncio.run(bot.handle_video(update, None))

    replies = [call.args[0] for call in update.message.reply_text.await_args_list]
    assert replies == [
        message("video_received", "pt", duration=13.72, frames=343),
        format_summary(RESULT, "Show", "pt"),
    ]
    assert history_calls == [(RESULT, "Show")]


def test_video_sent_as_document(allowlist, history_calls, monkeypatch):
    monkeypatch.setattr(bot, "probe_video_stats",
                        lambda path: VideoStats(frame_count=10, fps=10.0))
    monkeypatch.setattr(bot, "people_counter",
                        SimpleNamespace(analyze_video=lambda path: RESULT))
    attachment = make_video_attachment(file_size=2048)
    update = make_update(user_id=111, lang="en", video=None, document=attachment)

    asyncio.run(bot.handle_video(update, None))

    assert history_calls != []


def test_video_failure_replies_error(allowlist, history_calls, monkeypatch):
    def boom(path):
        raise ValueError("bad file")

    monkeypatch.setattr(bot, "probe_video_stats", boom)
    attachment = make_video_attachment(file_size=1024)
    update = make_update(user_id=111, lang="es", video=attachment)

    asyncio.run(bot.handle_video(update, None))

    replies = [call.args[0] for call in update.message.reply_text.await_args_list]
    assert replies == [message("video_failed", "es")]
    assert history_calls == []


def test_video_ignores_unauthorized(allowlist, history_calls):
    update = make_update(user_id=999, video=make_video_attachment())
    asyncio.run(bot.handle_video(update, None))
    update.message.reply_text.assert_not_awaited()


# ------------------------------ main ------------------------------

def test_main_requires_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="TELEGRAM_BOT_TOKEN"):
        bot.main()


def test_main_requires_allowlist(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setattr(bot, "ALLOWED_USER_IDS", frozenset())
    with pytest.raises(SystemExit, match="ALLOWED_USER_IDS"):
        bot.main()


def test_main_wires_handlers_and_polls(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setattr(bot, "ALLOWED_USER_IDS", frozenset({111}))
    monkeypatch.setattr(bot, "PeopleCounter",
                        lambda: SimpleNamespace(device="cpu"))

    application = MagicMock()
    builder = MagicMock()
    builder.token.return_value.build.return_value = application
    monkeypatch.setattr(bot, "Application",
                        SimpleNamespace(builder=lambda: builder))

    bot.main()

    builder.token.assert_called_once_with("123:abc")
    assert application.add_handler.call_count == 3
    application.run_polling.assert_called_once()
    assert bot.people_counter.device == "cpu"
