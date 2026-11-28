"""Validation gate: does eval_gt_fidelity.py reproduce Table 7 (D.1) exactly?"""
import json
import sys

new = json.load(open(sys.argv[1] if len(sys.argv) > 1 else
                     "results_fidelity/V_218_all_cap360.json", encoding="utf-8"))
old = json.load(open("results_egoexo_atomic_218.json", encoding="utf-8"))
worst, ok = 0.0, True
for method in ("uniform", "adaptive"):
    for rn, ro in zip(new["results"][method], old["results"][method]):
        assert abs(rn["target_hz"] - ro["target_hz"]) < 1e-9
        same_n = rn["n_decodes"] == ro["n_decodes"]
        c_new = rn.get("cider")
        diff = abs(c_new - ro["cider"]) if c_new is not None else float("inf")
        worst = max(worst, diff)
        ok &= same_n and diff < 1e-6
        print(f"{method:9} {ro['target_hz']:5.2f}Hz  published {ro['cider']:.6f} (n={ro['n_decodes']})"
              f"  rerun {c_new if c_new is None else round(c_new, 6)} (n={rn['n_decodes']},"
              f" misses={rn.get('decode_misses')})")
print(f"\nGATE {'PASSED' if ok else 'FAILED'}: worst |diff| = {worst:.2e}, "
      f"takes {new['stats']['n_takes']} vs {old['n_videos']}")
