"""Frozen Task 12 calibration and referral decisions for SCRUM-107."""

import hashlib
import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = PROJECT_ROOT / "results/calibration/frozen_settings.json"
CONDITIONS = ("cataract", "glaucoma")


def load_frozen_settings():
    """Load and validate the approved shared-model deployment settings."""
    with SETTINGS_PATH.open(encoding="utf-8") as file:
        document = json.load(file)

    if document.get("status") != "frozen" and document.get("frozen") is not True:
        raise ValueError("Calibration settings are not frozen")

    deployment = document["deployment"]
    if deployment["model_kind"] != "shared" or deployment["seed"] != 42:
        raise ValueError("Unexpected model deployment")

    checkpoint = deployment["checkpoint"]
    selected = {}

    for row in document["runs"]:
        if row["model_kind"] != "shared" or row["seed"] != 42:
            continue

        disease = row["disease"]
        if disease not in CONDITIONS or disease in selected:
            raise ValueError("Unexpected or duplicate condition")

        if row["method"] != "platt" or row["checkpoint"] != checkpoint:
            raise ValueError("Calibration does not match deployment")

        for field in ("scale", "offset", "threshold", "uncertain_margin"):
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Invalid {field} for {disease}")
            if not math.isfinite(value):
                raise ValueError(f"Non-finite {field} for {disease}")

        if row["scale"] <= 0:
            raise ValueError("Platt scale must be positive")
        if not 0 <= row["threshold"] <= 1:
            raise ValueError("Invalid referral threshold")
        if row["uncertain_margin"] < 0:
            raise ValueError("Invalid uncertainty margin")

        selected[disease] = row

    if set(selected) != set(CONDITIONS):
        raise ValueError("Missing condition-specific calibration")

    hashes = {selected[d]["checkpoint_sha256"] for d in CONDITIONS}
    if len(hashes) != 1:
        raise ValueError("Checkpoint hashes disagree")

    return deployment, selected


def verify_checkpoint(checkpoint_path, expected_sha256):
    """Verify checkpoint integrity before loading model weights."""
    digest = hashlib.sha256()
    with Path(checkpoint_path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    if digest.hexdigest() != expected_sha256:
        raise ValueError("Checkpoint SHA-256 mismatch")


def calibrate_logit(raw_logit, settings):
    """Apply frozen Platt scaling to a raw logit using Python float64."""
    logit = float(raw_logit)
    if not math.isfinite(logit):
        raise ValueError("Non-finite model logit")

    adjusted = settings["scale"] * logit + settings["offset"]

    # Numerically stable sigmoid without premature rounding.
    if adjusted >= 0:
        return 1.0 / (1.0 + math.exp(-adjusted))

    exponent = math.exp(adjusted)
    return exponent / (1.0 + exponent)


def classify_probability(probability, settings):
    """Apply the approved Task 12 uncertainty and referral policy."""
    probability = float(probability)
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Invalid calibrated probability")

    threshold = settings["threshold"]
    margin = settings["uncertain_margin"]

    if abs(probability - threshold) <= margin:
        return "uncertain"
    if probability >= threshold:
        return "refer"
    return "no_concern"


def requires_referral(classification):
    """Uncertain and ordinary refer results both require referral."""
    if classification not in ("uncertain", "refer", "no_concern"):
        raise ValueError("Unknown classification")
    return classification in ("uncertain", "refer")
