"""Evaluate a predictor checkpoint on a cached val set.

Reports direction quality (cos to target), collapse (pred-pred cos), and
optionally decodes example captions via SONAR for a qualitative before/after.

Usage:
    python scripts/eval_predictor.py --ckpt checkpoints/predictor_1000.pt \
           --val data_cache_coin2_val --decode
"""
import argparse, glob, os, sys
import numpy as np, yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import torch
from livejepa.predictor.model import Predictor
from livejepa.predictor.infer import rescale_to_native, native_norm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--val", default="data_cache_coin2_val")
    ap.add_argument("--decode", action="store_true", help="decode example captions via SONAR")
    ap.add_argument("--n-decode", type=int, default=10)
    args = ap.parse_args()

    cfg = yaml.safe_load(open("configs/default.yaml"))
    pc = cfg["predictor"]
    m = Predictor(pc["vis_dim"], pc["hidden_dim"], pc["out_dim"],
                  pc["depth"], pc["heads"], pc["dropout"])
    m.load_state_dict(torch.load(args.ckpt, map_location="cpu"))
    m.eval()

    files = sorted(f for d in args.val.split(",") if d
                   for f in glob.glob(os.path.join(d, "*.npz")))
    preds, tgts, caps = [], [], []
    for f in files:
        d = np.load(f)
        with torch.no_grad():
            p = m(torch.from_numpy(d["tokens"].astype(np.float32)[None]))[0].numpy()
        preds.append(p)
        tgts.append(d["target"].astype(np.float32))
        caps.append(open(f[:-4] + ".txt", encoding="utf-8").read().strip())
    preds, tgts = np.stack(preds), np.stack(tgts)

    def unit(x):
        return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-8)
    cos = (unit(preds) * unit(tgts)).sum(-1)
    pu = unit(preds)
    offdiag = (pu @ pu.T)[~np.eye(len(pu), dtype=bool)]
    pp = float(offdiag.mean()) if offdiag.size else float("nan")  # undefined for a single val sample
    print(f"ckpt: {args.ckpt}  |  val: {args.val} ({len(files)} samples)")
    print(f"  mean cos(pred,target): {cos.mean():.3f}   (higher = better direction)")
    print(f"  pred-pred cos:         {pp:.3f}   (lower = more diverse; ~1 = collapsed)")

    if args.decode:
        cfg["project"]["use_stubs"] = False
        cfg["encoders"]["sonar"]["backend"] = "transformers"
        from livejepa.encoders.sonar import SonarSpace
        sonar = SonarSpace(cfg)
        seen, idx = set(), []
        for i, c in enumerate(caps):
            if c not in seen:
                seen.add(c); idx.append(i)
            if len(idx) >= args.n_decode:
                break
        dec = sonar.decode(rescale_to_native(preds[idx], native_norm(cfg)))
        print("  example predictions (GT -> predicted):")
        for i, txt in zip(idx, dec):
            print(f"    '{caps[i]}'  ->  '{txt}'")


if __name__ == "__main__":
    main()
