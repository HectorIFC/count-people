"""Domain logic: people counting and demographics estimation with MiVOLO.

Runs on CUDA (VPS with GPU), Apple Silicon (MPS) or plain CPU (cheap VPS).
Device selection and FP16 usage are handled automatically.
Supports photos (single frame) and videos (multi-frame with tracking).
"""

import os

# Must be set BEFORE importing torch: lets unsupported MPS ops fall back to CPU.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import hashlib
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2
import gdown
import numpy as np
import torch

# --- Model weights (downloaded once, cached on disk) ---
MODELS_DIR = Path(os.environ.get("MODELS_DIR", "models"))
DETECTOR_WEIGHTS = MODELS_DIR / "yolov8x_person_face.pt"
MIVOLO_CHECKPOINT = MODELS_DIR / "mivolo_imdb.pth.tar"
DETECTOR_GDRIVE_ID = "1CGNCkZQNj5WkP3rLpENWAOgrBQkUWRdw"
CHECKPOINT_GDRIVE_ID = "11i8pKctxz3wVkDBlWKvhYIh7kpVFXSZ4"

# Integrity pins: the checkpoints are loaded with weights_only=False (pickle),
# so a tampered file could execute arbitrary code. Refuse anything that does
# not match the official MiVOLO release files.
DETECTOR_SHA256 = "2620f45609a65f909eb876bd7401308b5a8f3843ad5a03cb7416066a3e492989"
CHECKPOINT_SHA256 = "cc279b6914b3ee8be6a58139c06ecb24ca95751233cf6c07804b93184614eb17"

# --- Age classification rules ---
CHILD_MAX_AGE = 12
TEEN_MAX_AGE = 17
ADULT_MAX_AGE = 59

AGE_GROUPS = ("child", "teen", "adult", "senior")
GENDERS = ("M", "F")

# Video tracks shorter than this are likely tracker noise (ID switches,
# false positives) and would inflate the unique-people count.
MIN_TRACK_SAMPLES = 3


@dataclass(frozen=True)
class CountResult:
    source_name: str
    total_people: int
    analyzed_individuals: int
    demographics: Counter


@dataclass(frozen=True)
class VideoStats:
    frame_count: int
    fps: float

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.fps if self.fps else 0.0


def pick_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(path: Path, expected_sha256: str) -> None:
    actual = sha256_of(path)
    if actual != expected_sha256:
        path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Invalid SHA256 checksum for {path.name} "
            f"(expected {expected_sha256}, got {actual}). "
            "The file was deleted; run again to re-download it."
        )


def download_weights_if_missing() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if not DETECTOR_WEIGHTS.exists():
        gdown.download(id=DETECTOR_GDRIVE_ID, output=str(DETECTOR_WEIGHTS), quiet=False)
    if not MIVOLO_CHECKPOINT.exists():
        gdown.download(id=CHECKPOINT_GDRIVE_ID, output=str(MIVOLO_CHECKPOINT), quiet=False)
    # Verified on every startup, not only after download: catches on-disk tampering too.
    verify_checksum(DETECTOR_WEIGHTS, DETECTOR_SHA256)
    verify_checksum(MIVOLO_CHECKPOINT, CHECKPOINT_SHA256)


