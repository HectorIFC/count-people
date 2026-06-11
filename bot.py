"""Telegram bot: receives photos/videos and replies with people counts.

Replies are localized (pt/en/es) based on the sender's Telegram client language.

Environment variables:
  TELEGRAM_BOT_TOKEN     (required) token from @BotFather
  ALLOWED_USER_IDS       (required) comma-separated Telegram user ids
  SEND_ANNOTATED_PREVIEW (optional) "true" to reply with the annotated image
  HISTORY_FILE           (optional) CSV path, default ./counts.csv
  MODELS_DIR             (optional) weights cache dir, default ./models
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path

import cv2
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from analysis import PeopleCounter, probe_video_stats
from history import append_to_history, sanitize_label
from messages import format_summary, message, resolve_language

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    level=logging.INFO)
# httpx logs the full URL of every request -- which contains the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("people_counter_bot")

# Telegram Bot API refuses to serve files larger than this to bots.
TELEGRAM_BOT_DOWNLOAD_LIMIT_BYTES = 20 * 1024 * 1024

people_counter: PeopleCounter | None = None


def parse_allowed_user_ids() -> frozenset[int]:
    raw = os.environ.get("ALLOWED_USER_IDS", "").strip()
    if not raw:
        return frozenset()
    return frozenset(int(user_id) for user_id in raw.split(","))


ALLOWED_USER_IDS = parse_allowed_user_ids()
SEND_ANNOTATED_PREVIEW = os.environ.get("SEND_ANNOTATED_PREVIEW", "").lower() == "true"


def is_authorized(update: Update) -> bool:
    """Allowlist check. Unauthorized senders are logged and never answered,
    so the bot does not reveal its existence to strangers."""
    user = update.effective_user
    if user is not None and user.id in ALLOWED_USER_IDS:
        return True
    logger.warning("Ignored message from unauthorized user: %s",
                   user.id if user else "unknown")
    return False


def language_of(update: Update) -> str:
    return resolve_language(update.effective_user.language_code)


def event_label_from(update: Update, lang: str) -> str:
    label = sanitize_label(update.message.caption or "")
    return label or message("default_event_label", lang)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    await update.message.reply_text(message("start", language_of(update)))


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return

    lang = language_of(update)
    event_label = event_label_from(update, lang)
    await update.message.reply_text(message("photo_received", lang))

    highest_resolution_photo = update.message.photo[-1]
    telegram_file = await highest_resolution_photo.get_file()

    with tempfile.TemporaryDirectory() as temp_dir:
        photo_path = Path(temp_dir) / "input_photo.jpg"
        await telegram_file.download_to_drive(photo_path)
        try:
            # Inference is CPU/GPU-bound: run off the event loop.
            result, annotated_image = await asyncio.to_thread(
                people_counter.analyze, str(photo_path)
            )
        except Exception:
            logger.exception("Photo analysis failed")
            await update.message.reply_text(message("photo_failed", lang))
            return
    # TemporaryDirectory cleanup deletes the photo (privacy: keep numbers only).

    append_to_history(result, event_label)
    await update.message.reply_text(format_summary(result, event_label, lang))

    if SEND_ANNOTATED_PREVIEW:
        ok, encoded = cv2.imencode(".jpg", annotated_image)
        if ok:
            await update.message.reply_photo(
                photo=bytes(encoded.tobytes()),
                caption=message("annotated_caption", lang),
            )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return

    lang = language_of(update)
    video = update.message.video or update.message.document
    if video.file_size and video.file_size > TELEGRAM_BOT_DOWNLOAD_LIMIT_BYTES:
        await update.message.reply_text(message("video_too_large", lang))
        return

    event_label = event_label_from(update, lang)
    telegram_file = await video.get_file()

    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = Path(temp_dir) / "input_video.mp4"
        await telegram_file.download_to_drive(video_path)

        try:
            stats = probe_video_stats(str(video_path))
            await update.message.reply_text(
                message("video_received", lang,
                        duration=stats.duration_seconds, frames=stats.frame_count)
            )
            result = await asyncio.to_thread(
                people_counter.analyze_video, str(video_path)
            )
        except Exception:
            logger.exception("Video analysis failed")
            await update.message.reply_text(message("video_failed", lang))
            return
    # TemporaryDirectory cleanup deletes the video (privacy: keep numbers only).

    append_to_history(result, event_label)
    await update.message.reply_text(format_summary(result, event_label, lang))


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Set the TELEGRAM_BOT_TOKEN environment variable.")
    if not ALLOWED_USER_IDS:
        # Fail closed: without an allowlist anyone who finds the bot could use it.
        raise SystemExit(
            "Set ALLOWED_USER_IDS (comma-separated ids). "
            "The bot does not start without an allowlist."
        )

    global people_counter
    logger.info("Loading models (first run downloads ~250 MB)...")
    people_counter = PeopleCounter()
    logger.info("Models ready (device: %s).", people_counter.device)

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video)
    )

    logger.info("Bot running (long polling). Ctrl+C to stop.")
    application.run_polling()


if __name__ == "__main__":  # pragma: no cover
    main()
