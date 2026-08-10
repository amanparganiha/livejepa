"""Predictor inference helpers.

The predictor is trained with scale-invariant losses (InfoNCE + cosine), so it
learns embedding *direction* but not magnitude. SONAR sentence embeddings live
at L2 norm ~0.2; the SONAR decoder rejects off-scale vectors and emits empty
strings. We therefore L2-normalize each prediction and rescale it to the
empirical native norm before handing it to the selective decoder / SONAR.

`load_predictor` returns a single callable that maps a window of frozen
V-JEPA 2 visual tokens to a native-scale SONAR embedding, used identically by
the live demo and the offline Pareto evaluation.
"""
from __future__ import annotations
import numpy as np

# Empirical mean L2 norm of SONAR caption embeddings (measured from the feature
# cache: data_cache_val targets had mean norm 0.196, range 0.165-0.239).
DEFAULT_NATIVE_NORM = 0.196


def native_norm(cfg) -> float:
    """Native SONAR embedding norm to rescale predictions to (config override)."""
    return float(cfg["encoders"]["sonar"].get("native_norm", DEFAULT_NATIVE_NORM))


def rescale_to_native(emb, norm: float = DEFAULT_NATIVE_NORM) -> np.ndarray:
    """Rescale each row to L2 norm `norm`, preserving direction. Accepts (d,) or (T, d).

    Non-finite or ~zero-norm rows are zeroed rather than amplified — a dead/NaN
    prediction would otherwise be blown up to full native norm and decode into a
    confident-looking but meaningless caption."""
    emb = np.asarray(emb, dtype=np.float32)
    emb = np.where(np.isfinite(emb), emb, 0.0)
    n = np.linalg.norm(emb, axis=-1, keepdims=True)
    out = emb / (n + 1e-8) * norm
    return np.where(n < 1e-6, 0.0, out)


def load_predictor(cfg, ckpt=None):
    """Return ``predict(tokens) -> native-scale SONAR embedding``.

    tokens: (N, vis_dim) float array of V-JEPA 2 visual tokens for one window.
    returns: (out_dim,) predicted SONAR embedding at native scale.

    With a checkpoint, uses the trained Predictor; otherwise falls back to a
    deterministic random projector so the pipeline still runs end-to-end in dev.
    """
    nn_norm = native_norm(cfg)
    pc = cfg["predictor"]

    if ckpt:
        import torch
        from livejepa.predictor.model import Predictor
        dev = cfg["project"]["device"] if torch.cuda.is_available() else "cpu"
        m = Predictor(pc["vis_dim"], pc["hidden_dim"], pc["out_dim"],
                      pc["depth"], pc["heads"], pc["dropout"]).to(dev)
        m.load_state_dict(torch.load(ckpt, map_location=dev))
        m.eval()

        def predict(tokens):
            with torch.no_grad():
                t = torch.from_numpy(np.asarray(tokens, dtype=np.float32)[None]).to(dev)
                out = m(t)[0].float().cpu().numpy()
            return rescale_to_native(out, nn_norm)
        return predict

    # fallback: deterministic random linear projector (dev / stub use)
    rng = np.random.default_rng(0)
    W = rng.standard_normal((pc["vis_dim"], pc["out_dim"])).astype(np.float32)

    def predict(tokens):
        v = np.asarray(tokens, dtype=np.float32).mean(0) @ W
        return rescale_to_native(v, nn_norm)
    return predict
