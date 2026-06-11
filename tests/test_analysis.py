"""Tests for analysis.py: pure helpers, checksum integrity and PeopleCounter
with fake MiVOLO models (no real weights are loaded)."""

import sys
from collections import Counter
from types import ModuleType, SimpleNamespace

import cv2
import numpy as np
import pytest

import analysis
from analysis import (
    PeopleCounter,
    VideoStats,
    classify_age_group,
    normalize_gender,
    pick_device,
    probe_video_stats,
    sha256_of,
    verify_checksum,
)
from conftest import write_test_video

# ------------------------------ pure helpers ------------------------------

@pytest.mark.parametrize("age, expected", [
    (0, "child"),
    (12, "child"),
    (12.5, "teen"),
    (17, "teen"),
    (17.5, "adult"),
    (59, "adult"),
    (59.1, "senior"),
    (90, "senior"),
])
def test_classify_age_group(age, expected):
    assert classify_age_group(age) == expected


@pytest.mark.parametrize("label, expected", [
    ("male", "M"),
    ("female", "F"),
    ("anything-else", "F"),
])
def test_normalize_gender(label, expected):
    assert normalize_gender(label) == expected


def test_video_stats_duration():
    assert VideoStats(frame_count=343, fps=25.0).duration_seconds == 13.72
    assert VideoStats(frame_count=100, fps=0.0).duration_seconds == 0.0


@pytest.mark.parametrize("cuda, mps, expected", [
    (True, True, "cuda"),
    (True, False, "cuda"),
    (False, True, "mps"),
    (False, False, "cpu"),
])
def test_pick_device(monkeypatch, cuda, mps, expected):
    monkeypatch.setattr(analysis.torch.cuda, "is_available", lambda: cuda)
    monkeypatch.setattr(analysis.torch.backends.mps, "is_available", lambda: mps)
    assert pick_device() == expected


def test_allow_full_checkpoint_loading(monkeypatch):
    recorded = {}

    def fake_load(*args, **kwargs):
        recorded.update(kwargs)
        return "checkpoint"

    monkeypatch.setattr(analysis.torch, "load", fake_load)
    analysis.allow_full_checkpoint_loading()

    assert analysis.torch.load("weights.pt") == "checkpoint"
    assert recorded["weights_only"] is False

    recorded.clear()
    analysis.torch.load("weights.pt", weights_only=True)
    assert recorded["weights_only"] is True  # explicit choice is preserved


# ------------------------------ checksums ------------------------------

def test_sha256_of_known_content(tmp_path):
    path = tmp_path / "file.bin"
    path.write_bytes(b"abc")
    expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert sha256_of(path) == expected


def test_verify_checksum_accepts_matching_file(tmp_path):
    path = tmp_path / "file.bin"
    path.write_bytes(b"abc")
    verify_checksum(path, sha256_of(path))
    assert path.exists()


def test_verify_checksum_deletes_tampered_file(tmp_path):
    path = tmp_path / "file.bin"
    path.write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="Invalid SHA256"):
        verify_checksum(path, "0" * 64)
    assert not path.exists()


