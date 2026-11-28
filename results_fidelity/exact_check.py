"""Exact check (pre-registered in WORKLOG 2026-11-26, 19:05).

VL-JEPA's "exact" selective decoding against plain uniform: time-aligned CIDEr on the
ground-truth stream of the faithful benchmark (219 procedural takes, first annotator
pass, full length).

E1 = this run, configs/fidelity_exact.yaml (smoothing_window 1, pool none): adaptive
     decodes the RAW embedding at each Ward segment's midpoint and uniform decodes raw
     steps at fixed points, so only placement differs.
C1 = the main fidelity run (same takes, annotations and decode cache): uniform,
     uniform_pool and adaptive with smoothing 3 + mean pooling.

Together they fill a 2x2, placement {uniform, adaptive} x averaging {off, on}:
  U   uniform, raw steps                         C1 and E1 (must be identical)
  P   uniform_pool, smoothing 3 + block means    C1
  Ax  adaptive, raw midpoint steps               E1
  Am  adaptive, smoothing 3 + segment means      C1
For adaptive, averaging also moves the Ward boundaries (they are found on the smoothed
stream), so Am - Ax is averaging plus that boundary shift.

usage: python results_fidelity/exact_check.py <E1.json|E1.partial.json> <C1.json> <uids_file>
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

e1_path, c1_path, uids_file = sys.argv[1:4]
E = json.load(open(e1_path, encoding="utf-8"))
C = json.load(open(c1_path, encoding="utf-8"))
if "selective" in E:  # the final JSON records the config (the partial file does not)
    sel = E["selective"]
    assert sel.get("pool") == "none" and int(sel.get("smoothing_window", 1)) <= 1, \
        f"E1 was not run with the exact config: {sel}"


def grid(R, method, key="per_take_cider"):
    rows = R.get(method, [])
    if len(rows) < 8 or not all(key in r for r in rows):
        raise SystemExit(f"{method}: not finished at all 8 budgets yet")
    return np.array([r[key] for r in rows], dtype=float), [r["target_hz"] for r in rows]


U, hz = grid(E["results"], "uniform")          # (8 budgets, n takes)
Ax, hz_ax = grid(E["results"], "adaptive")
n = U.shape[1]
Uc, hz_c = grid(C["results"], "uniform")
P, _ = grid(C["results"], "uniform_pool")
Am, _ = grid(C["results"], "adaptive")
assert hz == hz_ax == hz_c, "budget lists differ between runs"
Uc, P, Am = Uc[:, :n], P[:, :n], Am[:, :n]     # n < 219 only in a --max-takes smoke test
assert np.isfinite(U).all() and np.isfinite(Ax).all(), "NaN = uncached decodes"

# take order and participants, exactly as eval_gt_fidelity.py builds them (sorted uids)
cfg = yaml.safe_load(open(os.path.join(REPO, "configs", "default.yaml"), encoding="utf-8"))
root = os.path.join(REPO, cfg["eval"]["data_root"], "egoexo")
takes = json.load(open(os.path.join(root, "takes.json"), encoding="utf-8"))
meta = {t["take_uid"]: t for t in takes if t.get("take_uid")}
uids = sorted({l.strip() for l in open(uids_file) if l.strip()})[:n]
assert not E["stats"]["missing_uids"] and E["stats"]["n_takes"] == n, "take order mismatch"
groups = [meta.get(u, {}).get("participant_uid", u) for u in uids]
scen = [meta.get(u, {}).get("parent_task_name", "unknown") for u in uids]

print(f"{n} takes, {len(set(groups))} participants | E1 = {os.path.basename(e1_path)}")
same = np.array_equal(U, Uc)
print(f"identity check, E1 uniform per-take CIDEr == C1 uniform at all 8 budgets: {same}")
if not same:
    raise SystemExit("  uniform differs between E1 and C1: the runs are not comparable. Stop.")


def ci_str(v):
    lo, hi = boot_ci(v)
    sig = "SIG" if lo > 0 or hi < 0 else "ns "
    return f"{v.mean():+7.3f} [{lo:+.3f},{hi:+.3f}] {sig}"


print("\nper-take CIDEr means; Ax = adaptive exact (raw midpoint), Am = adaptive mean (C1)")
print("   Hz      U      P     Ax     Am | Ax-U (primary) [95% CI]    Ax>U takes"
      " | Am-Ax [95% CI]               | corpus U  corpus Ax")
D = Ax - U
for i, h in enumerate(hz):
    cu = E["results"]["uniform"][i]["cider"]
    ca = E["results"]["adaptive"][i]["cider"]
    print(f"  {h:4.2f} {U[i].mean():6.3f} {P[i].mean():6.3f} {Ax[i].mean():6.3f} "
          f"{Am[i].mean():6.3f} | {ci_str(D[i])}  {int((D[i] > 0).sum()):3d}/{n}"
          f" | {ci_str(Am[i] - Ax[i])} | {cu:8.3f} {ca:9.3f}")

across = D.mean(axis=0)                       # per take, mean over the 8 budgets
lo, hi = boot_ci(across)
clo, chi = cluster_boot_ci(across, groups)
base = float(U.mean())                        # uniform's mean over budgets and takes
band = 0.02 * base
won = int(sum(D[i].mean() > 0 for i in range(len(hz))))
ci_b = [boot_ci(D[i]) for i in range(len(hz))]
sig_pos = sum(c[0] > 0 for c in ci_b)
sig_neg = sum(c[1] < 0 for c in ci_b)
print(f"\n  PRIMARY  Ax - U, mean over budgets {across.mean():+.4f}"
      f"  CI takes [{lo:+.4f},{hi:+.4f}]  CI participants [{clo:+.4f},{chi:+.4f}]")
print(f"  = {100 * across.mean() / base:+.1f}% of uniform's mean {base:.4f}"
      f" (±2% tie band = ±{band:.4f})")
print(f"  budgets: adaptive ahead {won}/8 ({sig_pos} significant), behind {8 - won}/8"
      f" ({sig_neg} significant); takes ahead on the 8-budget mean"
      f" {int((across > 0).sum())}/{n}")
if lo > 0 and clo > 0:
    verdict = "PLACEMENT ALONE HELPS (both CIs above 0)"
elif hi < 0 and chi < 0:
    verdict = "PLACEMENT ALONE LOSES (both CIs below 0)"
elif -band <= min(lo, clo) and max(hi, chi) <= band:
    verdict = "TIE (both CIs inside ±2% of uniform's mean)"
else:
    verdict = "NO RELIABLE DIFFERENCE (a CI straddles 0, or the two CIs disagree)"
print(f"  pre-registered verdict: {verdict}")

print("\n  2x2, per-take CIDEr, mean over budgets [95% CI takes], % of uniform's mean")
for label, v in [
        ("placement, averaging off    Ax - U", across),
        ("placement, averaging on     Am - P", (Am - P).mean(axis=0)),
        ("averaging, uniform          P - U", (P - U).mean(axis=0)),
        ("averaging*, adaptive        Am - Ax", (Am - Ax).mean(axis=0)),
        ("interaction  (Am-P) - (Ax-U)", ((Am - P) - (Ax - U)).mean(axis=0)),
        ("net, as in the paper        Am - U", (Am - U).mean(axis=0))]:
    lo2, hi2 = boot_ci(v)
    print(f"    {label:37} {v.mean():+.4f} [{lo2:+.4f},{hi2:+.4f}]"
          f"  {100 * v.mean() / base:+6.1f}%")
print("    * includes the Ward-boundary shift from segmenting the smoothed stream")

print("\n  per scenario, primary Ax - U (mean over budgets)")
for s in sorted(set(scen)):
    ix = [i for i, x in enumerate(scen) if x == s]
    v = across[ix]
    slo, shi = boot_ci(v) if len(ix) > 1 else (float("nan"),) * 2
    print(f"    {s:12} n={len(ix):3d}  {v.mean():+.4f} [{slo:+.4f},{shi:+.4f}]")
