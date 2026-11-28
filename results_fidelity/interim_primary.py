"""Pre-registered PRIMARY test on a run that is still going: adaptive - uniform,
time-aligned CIDEr, per take, averaged over the 8 budgets (WORKLOG 2026-11-25).

Reads <out>.partial.json, rebuilds the take order and the participant groups
exactly as eval_gt_fidelity.py does (sorted uids, takes.json metadata), and uses
that script's own boot_ci / cluster_boot_ci with the same seeds, so the numbers
equal the final JSON's paired block once the run finishes.

usage: python results_fidelity/interim_primary.py <partial.json> <uids_file> [S1.json]
"""
import json
import os
import sys

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, REPO)
from eval_gt_fidelity import boot_ci, cluster_boot_ci  # noqa: E402

part_path, uids_file = sys.argv[1], sys.argv[2]
s1_path = sys.argv[3] if len(sys.argv) > 3 else None
d = json.load(open(part_path, encoding="utf-8"))
R = d["results"]
for m in ("uniform", "adaptive"):
    if m not in R or len(R[m]) < 8 or not all("per_take_cider" in r for r in R[m]):
        raise SystemExit(f"{m} is not finished at all 8 budgets yet")

cfg = yaml.safe_load(open(os.path.join(REPO, "configs", "default.yaml")))
root = os.path.join(cfg["eval"]["data_root"], "egoexo")
takes = json.load(open(os.path.join(root, "takes.json"), encoding="utf-8"))
meta = {t["take_uid"]: t for t in takes if t.get("take_uid")}
uids = sorted({l.strip() for l in open(uids_file) if l.strip()})
assert not d["stats"]["missing_uids"], "missing uids would shift the order"
n = d["stats"]["n_takes"]
assert len(uids) == n == len(R["uniform"][0]["per_take_cider"]), "take order mismatch"
groups = [meta.get(u, {}).get("participant_uid", u) for u in uids]
scen = [meta.get(u, {}).get("parent_task_name", "unknown") for u in uids]
assert len(set(groups)) == d["stats"]["participants"], "participant count mismatch"

U = np.array([r["per_take_cider"] for r in R["uniform"]])   # (8 budgets, n takes)
A = np.array([r["per_take_cider"] for r in R["adaptive"]])
assert np.isfinite(U).all() and np.isfinite(A).all(), "NaN = uncached decodes"
hz = [r["target_hz"] for r in R["uniform"]]

print(f"{n} takes, {len(set(groups))} participants | primary: CIDEr adaptive - uniform")
print("\n  Hz    corpus U  corpus A   diff | per-take U  per-take A   diff  [95% CI takes]"
      "      adaptive ahead")
won_pt = won_corpus = 0
for i, h in enumerate(hz):
    dd = A[i] - U[i]
    lo, hi = boot_ci(dd)
    cu, ca = R["uniform"][i]["cider"], R["adaptive"][i]["cider"]
    won_pt += dd.mean() > 0
    won_corpus += ca > cu
    print(f"  {h:4.2f}  {cu:8.3f}  {ca:8.3f} {ca - cu:+6.3f} | {U[i].mean():10.3f}  {A[i].mean():10.3f}"
          f" {dd.mean():+6.3f}  [{lo:+.3f},{hi:+.3f}] {'SIG' if lo > 0 or hi < 0 else 'ns '}"
          f"  {int((dd > 0).sum()):3d}/{n} takes")

across = (A - U).mean(axis=0)                    # per take, mean over the 8 budgets
lo, hi = boot_ci(across)
clo, chi = cluster_boot_ci(across, groups)
base = float(U.mean(axis=1).mean())              # = the script's baseline_mean
band = 0.02 * base
print(f"\n  PRIMARY  mean over budgets {across.mean():+.4f}  CI takes [{lo:+.4f},{hi:+.4f}]"
      f"  CI participants [{clo:+.4f},{chi:+.4f}]")
print(f"  uniform mean {base:.4f}  (diff = {100 * across.mean() / base:+.1f}% of it;"
      f" ±2% tie band = ±{band:.4f})")
print(f"  budgets won by adaptive: per-take means {won_pt}/8, corpus CIDEr {won_corpus}/8")
print(f"  takes where adaptive is ahead on the 8-budget mean: {int((across > 0).sum())}/{n}")

if hi < 0 and clo < 0 and chi < 0 and (8 - won_pt) >= 6:
    verdict = "CLAIM STANDS: CI entirely below 0 and uniform wins >= 6/8"
elif lo > 0:
    verdict = "WITHDRAW: CI entirely above 0"
elif hi < 0:
    verdict = "CI below 0 but uniform wins < 6/8 budgets: claim only partly stands"
else:
    verdict = ("TIE (CI inside ±2%)" if -band <= lo and hi <= band
               else "NO RELIABLE DIFFERENCE (CI straddles 0)")
print(f"  pre-registered verdict: {verdict}")

print("\n  per scenario, CIDEr adaptive - uniform (mean over budgets)")
for s in sorted(set(scen)):
    ix = [i for i, x in enumerate(scen) if x == s]
    v = across[ix]
    slo, shi = boot_ci(v)
    print(f"    {s:12} n={len(ix):3d}  {v.mean():+.4f} [{slo:+.4f},{shi:+.4f}]"
          f"  uniform mean {U[:, ix].mean():.3f}")

if s1_path:  # pre-registered sanity check: decoding must not change the semantic cells
    s1 = json.load(open(s1_path, encoding="utf-8"))["results"]
    same = all(np.array_equal(np.asarray(a["per_take_semantic"]), np.asarray(b["per_take_semantic"]))
               for m in ("uniform", "adaptive") for a, b in zip(R[m], s1[m]))
    print(f"\n  semantic per-take arrays identical to {os.path.basename(s1_path)}: {same}")
