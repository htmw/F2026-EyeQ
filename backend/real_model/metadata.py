"""Model identity and provenance for SCRUM-107."""

import csv

from .calibration import (
    PROJECT_ROOT,
    CONDITIONS,
    load_frozen_settings,
)

# Proposed real-model version ID, subject to Anel's review.
MODEL_VERSION = "shared-resnet50-seed42-task12-v1"

TRAINING_RESULTS_PATH = (
    PROJECT_ROOT / "results/task11/shared_results.csv"
)

EXPECTED_TRAINING_COMMIT = (
    "3836f00f11d9ce1189c349a39591eaa0753795de"
)


def load_model_metadata():
    """Validate and return the approved model's recorded provenance."""
    deployment, settings = load_frozen_settings()

    with TRAINING_RESULTS_PATH.open(
        newline="", encoding="utf-8"
    ) as file:
        rows = list(csv.DictReader(file))

    matches = [
        row for row in rows
        if row["model_type"] == "shared_two_head"
        and row["seed"] == "42"
        and row["checkpoint"] == deployment["checkpoint"]
    ]

    if len(matches) != 1:
        raise ValueError("Expected exactly one seed-42 training record")

    record = matches[0]
    expected_hash = settings["cataract"]["checkpoint_sha256"]

    if record["checkpoint_sha256"] != expected_hash:
        raise ValueError("Training and calibration hashes disagree")

    if record["git_commit"] != EXPECTED_TRAINING_COMMIT:
        raise ValueError("Unexpected recorded training commit")

    return {
        "version_id": MODEL_VERSION,
        "model_type": record["model_type"],
        "seed": int(record["seed"]),
        "checkpoint": record["checkpoint"],
        "checkpoint_sha256": record["checkpoint_sha256"],
        "training_commit": record["git_commit"],
        "training_script_sha256": record["script_sha256"],
        "labels_sha256": record["labels_sha256"],
        "thresholds": {
            condition: settings[condition]["threshold"]
            for condition in CONDITIONS
        },
        "uncertain_margins": {
            condition: settings[condition]["uncertain_margin"]
            for condition in CONDITIONS
        },
        "calibration_method": "platt",
        "is_mock": False,
    }
