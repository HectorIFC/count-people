"""End-to-end tests with the real MiVOLO models.

Slow and dependent on local files (downloaded weights + sample media), so they
only run when RUN_INTEGRATION=1:

    RUN_INTEGRATION=1 pytest tests/test_integration.py
"""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

run_integration = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1",
    reason="set RUN_INTEGRATION=1 to run the real-model tests",
)


@pytest.fixture(scope="module")
def counter():
    from analysis import PeopleCounter
    return PeopleCounter()


@pytest.mark.integration
@run_integration
def test_real_photo_count(counter):
    photo = ROOT / "people.jpg"
    if not photo.exists():
        pytest.skip("sample photo not available")

    result, annotated = counter.analyze(str(photo))

    assert result.total_people >= 1
    assert result.analyzed_individuals <= result.total_people
    assert sum(result.demographics.values()) == result.analyzed_individuals
    assert annotated.ndim == 3


@pytest.mark.integration
@run_integration
def test_real_video_count(counter):
    video = ROOT / "people.mp4"
    if not video.exists():
        pytest.skip("sample video not available")

    from analysis import probe_video_stats
    stats = probe_video_stats(str(video))
    assert stats.duration_seconds > 0

    result = counter.analyze_video(str(video))
    assert result.total_people >= 1
    assert sum(result.demographics.values()) == result.analyzed_individuals