def allow_full_checkpoint_loading() -> None:
    """PyTorch >= 2.6 defaults torch.load to weights_only=True, which rejects
    MiVOLO/ultralytics checkpoints (pickled with model classes). Restoring the
    old behavior is safe here: weights come from the official MiVOLO release.
    """
    original_torch_load = torch.load

    def torch_load_trusted(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return original_torch_load(*args, **kwargs)

    torch.load = torch_load_trusted


def classify_age_group(age: float) -> str:
    if age <= CHILD_MAX_AGE:
        return "child"
    if age <= TEEN_MAX_AGE:
        return "teen"
    if age <= ADULT_MAX_AGE:
        return "adult"
    return "senior"


def normalize_gender(gender_label: str) -> str:
    return "M" if gender_label == "male" else "F"


def probe_video_stats(video_path: str) -> VideoStats:
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    stats = VideoStats(
        frame_count=int(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
        fps=capture.get(cv2.CAP_PROP_FPS),
    )
    capture.release()
    return stats


class PeopleCounter:
    """Loads MiVOLO once and analyzes photos and videos.

    Instantiates Detector and MiVOLO directly (instead of mivolo.Predictor)
    to control FP16: half precision is only reliable on CUDA.
    """

    def __init__(self) -> None:
        from mivolo.model.mi_volo import MiVOLO

        download_weights_if_missing()
        allow_full_checkpoint_loading()

        self.device = pick_device()
        self.use_half_precision = self.device == "cuda"
        self.detector = self._create_detector()
        self.age_gender_model = MiVOLO(
            str(MIVOLO_CHECKPOINT),
            self.device,
            half=self.use_half_precision,
            use_persons=True,
            disable_faces=False,
            verbose=False,
        )

    def _create_detector(self):
        from mivolo.model.yolo_detector import Detector

        return Detector(
            str(DETECTOR_WEIGHTS),
            self.device,
            half=self.use_half_precision,
            verbose=False,
        )

    # ------------------------------ photos ------------------------------

    def analyze(self, image_path: str) -> tuple[CountResult, np.ndarray]:
        """Returns the aggregated result and the annotated image (BGR)."""
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not read image: {image_path}")

        detected = self.detector.predict(image)
        self.age_gender_model.predict(image, detected)
        annotated_image = detected.plot()

        analyzed, demographics = self._summarize_face_demographics(detected)
        result = CountResult(
            source_name=Path(image_path).name,
            total_people=max(detected.n_persons, detected.n_faces),
            analyzed_individuals=analyzed,
            demographics=demographics,
        )
        return result, annotated_image

    @staticmethod
    def _summarize_face_demographics(detected) -> tuple[int, Counter]:
        demographics: Counter = Counter()
        analyzed = 0
        for index in detected.get_bboxes_inds("face"):
            age, gender = detected.ages[index], detected.genders[index]
            if age is None or gender is None:
                continue
            analyzed += 1
            demographics[f"{classify_age_group(age)}_{normalize_gender(gender)}"] += 1
        return analyzed, demographics

    # ------------------------------ videos ------------------------------

    def analyze_video(self, video_path: str) -> CountResult:
        """Counts UNIQUE people across frames using tracking.

        A fresh detector is created per video because the YOLO tracker keeps
        state between track() calls (persist=True); reusing it would leak
        track ids from one video into the next.
        """
        person_tracks, face_tracks = self._collect_video_tracks(video_path)
        person_tracks = self._drop_noise_tracks(person_tracks)
        face_tracks = self._drop_noise_tracks(face_tracks)

        richer_tracks = (
            face_tracks if len(face_tracks) >= len(person_tracks) else person_tracks
        )
        return CountResult(
            source_name=Path(video_path).name,
            total_people=max(len(person_tracks), len(face_tracks)),
            analyzed_individuals=len(richer_tracks),
            demographics=self._summarize_track_demographics(richer_tracks),
        )

    def _collect_video_tracks(self, video_path: str) -> tuple[dict, dict]:
        """Tracks persons and faces SEPARATELY across frames.

        MiVOLO assigns independent track ids to bodies and faces, so merging
        them in a single dict would count each visible person twice.
        """
        video_detector = self._create_detector()
        person_tracks: dict[int, list] = defaultdict(list)
        face_tracks: dict[int, list] = defaultdict(list)

        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        while True:
            ok, frame = capture.read()
            if not ok:
                break
            detected = video_detector.track(frame)
            self.age_gender_model.predict(frame, detected)
            persons, faces = detected.get_results_for_tracking()
            for track_id, sample in persons.items():
                if None not in sample:
                    person_tracks[track_id].append(sample)
            for track_id, sample in faces.items():
                if None not in sample:
                    face_tracks[track_id].append(sample)
        capture.release()
        return person_tracks, face_tracks

    @staticmethod
    def _drop_noise_tracks(tracks: dict) -> dict:
        return {track_id: samples for track_id, samples in tracks.items()
                if len(samples) >= MIN_TRACK_SAMPLES}

    @staticmethod
    def _summarize_track_demographics(tracks: dict) -> Counter:
        """One person per track: median age, majority-vote gender."""
        demographics: Counter = Counter()
        for samples in tracks.values():
            median_age = statistics.median(age for age, _ in samples)
            genders = [gender for _, gender in samples]
            majority_gender = max(set(genders), key=genders.count)
            demographics[
                f"{classify_age_group(median_age)}_{normalize_gender(majority_gender)}"
            ] += 1
        return demographics
