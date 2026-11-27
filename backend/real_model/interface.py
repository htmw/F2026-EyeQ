"""Isolated real-model screening interface for SCRUM-107."""

import math
import threading

import numpy as np

from .adapter import RealModelAdapter
from .gradcam import CONDITIONS, RealGradCAM
from .metadata import load_model_metadata


class RealScreeningInterface:
    """Coordinate real-model predictions and condition-specific Grad-CAM."""

    def __init__(self):
        self._lock = threading.RLock()
        self.adapter = RealModelAdapter()
        self.metadata = load_model_metadata()
        self.gradcam = RealGradCAM(self.adapter.model)
        self._closed = False

    def _check_open(self):
        if self._closed:
            raise RuntimeError("Real-model interface is closed")

    def predict(self, image_bgr):
        """Return calibrated predictions for both conditions."""
        with self._lock:
            self._check_open()
            return self.adapter.predict(image_bgr)

    def heatmap(self, image_bgr, condition):
        """Return a condition-specific 512x512 BGR Grad-CAM overlay."""
        if condition not in CONDITIONS:
            raise ValueError(f"Unsupported condition: {condition}")

        with self._lock:
            self._check_open()
            tensor = self.adapter.prepare_image(image_bgr)
            cam, raw_logit = self.gradcam.generate(tensor, condition)

            if not math.isfinite(raw_logit):
                raise ValueError("Non-finite Grad-CAM logit")

            return self.gradcam.create_overlay(image_bgr, cam)

    def screen(self, image_bgr):
        """Return both predictions and both heatmaps from one image."""
        with self._lock:
            self._check_open()
            predictions = self.adapter.predict(image_bgr)

            heatmaps = {
                condition: self.heatmap(image_bgr, condition)
                for condition in CONDITIONS
            }

            return {
                "model_version": self.metadata["version_id"],
                "predictions": predictions,
                "heatmaps": heatmaps,
            }

    def close(self):
        """Close the interface and release Grad-CAM resources."""
        with self._lock:
            if not self._closed:
                self.gradcam.close()
                self._closed = True

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
