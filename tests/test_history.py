"""Tests for history.py: label sanitization and CSV persistence."""

import csv
import os
from collections import Counter

import pytest

from analysis import CountResult
from history import MAX_LABEL_LENGTH, append_to_history, sanitize_label


@pytest.mark.parametrize("raw, expected", [
    ("Reuniao de domingo", "Reuniao de domingo"),
    ("  com espacos  ", "com espacos"),
    ("=HYPERLINK(1)", "HYPERLINK(1)"),          # formula prefix dropped
    ("+55 11 99999", "55 11 99999"),
    ("@canal", "canal"),
    ("-- Evento --", "Evento --"),              # only LEADING formula chars
    ("=+-@combo", "combo"),
    ("meio-dia", "meio-dia"),                   # inner dashes preserved
    ("com\x00controle\x1b", "comcontrole"),     # control chars removed
    ("linha\nquebrada", "linhaquebrada"),
    ("", ""),
    ("=+-@", ""),
])
def test_sanitize_label(raw, expected):
    assert sanitize_label(raw) == expected


def test_sanitize_label_truncates():
    assert len(sanitize_label("a" * 500)) == MAX_LABEL_LENGTH


def test_append_creates_file_with_header_and_row(history_file):
    result = CountResult("photo.jpg", 10, 9,
                         Counter({"adult_M": 5, "adult_F": 4}))
    append_to_history(result, "Sunday")

    with open(history_file, newline="", encoding="utf-8") as csv_file:
        rows = list(csv.reader(csv_file))

    assert len(rows) == 2
    header, row = rows
    assert header[:4] == ["timestamp", "event", "total_people",
                          "analyzed_individuals"]
    assert header[-1] == "source"
    assert len(header) == 13  # 4 fixed + 4 age groups x 2 genders + source
    assert row[1] == "Sunday"
    assert row[2] == "10"
    assert row[3] == "9"
    assert row[header.index("adult_M")] == "5"
    assert row[header.index("adult_F")] == "4"
    assert row[header.index("child_M")] == "0"
    assert row[-1] == "photo.jpg"


def test_append_twice_keeps_single_header(history_file):
    result = CountResult("a.jpg", 1, 1, Counter({"teen_F": 1}))
    append_to_history(result, "One")
    append_to_history(result, "Two")

    with open(history_file, newline="", encoding="utf-8") as csv_file:
        rows = list(csv.reader(csv_file))

    assert len(rows) == 3
    assert rows[1][1] == "One"
    assert rows[2][1] == "Two"


def test_append_sanitizes_label(history_file):
    result = CountResult("a.jpg", 1, 1, Counter())
    append_to_history(result, "=cmd|'/c calc'")

    with open(history_file, newline="", encoding="utf-8") as csv_file:
        rows = list(csv.reader(csv_file))

    assert not rows[1][1].startswith("=")


def test_history_file_is_owner_only(history_file):
    result = CountResult("a.jpg", 1, 1, Counter())
    append_to_history(result, "Perm")
    assert os.stat(history_file).st_mode & 0o777 == 0o600
