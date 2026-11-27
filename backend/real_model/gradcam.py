"""Real Grad-CAM for the approved shared ResNet-50 model."""

import threading

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from matplotlib import colormaps


OVERLAY_ALPHA = 0.40
CONDITIONS = ("cataract", "glaucoma")


class RealGradCAM:
    """Generate condition-specific Grad-CAM with scoped hooks."""

    def __init__(self, model):
        self.model = model
        self.target_layer = model.backbone.features[7][-1]
        self._lock = threading.RLock()

    def generate(self, image_tensor, condition):
        """Return a normalized CAM and the selected raw logit."""
        if condition not in CONDITIONS:
            raise ValueError(f"Unsupported condition: {condition}")

        if not isinstance(image_tensor, torch.Tensor):
            raise TypeError("Expected a PyTorch image tensor")

        if image_tensor.ndim != 4 or image_tensor.shape[0] != 1:
            raise ValueError("Expected a batch containing exactly one image")

        activations = []

        def capture_activations(module, inputs, output):
            activations.append(output)

        # Serializes Grad-CAM calls using this instance.
        # The integration layer must also coordinate other users of the model.
        with self._lock:
            hook = self.target_layer.register_forward_hook(
                capture_activations
            )
            try:
                with torch.inference_mode(False), torch.enable_grad():
                    cataract_logits, glaucoma_logits = self.model(
                        image_tensor
                    )
                    selected = (
                        cataract_logits
                        if condition == "cataract"
                        else glaucoma_logits
                    )
                    raw_logit = selected.reshape(-1)[0]

                    if len(activations) != 1:
                        raise RuntimeError(
                            "Expected one Grad-CAM activation"
                        )

                    gradients = torch.autograd.grad(
                        outputs=raw_logit,
                        inputs=activations[0],
                        retain_graph=False,
                        create_graph=False,
                    )[0]

                    activation = activations[0].detach()
                    gradients = gradients.detach()

                    weights = gradients.mean(
                        dim=(2, 3), keepdim=True
                    )
                    cam = torch.relu(
                        (weights * activation).sum(
                            dim=1, keepdim=True
                        )
                    )

                    cam = F.interpolate(
                        cam,
                        size=image_tensor.shape[-2:],
                        mode="bilinear",
                        align_corners=False,
                    )

                    cam = cam[0, 0].cpu().numpy()
                    raw_value = float(raw_logit.detach().item())
            finally:
                hook.remove()

        if not np.isfinite(raw_value):
            raise ValueError("Non-finite model output")

        maximum = float(cam.max())
        minimum = float(cam.min())

        if maximum > minimum:
            cam = (cam - minimum) / (maximum - minimum)
        else:
            cam = np.zeros_like(cam)

        if not np.isfinite(cam).all():
            raise ValueError("Non-finite Grad-CAM values")

        return cam, raw_value

    def create_overlay(self, image_bgr, cam):
        """Return a 512x512 BGR overlay compatible with OpenCV."""
        if (
            not isinstance(image_bgr, np.ndarray)
            or image_bgr.shape != (512, 512, 3)
            or image_bgr.dtype != np.uint8
        ):
            raise ValueError("Expected a 512x512 uint8 BGR image")

        if not isinstance(cam, np.ndarray) or cam.shape != (512, 512):
            raise ValueError("Expected a 512x512 Grad-CAM")

        if not np.isfinite(cam).all():
            raise ValueError("Non-finite Grad-CAM values")

        original_rgb = cv2.cvtColor(
            image_bgr, cv2.COLOR_BGR2RGB
        ).astype(np.float32) / 255.0

        heatmap_rgb = colormaps["jet"](cam)[..., :3].astype(
            np.float32
        )

        overlay_rgb = (
            (1.0 - OVERLAY_ALPHA) * original_rgb
            + OVERLAY_ALPHA * heatmap_rgb
        )

        overlay_rgb = np.clip(
            overlay_rgb * 255.0, 0, 255
        ).astype(np.uint8)

        return cv2.cvtColor(
            overlay_rgb, cv2.COLOR_RGB2BGR
        )

    def close(self):
        """Compatibility method; hooks are removed after each call."""
        pass
