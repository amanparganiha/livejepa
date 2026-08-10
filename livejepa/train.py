"""Train the predictor on cached (V-JEPA 2 tokens -> SONAR target) pairs.

Usage:
    python -m livejepa.train --config configs/default.yaml

Requires a populated feature cache (see livejepa/data/cache.py). The encoders
are NOT in the loop here — training is a cheap regression over cached tensors.
"""
from __future__ import annotations
import argparse
import os
import yaml
import numpy as np


def collate(batch, max_tokens=256):
    """Pad (or evenly subsample) token sequences to a common length.
    Subsampling beats truncation: it keeps the whole clip in view."""
    import torch
    toks, tgts = zip(*batch)
    d = toks[0].shape[-1]
    out = np.zeros((len(toks), max_tokens, d), dtype=np.float32)
    mask = np.zeros((len(toks), max_tokens), dtype=bool)
    for i, t in enumerate(toks):
        if len(t) > max_tokens:
            t = t[np.linspace(0, len(t) - 1, max_tokens).astype(int)]
        out[i, : len(t)] = t
        mask[i, : len(t)] = True
    return (torch.from_numpy(out), torch.from_numpy(mask),
            torch.from_numpy(np.stack(tgts)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--max-steps", type=int, default=None, help="override train.max_steps")
    ap.add_argument("--batch-size", type=int, default=None, help="override train.batch_size")
    ap.add_argument("--data-root", default=None, help="override train.data_root (feature cache dir)")
    ap.add_argument("--ckpt-dir", default=None, help="override train.ckpt_dir")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    if args.max_steps is not None:
        cfg["train"]["max_steps"] = args.max_steps
    if args.batch_size is not None:
        cfg["train"]["batch_size"] = args.batch_size
    if args.data_root is not None:
        cfg["train"]["data_root"] = args.data_root
    if args.ckpt_dir is not None:
        cfg["train"]["ckpt_dir"] = args.ckpt_dir

    import torch
    from torch.utils.data import DataLoader
    from livejepa.data.cache import CachedDataset
    from livejepa.predictor.model import Predictor
    from livejepa.predictor.losses import predictor_loss

    torch.manual_seed(cfg["project"]["seed"])
    dev = cfg["project"]["device"] if torch.cuda.is_available() else "cpu"

    ds = CachedDataset(cfg["train"]["data_root"])
    if len(ds) == 0:
        raise SystemExit(
            f"No cached features in {cfg['train']['data_root']}. "
            "Build the cache first (see livejepa/data/cache.py)."
        )
    dl = DataLoader(ds, batch_size=cfg["train"]["batch_size"], shuffle=True,
                    collate_fn=collate, drop_last=True)

    pc = cfg["predictor"]
    model = Predictor(pc["vis_dim"], pc["hidden_dim"], pc["out_dim"],
                      pc["depth"], pc["heads"], pc["dropout"]).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["train"]["lr"],
                            weight_decay=cfg["train"]["weight_decay"])

    import math
    warmup, total = cfg["train"]["warmup_steps"], cfg["train"]["max_steps"]

    def lr_lambda(s):
        if s < warmup:
            return (s + 1) / warmup
        p = (s - warmup) / max(1, total - warmup)
        return 0.5 * (1.0 + math.cos(math.pi * p))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda)

    os.makedirs(cfg["train"]["ckpt_dir"], exist_ok=True)
    step = 0
    model.train()
    while step < cfg["train"]["max_steps"]:
        for tokens, mask, target in dl:
            tokens, mask, target = tokens.to(dev), mask.to(dev), target.to(dev)
            pred = model(tokens, vis_mask=mask)  # (B, out_dim)
            loss, logs = predictor_loss(
                pred, target, cfg["train"]["infonce_temp"],
                cfg["train"]["cosine_loss_weight"])
            opt.zero_grad(); loss.backward(); opt.step(); sched.step()
            step += 1
            if step % cfg["train"]["log_every"] == 0:
                print(f"step {step:6d} | " +
                      " ".join(f"{k}={v:.4f}" for k, v in logs.items()))
            if step % cfg["train"]["ckpt_every"] == 0:
                p = os.path.join(cfg["train"]["ckpt_dir"], f"predictor_{step}.pt")
                torch.save(model.state_dict(), p)
                print("saved", p)
            if step >= cfg["train"]["max_steps"]:
                break
    print("done")


if __name__ == "__main__":
    main()