@pytest.fixture
def weights_env(tmp_path, monkeypatch):
    detector = tmp_path / "detector.pt"
    checkpoint = tmp_path / "mivolo.pth.tar"
    contents = {detector.name: b"detector-bytes", checkpoint.name: b"ckpt-bytes"}

    def fake_download(id=None, output=None, quiet=False):
        from pathlib import Path
        Path(output).write_bytes(contents[Path(output).name])

    monkeypatch.setattr(analysis, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(analysis, "DETECTOR_WEIGHTS", detector)
    monkeypatch.setattr(analysis, "MIVOLO_CHECKPOINT", checkpoint)
    monkeypatch.setattr(analysis.gdown, "download", fake_download)

    import hashlib
    monkeypatch.setattr(analysis, "DETECTOR_SHA256",
                        hashlib.sha256(b"detector-bytes").hexdigest())
    monkeypatch.setattr(analysis, "CHECKPOINT_SHA256",
                        hashlib.sha256(b"ckpt-bytes").hexdigest())
    return SimpleNamespace(detector=detector, checkpoint=checkpoint)


def test_download_weights_when_missing(weights_env):
    analysis.download_weights_if_missing()
    assert weights_env.detector.exists()
    assert weights_env.checkpoint.exists()


def test_download_skipped_when_present(weights_env, monkeypatch):
    analysis.download_weights_if_missing()

    def must_not_download(**kwargs):
        raise AssertionError("download should not happen")

    monkeypatch.setattr(analysis.gdown, "download", must_not_download)
    analysis.download_weights_if_missing()  # verifies checksums only


def test_download_rejects_tampered_existing_file(weights_env):
    weights_env.detector.write_bytes(b"evil")
    weights_env.checkpoint.write_bytes(b"ckpt-bytes")
    with pytest.raises(RuntimeError, match="Invalid SHA256"):
        analysis.download_weights_if_missing()
    assert not weights_env.detector.exists()


# ------------------------------ video probing ------------------------------

def test_probe_video_stats(tmp_path):
    video = write_test_video(tmp_path / "clip.avi", frame_count=5, fps=10.0)
    stats = probe_video_stats(str(video))
    assert stats.frame_count == 5
    assert stats.fps == 10.0
    assert stats.duration_seconds == 0.5


def test_probe_video_stats_invalid_path(tmp_path):
    with pytest.raises(ValueError, match="Could not open video"):
        probe_video_stats(str(tmp_path / "missing.mp4"))


# ------------------------------ PeopleCounter ------------------------------

class FakeMiVOLO:
    def __init__(self, checkpoint, device, half=False, use_persons=True,
                 disable_faces=False, verbose=False):
        self.init_kwargs = dict(checkpoint=checkpoint, device=device, half=half,
                                use_persons=use_persons,
                                disable_faces=disable_faces)

    def predict(self, frame, detected):
        pass


class FakeDetector:
    def __init__(self, weights, device, half=False, verbose=False):
        self.init_kwargs = dict(weights=weights, device=device, half=half)


@pytest.fixture
def fake_counter(monkeypatch):
    monkeypatch.setattr(analysis, "download_weights_if_missing", lambda: None)
    monkeypatch.setattr(analysis, "allow_full_checkpoint_loading", lambda: None)
    monkeypatch.setattr(analysis, "pick_device", lambda: "cpu")

    mivolo_module = ModuleType("mivolo.model.mi_volo")
    mivolo_module.MiVOLO = FakeMiVOLO
    detector_module = ModuleType("mivolo.model.yolo_detector")
    detector_module.Detector = FakeDetector
    monkeypatch.setitem(sys.modules, "mivolo.model.mi_volo", mivolo_module)
    monkeypatch.setitem(sys.modules, "mivolo.model.yolo_detector", detector_module)

    return PeopleCounter()


def test_counter_init_cpu(fake_counter):
    assert fake_counter.device == "cpu"
    assert fake_counter.use_half_precision is False
    assert isinstance(fake_counter.detector, FakeDetector)
    assert fake_counter.detector.init_kwargs["half"] is False
    assert fake_counter.age_gender_model.init_kwargs["use_persons"] is True


def test_counter_uses_half_precision_on_cuda(fake_counter, monkeypatch):
    monkeypatch.setattr(analysis, "pick_device", lambda: "cuda")
    counter = PeopleCounter()
    assert counter.use_half_precision is True
    assert counter.detector.init_kwargs["half"] is True


def _fake_photo_detected():
    return SimpleNamespace(
        n_persons=3,
        n_faces=3,
        ages=[25, None, 8],
        genders=["male", "female", "female"],
        get_bboxes_inds=lambda category: [0, 1, 2],
        plot=lambda: np.ones((32, 32, 3), dtype=np.uint8),
    )


def test_analyze_photo(fake_counter, tmp_path):
    image_path = tmp_path / "scene.png"
    cv2.imwrite(str(image_path), np.zeros((32, 32, 3), dtype=np.uint8))

    detected = _fake_photo_detected()
    fake_counter.detector = SimpleNamespace(predict=lambda image: detected)
    fake_counter.age_gender_model = SimpleNamespace(predict=lambda img, det: None)

    result, annotated = fake_counter.analyze(str(image_path))

    assert result.source_name == "scene.png"
    assert result.total_people == 3
    assert result.analyzed_individuals == 2  # the None age is skipped
    assert result.demographics == Counter({"adult_M": 1, "child_F": 1})
    assert annotated.shape == (32, 32, 3)


def test_analyze_unreadable_image(fake_counter, tmp_path):
    with pytest.raises(ValueError, match="Could not read image"):
        fake_counter.analyze(str(tmp_path / "missing.png"))


def test_summarize_face_demographics_skips_missing_data():
    detected = _fake_photo_detected()
    analyzed, demographics = PeopleCounter._summarize_face_demographics(detected)
    assert analyzed == 2
    assert demographics == Counter({"adult_M": 1, "child_F": 1})


def test_drop_noise_tracks():
    tracks = {1: ["a"] * 3, 2: ["b"] * 2, 3: ["c"] * 5}
    kept = PeopleCounter._drop_noise_tracks(tracks)
    assert set(kept) == {1, 3}


def test_summarize_track_demographics_median_and_majority():
    tracks = {
        1: [(20, "male"), (70, "male"), (30, "female")],   # median 30, male
        2: [(8, "female"), (9, "female"), (70, "female")],  # median 9, female
    }
    demographics = PeopleCounter._summarize_track_demographics(tracks)
    assert demographics == Counter({"adult_M": 1, "child_F": 1})


def test_analyze_video_counts_unique_people(fake_counter, tmp_path):
    video_path = write_test_video(tmp_path / "clip.avi", frame_count=5)

    frame_index = {"value": 0}

    def track(frame):
        index = frame_index["value"]
        frame_index["value"] += 1
        persons = {1: (30.0, "male")}
        faces = {1: (29.0, "male")} if index < 4 else {}
        if index < 2:
            persons[2] = (40.0, "female")   # noise: only 2 samples
        if index == 0:
            persons[3] = (None, "male")     # incomplete sample: ignored
        return SimpleNamespace(get_results_for_tracking=lambda: (persons, faces))

    fake_counter._create_detector = lambda: SimpleNamespace(track=track)
    fake_counter.age_gender_model = SimpleNamespace(predict=lambda f, d: None)

    result = fake_counter.analyze_video(str(video_path))

    assert result.source_name == "clip.avi"
    assert result.total_people == 1          # noise track dropped
    assert result.analyzed_individuals == 1
    assert result.demographics == Counter({"adult_M": 1})


def test_analyze_video_invalid_path(fake_counter, tmp_path):
    fake_counter._create_detector = lambda: SimpleNamespace(track=lambda f: None)
    with pytest.raises(ValueError, match="Could not open video"):
        fake_counter.analyze_video(str(tmp_path / "missing.avi"))
