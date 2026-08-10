"""V-JEPA 2 vision encoder wrapper.

Extracts a sequence of visual tokens from a window of frames.
Falls back to a deterministic synthetic encoder when `use_stubs=True`
so the rest of the pipeline (especially selective decoding) can be
developed before the heavy model is installed.
"""
from __future__ import annotations
import numpy as np

try:
    import torch
    _HAS_TORCH = True
except Exception:  # torch not installed yet
    _HAS_TORCH = False


class VisionEncoder:
    def __init__(self, cfg):
        self.cfg = cfg
        self.use_stubs = cfg["project"]["use_stubs"]
        self.vis_dim = cfg["predictor"]["vis_dim"]
        self.n_tokens = 256  # nominal token count for the stub
        self._model = None
        self._proc = None
        if not self.use_stubs:
            self._load_real()

    def _load_real(self):
        from transformers import AutoVideoProcessor, AutoModel
        vc = self.cfg["encoders"]["vision"]
        dtype = getattr(torch, vc["dtype"])
        self._model = AutoModel.from_pretrained(
            vc["hf_id"], dtype=dtype, device_map=self.cfg["project"]["device"],
            attn_implementation="sdpa",
        ).eval()
        self._proc = AutoVideoProcessor.from_pretrained(vc["hf_id"])

    def encode_window(self, frames) -> np.ndarray:
        """frames: list of HxWx3 uint8 RGB arrays.
        Returns visual tokens as a numpy array of shape (n_tokens, vis_dim)."""
        if self.use_stubs:
            return self._stub_tokens(frames)
        import torch
        with torch.no_grad():
            inputs = self._proc(frames, return_tensors="pt").to(
                self._model.device, dtype=self._model.dtype
            )
            feats = self._model.get_vision_features(inputs["pixel_values_videos"])
            return feats[0].float().cpu().numpy()  # (n_tokens, vis_dim)

    # ---- stub: deterministic "embedding" that depends on coarse frame content ----
    def _stub_tokens(self, frames) -> np.ndarray:
        # Summarize the window by a few cheap statistics so that visually
        # different windows give different tokens (lets selective decoding be tested).
        arr = np.stack([np.asarray(f, dtype=np.float32) for f in frames])  # (T,H,W,3)
        feat = np.array([
            arr.mean(), arr.std(),
            arr[..., 0].mean(), arr[..., 1].mean(), arr[..., 2].mean(),
            np.abs(np.diff(arr, axis=0)).mean() if len(arr) > 1 else 0.0,
        ], dtype=np.float32)
        rng = np.random.default_rng(int(abs(feat.sum() * 1000)) % (2**32))
        base = rng.standard_normal((self.n_tokens, self.vis_dim)).astype(np.float32)
        # inject the content signal into the tokens
        base[:, : feat.size] += feat[None, :]
        return base
