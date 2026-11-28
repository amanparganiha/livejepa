"""Readable summary of one eval_gt_fidelity.py result (semantic screen + decode cost)."""
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
s = d["stats"]
print(f"{d['uids_file']} | passes={d['passes']} | cap={d['max_seconds']} | "
      f"takes={s['n_takes']} participants={s['participants']} scenarios={s['scenarios']}")
print(f"  annotations/take {s['mean_annotations']:.1f} | stream {s['mean_stream_seconds'] / 60:.2f} min "
      f"| density {s['annotations_per_second']:.3f}/s (one per {1 / s['annotations_per_second']:.2f} s)")

R = d["results"]
methods = [m for m in ("uniform", "uniform_pool", "adaptive", "take_mean") if m in R]
print("\n  semantic (mean of per-take means)\n  Hz     " + "".join(f"{m:>14}" for m in methods))
for i, row in enumerate(R[methods[0]]):
    print(f"  {row['target_hz']:5.2f}  " + "".join(f"{R[m][i]['semantic_mean']:14.4f}" for m in methods))

for name, block in d["paired"].items():
    sm = block["summary"].get("semantic")
    if not sm:
        continue
    note = "valid (matched pooling)" if name.endswith("uniform_pool") else \
        "NOT a placement test: the metric rewards pooling itself"
    print(f"\n  {name} [semantic, {note}]")
    print(f"    mean over budgets {sm['mean_diff_over_budgets']:+.4f}  CI takes "
          f"[{sm['ci95_takes'][0]:+.4f},{sm['ci95_takes'][1]:+.4f}]  CI participants "
          f"[{sm['ci95_participants'][0]:+.4f},{sm['ci95_participants'][1]:+.4f}]  "
          f"(baseline mean {sm['baseline_mean']:.4f}; ±2% = ±{0.02 * sm['baseline_mean']:.4f})")
    for r in block["per_budget"]:
        if r["metric"] == "semantic":
            print(f"    {r['target_hz']:5.2f}Hz {r['mean_diff']:+.4f} [{r['ci95'][0]:+.4f},{r['ci95'][1]:+.4f}]"
                  f" {'SIG' if r['significant'] else 'ns '} adaptive ahead on "
                  f"{r['takes_favoring_adaptive']}/{r['n_takes']} takes")

print("\n  per scenario, semantic adaptive - uniform_pool (mean over budgets)")
for sc, e in d["per_scenario"].items():
    v = e.get("semantic_adaptive_minus_uniform_pool")
    if v:
        print(f"    {sc:14} n={e['n_takes']:3d}  {v['mean']:+.4f} [{v['ci95_takes'][0]:+.4f},{v['ci95_takes'][1]:+.4f}]")

if d.get("cider_mode") == "cache-only":
    print("\n  CIDEr from cache (decodes missing from the cache = cost of a full run)")
    total = 0
    for m in methods:
        for row in R[m]:
            miss = row.get("decode_misses", 0)
            total += miss if m != "take_mean" or row is R[m][0] else 0
            c = f"{row['cider']:.3f}" if "cider" in row else "n/a"
            print(f"    {m:12} {row['target_hz']:5.2f}Hz  CIDEr {c:>7}  missing {miss}")
    print(f"  total uncached decodes (upper bound, before within-run dedup): {total}")
