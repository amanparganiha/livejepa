"""Attribution table for the fidelity rerun (semantic metric, no decoding).

Which change moves the result from the old 218 set to the faithful benchmark:
the take set (218 count-matched vs 219 procedural), the annotations (all passes
merged vs first pass) or the 360 s cap? Each cell is one eval_gt_fidelity.py JSON.

usage: python results_fidelity/attribution.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CELLS = [  # label, file
    ("old 218 | all passes | cap 360 s (V)", "V_218_all_cap360.json"),
    ("old 218 | all passes | full (S4)", "S4_218_all_full.json"),
    ("old 218 | first pass | full (S3)", "S3_218_first_full.json"),
    ("proc219 | all passes | full (S2)", "S2_proc219_all_full.json"),
    ("proc219 | first pass | cap 360 s (S5)", "S5_proc219_first_cap360.json"),
    ("proc219 | first pass | full (S1 = C1)", "S1_proc219_first_full.json"),
]


def signs(per_budget, metric="semantic"):
    out = ""
    for r in per_budget:
        if r["metric"] != metric:
            continue
        out += "+" if r["significant"] and r["mean_diff"] > 0 else \
               "-" if r["significant"] and r["mean_diff"] < 0 else "0"
    return out


print("semantic metric; A-P = adaptive - uniform_pool (matched pooling), A-U = adaptive - uniform")
print("budget pattern 1.0 -> 0.01 Hz: + adaptive significantly ahead, - behind, 0 not significant\n")
print(f"{'cell':40} {'takes':>5} {'ann':>6} {'min':>5} {'s/ann':>5} | "
      f"{'A-P mean [95% CI takes]':>28} {'pattern':>8} | {'A-U mean':>8}")
for label, fn in CELLS:
    path = os.path.join(HERE, fn)
    if not os.path.exists(path):
        print(f"{label:40} missing")
        continue
    d = json.load(open(path, encoding="utf-8"))
    s = d["stats"]
    row = (f"{label:40} {s['n_takes']:5d} {s['mean_annotations']:6.1f} "
           f"{s['mean_stream_seconds'] / 60:5.2f} {1 / s['annotations_per_second']:5.2f} | ")
    p = d["paired"].get("adaptive_minus_uniform_pool", {})
    sp = p.get("summary", {}).get("semantic")
    if sp:
        row += (f"{sp['mean_diff_over_budgets']:+.4f} [{sp['ci95_takes'][0]:+.4f},"
                f"{sp['ci95_takes'][1]:+.4f}] {signs(p['per_budget']):>8} | ")
    else:
        row += f"{'(no uniform_pool in this run)':>37} | "
    su = d["paired"].get("adaptive_minus_uniform", {}).get("summary", {}).get("semantic")
    row += f"{su['mean_diff_over_budgets']:+8.4f}" if su else "n/a"
    print(row)
