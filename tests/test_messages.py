"""Tests for messages.py: language resolution and localized texts."""

import string
from collections import Counter

import pytest

from analysis import CountResult
from messages import (
    AGE_GROUP_LABELS,
    DEFAULT_LANGUAGE,
    MESSAGES,
    SUPPORTED_LANGUAGES,
    format_summary,
    message,
    resolve_language,
)


@pytest.mark.parametrize("code, expected", [
    ("pt", "pt"),
    ("pt-br", "pt"),
    ("PT-BR", "pt"),
    ("en", "en"),
    ("en-US", "en"),
    ("es", "es"),
    ("es-419", "es"),
    ("de", "en"),     # unsupported -> fallback
    ("", "en"),
    (None, "en"),
])
def test_resolve_language(code, expected):
    assert resolve_language(code) == expected


def test_default_language_is_supported():
    assert DEFAULT_LANGUAGE in SUPPORTED_LANGUAGES


def test_every_message_has_every_language():
    for key, translations in MESSAGES.items():
        assert set(translations) == set(SUPPORTED_LANGUAGES), key


def test_every_age_group_label_has_every_language():
    for age_group, translations in AGE_GROUP_LABELS.items():
        assert set(translations) == set(SUPPORTED_LANGUAGES), age_group


def _placeholders(template):
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def test_placeholders_are_consistent_across_languages():
    for key, translations in MESSAGES.items():
        expected = _placeholders(translations["en"])
        for lang, template in translations.items():
            assert _placeholders(template) == expected, (key, lang)


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_message_formats_kwargs(lang):
    text = message("video_received", lang, duration=13.7, frames=343)
    assert "14s" in text
    assert "343" in text


def test_message_unknown_key_raises():
    with pytest.raises(KeyError):
        message("does_not_exist", "en")


@pytest.mark.parametrize("lang, title", [
    ("pt", "Resumo - Reuniao"),
    ("en", "Summary - Reuniao"),
    ("es", "Resumen - Reuniao"),
])
def test_format_summary_title_and_totals(lang, title):
    result = CountResult("photo.jpg", 13, 12,
                         Counter({"adult_M": 4, "adult_F": 8}))
    summary = format_summary(result, "Reuniao", lang)
    lines = summary.splitlines()
    assert lines[0] == title
    assert "13" in lines[1]
    assert "12" in lines[2]


def test_format_summary_includes_only_nonzero_groups():
    result = CountResult("photo.jpg", 3, 3,
                         Counter({"child_F": 1, "senior_M": 2}))
    summary = format_summary(result, "Event", "en")
    assert "Children: 0 M, 1 F" in summary
    assert "Seniors: 2 M, 0 F" in summary
    assert "Adults" not in summary
    assert "Teens" not in summary


def test_format_summary_without_demographics_has_no_group_lines():
    result = CountResult("photo.jpg", 5, 0, Counter())
    summary = format_summary(result, "Event", "en")
    assert summary.splitlines() == [
        "Summary - Event",
        "Total people: 5",
        "With estimated demographics: 0",
    ]
