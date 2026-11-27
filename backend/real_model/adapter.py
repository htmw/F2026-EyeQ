"""Isolated shared ResNet-50 inference adapter for SCRUM-107."""

import math
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

from .calibration import (
    PROJECT_ROOT,
    calibrate_logit,
    classify_probability,
    load_frozen_settings,
    verify_checkpoint,
)

SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# The approved dual_model.py imports resnet_backbone as a top-level module.
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from dual_model import DualNet
from fundus_dataset import get_validation_transform


class RealModelAdapter:
    """Load and run the approved shared seed-42 model."""

    def __init__(self):
        deployment, settings = load_frozen_settings()

        checkpoint_path = PROJECT_ROOT / deployment["checkpoint"]
        expected_hash = settings["cataract"]["checkpoint_sha256"]

        verify_checkpoint(checkpoint_path, expected_hash)

        checkpoint = torch.load(
            checkpoint_path,
            map_location="cpu",
            weights_only=True,
        )

        if (
            checkpoint.get("model_type") != "shared_two_head"
            or checkpoint.get("seed") != 42
        ):
            raise ValueError("Unexpected shared-model checkpoint identity")

        model = DualNet(pretrained=False)
        model.load_state_dict(
            checkpoint["model_state_dict"],
            strict=True,
        )

        self.model = model.eval()
        self.transform = get_validation_transform()
        self.settings = settings
        self.checkpoint_path = checkpoint_path

    def prepare_image(self, image):
        """Convert a preprocessed 512x512 BGR image to model input."""
        if not isinstance(image, np.ndarray):
            raise TypeError("Expected a NumPy BGR image")

        if image.shape != (512, 512, 3):
            raise ValueError("Expected a 512x512 three-channel BGR image")

        if image.dtype != np.uint8:
            raise ValueError("Expected uint8 image data")

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb)

        return self.transform(pil_image).unsqueeze(0)

    def predict_logits(self, image):
        """Return uncalibrated logits for both conditions."""
        batch = self.prepare_image(image)

        with torch.inference_mode():
            cataract, glaucoma = self.model(batch)

        logits = {
            "cataract": float(cataract.item()),
            "glaucoma": float(glaucoma.item()),
        }

        if not all(math.isfinite(value) for value in logits.values()):
            raise ValueError("Non-finite model output")

        return logits

    def predict(self, image):
        """Return full-precision calibrated scores and decisions."""
        logits = self.predict_logits(image)
        results = {}

        for condition, raw_logit in logits.items():
            settings = self.settings[condition]
            probability = calibrate_logit(raw_logit, settings)

            results[condition] = {
                "raw_logit": raw_logit,
                "probability": probability,
                "classification": classify_probability(
                    probability,
                    settings,
                ),
                "threshold": settings["threshold"],
                "uncertain_margin": settings["uncertain_margin"],
            }

        return results
