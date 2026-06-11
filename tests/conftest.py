"""Shared fixtures and helpers for the test suite."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import cv2
import numpy as np
import pytest


def write_test_video(path, frame_count=5, fps=10.0, size=(64, 64)):
    """Writes a tiny solid-black AVI so cv2.VideoCapture can read real frames."""
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, size
    )
    frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    for _ in range(frame_count):
        writer.write(frame)
    writer.release()
    return path


def make_update(user_id=111, lang="pt", caption=None,
                with_photo=False, video=None, document=None):
    """Builds a minimal stand-in for telegram.Update used by the handlers."""
    photo = []
    if with_photo:
        telegram_file = SimpleNamespace(download_to_drive=AsyncMock())
        photo = [SimpleNamespace(get_file=AsyncMock(return_value=telegram_file))]

    message = SimpleNamespace(
        caption=caption,
        reply_text=AsyncMock(),
        reply_photo=AsyncMock(),
        photo=photo,
        video=video,
        document=document,
    )
    user = None
    if user_id is not None:
        user = SimpleNamespace(id=user_id, language_code=lang)
    return SimpleNamespace(effective_user=user, message=message)


def make_video_attachment(file_size=1024):
    telegram_file = SimpleNamespace(download_to_drive=AsyncMock())
    return SimpleNamespace(
        file_size=file_size,
        get_file=AsyncMock(return_value=telegram_file),
    )


@pytest.fixture
def history_file(tmp_path, monkeypatch):
    """Redirects the CSV history to a temporary file."""
    import history

    path = tmp_path / "counts.csv"
    monkeypatch.setattr(history, "HISTORY_FILE", path)
    return path
