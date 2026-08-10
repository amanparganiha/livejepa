"""Decode the pilot predictor's predictions on held-out clips.

The Phase 2 gate asks for *coherent* (not perfect) captions on held-out
video. This loads a checkpoint, predicts SONAR embeddings for every clip
in the validation cache, rescales them to SONAR's native norm (the decoder
rejects off-scale vectors — see memory: training losses are scale-invariant,
so predicted norms are arbitrary), decodes to text, and prints them next to
the ground truth, plus retrieval-style cosine diagnostics.

    python scripts/eval_pilot.py --ckpt checkpoints/predictor_1500.pt
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--val-dir", default="data_cache_val")
    ap.add_argument("--n-decode", type=int, default=12,
                    help="how many predictions to decode to text (slow part)")
    args = ap.parse_args()

    import torch
    from livejepa.data.cache import CachedDataset
    from livejepa.encoders.sonar import SonarSpace
    from livejepa.predictor.model import Predictor
    from livejepa.train import collate

    cfg = yaml.safe_load(open(args.config))
    dev = cfg["project"]["device"] if torch.cuda.is_available() else "cpu"

    pc = cfg["predictor"]
    model = Predictor(pc["vis_dim"], pc["hidden_dim"], pc["out_dim"],
                      pc["depth"], pc["heads"], pc["dropout"]).to(dev).eval()
    model.load_state_dict(torch.load(args.ckpt, map_location=dev))

    ds = CachedDataset(args.val_dir)
    captions = [open(os.path.join(args.val_dir, f"{i}.txt"), encoding="utf-8").read()
                for i in ds.ids]
    print(f"validation clips: {len(ds)}\n")

    preds, tgts = [], []
    with torch.no_grad():
        for i in range(0, len(ds), 16):
            batch = [ds[j] for j in range(i, min(i + 16, len(ds)))]
            tokens, mask, target = collate(batch)
            p = model(tokens.to(dev), vis_mask=mask.to(dev))
            preds.append(p.cpu().numpy())
            tgts.append(target.numpy())
    preds = np.concatenate(preds)
    tgts = np.concatenate(tgts)

    # --- diagnostics in embedding space (cheap, scale-invariant) ---
    pn = preds / (np.linalg.norm(preds, axis=1, keepdims=True) + 1e-8)
    tn = tgts / (np.linalg.norm(tgts, axis=1, keepdims=True) + 1e-8)
    cos = (pn * tn).sum(1)
    sims = pn @ tn.T
    r1 = float((sims.argmax(1) == np.arange(len(ds))).mean())
    print(f"cosine(pred, target): mean {cos.mean():.3f}  min {cos.min():.3f}  "
          f"max {cos.max():.3f}")
    print(f"retrieval R@1 among {len(ds)} val clips: {r1:.2%}\n")

    # --- decode a sample to text at SONAR's native scale ---
    sonar = SonarSpace(cfg)
    scale = float(np.linalg.norm(tgts, axis=1).mean())
    sel = np.linspace(0, len(ds) - 1, min(args.n_decode, len(ds))).astype(int)
    cal = pn[sel] * scale
    texts = sonar.decode(cal)
    for i, t in zip(sel, texts):
        print(f"  GT  : {captions[i]}\n  pred: {t}\n")


if __name__ == "__main__":
    main()
