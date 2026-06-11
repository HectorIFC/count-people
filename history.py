"""CSV history persistence. Schema is compatible with the Colab notebook."""

import csv
import os
from datetime import datetime
from pathlib import Path

from analysis import AGE_GROUPS, GENDERS, CountResult

HISTORY_FILE = Path(os.environ.get("HISTORY_FILE", "counts.csv"))

MAX_LABEL_LENGTH = 64


def sanitize_label(label: str) -> str:
    """User-supplied text that ends up in the CSV: strip control characters,
    truncate, and drop leading formula characters (CSV injection)."""
    cleaned = "".join(ch for ch in label if ch.isprintable())
    cleaned = cleaned.strip().lstrip("=+-@").strip()
    return cleaned[:MAX_LABEL_LENGTH]


def append_to_history(result: CountResult, event_label: str) -> None:
    header = (
        ["timestamp", "event", "total_people", "analyzed_individuals"]
        + [f"{age_group}_{gender}" for age_group in AGE_GROUPS for gender in GENDERS]
        + ["source"]
    )
    row = (
        [datetime.now().strftime("%Y-%m-%d %H:%M"), sanitize_label(event_label),
         result.total_people, result.analyzed_individuals]
        + [result.demographics.get(f"{age_group}_{gender}", 0)
           for age_group in AGE_GROUPS for gender in GENDERS]
        + [result.source_name]
    )

    needs_header = not HISTORY_FILE.exists()
    # 0600: history is only readable by the account running the bot.
    fd = os.open(HISTORY_FILE, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        if needs_header:
            writer.writerow(header)
        writer.writerow(row)
