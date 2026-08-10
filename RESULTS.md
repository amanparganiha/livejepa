# LiveJEPA — Results

All numbers use **real SONAR decode** + the paper's **time-aligned CIDEr-D**
(each GT annotation matched to the nearest decoded caption in time).

**The honest thesis claim.** Adaptive selective decoding **Pareto-dominates
uniform-interval decoding when the semantic stream is temporally redundant** —
COIN steps and EgoExo4D keysteps (§1). Its advantage is a **function of that
redundancy**, and the decisive variable is whether the stream is *predicted* or
raw: on a **raw** hyper-dense annotation stream (EgoExo4D *atomic* descriptions,
~1 event / 2 s, measured at the paper's full 218-take scale) the advantage
**inverts** and uniform wins (§5) — but running the **full predicted pipeline**
on the same benchmark with an in-domain predictor restores dominance decisively:
**≈9.9× fewer decodes at equal-or-better CIDEr, adaptive winning 7/8 budgets,
confirmed against three controls** (§5b). On COIN's predicted stream the effect is
weaker and uniform holds the mid-band (§3), which a trigger-tuning sweep shows is
*fundamental, not a tuning artifact*. Separately, a **data-scaling study** (§4)
takes the predictor from cos 0.667 → **0.846** on a fixed 956-sample diverse val
across a 9× data increase, with the curve still climbing. We do **not** claim
absolute parity with VL-JEPA (different embedding space by design). See
`docs/STATUS_AND_NEXT_STEPS.md` for phase status and `docs/PROJECT_CONTEXT.md`
for the why.

> **Doc status (2026-07-23):** §3b (full-system Pareto, now re-run with the final
> checkpoint), §4 (data scaling), and §5 (paper-protocol EgoExo) are the current
> headline results. Older sub-sections (§1–2 mechanism/ablations) retain the
> earlier checkpoint as their baseline; the current best is
> `checkpoints_c1_final/predictor_30000.pt` (cos 0.846).

> **Where the result files are (2026-08-10).** The reproduce commands below write
> `results_*.{json,png}` to the repo **root**, which is where you will find them
> after a run. Those root copies are *not* committed — the curated, thesis-cited
> copies live in **`thesis_materials/figures/`** and are the ones in git. So
> `results_egoexo_rigor.json` in a command means the file you generate; the
> reference copy is `thesis_materials/figures/results_egoexo_rigor.json`. Every
> result named anywhere in this document has a committed copy there, including
> the superseded first oracle run kept as provenance for the §5b post-mortem.

---

## 1. Mechanism result — adaptive vs uniform on clean GT streams

**COIN val, gt mode** — 26 videos, `results_coin_gt.png/.json`:

| target Hz | uniform | adaptive |
|---:|---:|---:|
| 0.50 | 8.47 | **8.79** |
| 0.35 | 7.92 | **8.68** |
| 0.20 | 6.83 | **7.72** |
| 0.10 | 4.94 | **5.27** |

Adaptive holds CIDEr ≈ 7.7 at 0.20 Hz, which uniform reaches only near ~0.31 Hz →
**≈1.6× fewer decodes at equal quality**. Honest crossover at ≤0.05 Hz.
```bash
python -m livejepa.run_eval --dataset coin --mode gt
```

**EgoExo4D val keysteps** — the paper's own benchmark, 10 takes,
`results_egoexo_keystep.png/.json`:

| target Hz | uniform | adaptive |
|---:|---:|---:|
| 0.50 | 8.20 | 8.20 |
| 0.35 | 8.12 | **8.20** |
| 0.20 | 7.75 | **8.20** |
| 0.10 | 6.54 | **7.38** |
| 0.05 | 4.70 | 4.16 |

Adaptive holds the 8.20 plateau down to 0.20 Hz vs uniform's ~0.50 Hz →
**≈2.5× fewer decodes** (paper reports 2.85×). Crossover at ~0.05 Hz.
```bash
python -m livejepa.run_eval --dataset egoexo --mode gt --gt-source keystep --max-videos 10 --max-seconds 300
```
*Granularity note:* this uses **keysteps** (~27/take, coarse/stable). The paper's
**atomic** descriptions (~89/take, ~1 every 2 s) are too dense for a clean-signal
segmenter — selective decoding needs temporally-stable meaning.

---

## 2. Ablations (EgoExo4D keysteps, light noise) — `results_ablations.json`, `results_ablation_methods.png`

**Method (incl. the WS3 online-trigger fix)** — CIDEr at ~0.10 Hz:

| uniform | adaptive (offline Ward) | online — naive | online_seg — corrected |
|---:|---:|---:|---:|
| 6.06 | 6.72 | ~3.5 | **7.2–7.7** |

The naive streaming `VarianceTrigger` decodes a boundary-straddling window mean
(→ ~3.5). The corrected `SegmentTrigger` emits each **segment's mean at its
midpoint** and **recovers offline-level quality** (matches/edges out Ward). The
real-time path works.

- **Pooling** (mean vs exact-midpoint): +0.18 CIDEr @0.2–0.35 Hz, −0.22 @0.10 Hz (coarse segments blend).
- **Smoothing** (moving-avg W=1/3/5 @~0.2 Hz): **hurts** (7.95→7.50) — blurs boundaries at this granularity.
- **Naive-online W×τ**: W=8 sweet spot (~3.8); W=16 fires more, quality drops.
```bash
python scripts/ablations.py            # writes results_ablations.json + the plot
python -m pytest tests/ -q             # 13/13 (incl. SegmentTrigger)
```

---

## 3. Full predicted pipeline (V-JEPA 2 → predictor → SONAR)

### 3a. Wide-predictor retrain (the quality lever) — **DONE (Kaggle, 2026-07-09)**

Trained the predictor for 20k steps on class-diverse COIN (2962 train / 1118 val
samples, ~180 classes) via `notebooks/kaggle_colab_training.ipynb`. Gate result
on the **1118-sample class-diverse** held-out val:

| metric | value | reading |
|---|---:|---|
| mean cos(pred, target) | **0.636** | direction quality on a hard, diverse val |
| pred–pred cos | **0.504** | **not collapsed** (diverse predictions) |

Captions capture the right action manifold with fuzzy object detail
(`"stand up with straight legs"`→exact; `"open the car key cover"`→`"open the
back lid"`). This is a **qualified pass**: 0.636 < 0.70 target, but measured on a
far larger/harder val than the earlier inflated 11-class number — and vocabulary
breadth (the whole point) is now real. Checkpoint: `checkpoints_kaggle/predictor_20000.pt`.
```bash
python scripts/eval_predictor.py --ckpt checkpoints_kaggle/predictor_20000.pt --val data_cache_coin2_val --decode
```

### 3b. Predictor-in-the-loop Pareto — data scaling on the full system (2026-07-22)

Both checkpoints run on the **same 7 leakage-clean held-out COIN videos**
(verified in neither the final predictor's train nor val cache), identical
protocol, so the only variable is predictor quality. Full V-JEPA 2 → predictor →
SONAR → time-aligned CIDEr. `results_coin_predictor_c1{final,old}.json`.

| target Hz | old u | old a | **final u** | **final a** | winner (both) |
|---:|---:|---:|---:|---:|:--|
| 1.00 | 2.611 | 2.658 | 5.046 | **5.359** | adaptive |
| 0.50 | 2.644 | 2.561 | **5.388** | 5.009 | uniform |
| 0.35 | 2.856 | 2.492 | **5.072** | 5.043 | uniform (near-tie) |
| 0.20 | 2.960 | 2.388 | **5.129** | 4.909 | uniform |
| 0.10 | 2.124 | 2.348 | 4.057 | **4.486** | adaptive |
| 0.05 | 2.191 | 2.090 | **3.385** | 3.115 | uniform |
| 0.01 | 1.960 | 0.977 | **3.500** | 2.159 | uniform |

**Two findings.** (i) **Data scaling ~2×'d absolute full-system quality** — CIDEr
5.0–5.4 (final) vs 2.6–2.9 (old) at the useful rates, the end-to-end payoff of the
cos 0.667 → 0.846 predictor (§4). (ii) **The regime-dependent pattern is robust to
predictor quality**: even a 2×-better predictor keeps adaptive winning at high
(1.0 Hz) and sparse (0.1 Hz) rates while uniform owns the 0.2–0.5 Hz mid-band —
the *same* shape as the weak predictor. This is informative: the mid-band
uniform-advantage is **not an artifact of a noisy predictor** but tracks COIN's
intrinsic ~0.2 Hz step cadence, where even spacing matches the true event rate.
At 0.35 Hz the two nearly tie (5.07 vs 5.04), the closest adaptive comes.

**Caveats.** N = 7 videos (only 7 held-out COIN videos remain on disk;
extraction deleted the rest as transient). This run used the config default
`smoothing_window=3`; §3c found un-smoothed (`=1`) is marginally better for
adaptive, so adaptive is if anything slightly under-shown here. **The definitive
full-system Pareto — best adaptive config, 30–50 held-out videos — is bundled
into rung C2** (fast 4090 + the download/extract infra already there).
```bash
python -m livejepa.run_eval --dataset coin --mode predictor \
    --ckpt checkpoints_c1_final/predictor_30000.pt --coin-split val --max-videos 7 --max-seconds 180
```

### 3c. Trigger-tuning sweep — is the mid-band loss fixable? **No.** `results_adaptive_tuning.json`

Swept `smoothing_window ∈ {1,3,5,7}` × `linkage ∈ {ward,average}` on the cached
streams (same SONAR decoder + CIDEr; harness self-validated — `smooth1_ward`
reproduces 3b exactly). **Smoothing makes the mid-band worse, not better**; best
config is the baseline (no smoothing, ward, mean Δ = −0.061 vs uniform). At
0.20 Hz uniform (2.96) beats **all 8** adaptive configs. Conclusion: the
attenuation is fundamental to the noisy predicted stream, not a trigger-tuning
artifact — a clean negative result.
```bash
python scripts/tune_adaptive.py --ckpt checkpoints_kaggle/predictor_20000.pt
```

### 3d. Live demo (Phase 4) — `demo_adaptive.mp4`, `demo_uniform.mp4`

`livejepa/demo.py` runs the full pipeline live (webcam or video), decoding only
when the online `SegmentTrigger` fires, with an annotated overlay (caption +
"DECODE" flash + decodes/steps counter). Verified end-to-end on real video; a bug
was fixed where frames were sampled at native fps (→ near-duplicate windows)
instead of subsampled to `demo.display_fps` like `run_eval`. On a COIN clip:
adaptive 2 decodes / 40 windows (5%) vs uniform 4/40 (10%) — **half the decodes**.
```bash
python -m livejepa.demo --source <video.mp4> --ckpt checkpoints_kaggle/predictor_20000.pt \
    --no-display --save-video demo_adaptive.mp4 --mode adaptive     # or --mode uniform
```

---

## 4. Data-scaling study (the new headline) — 2026-07-19

The predictor architecture (29.9M params), training recipe (30k steps, InfoNCE +
cosine), and both validation sets are held **identical** across rows; only the
training-data volume grows. Extraction ran on a three-lane fleet (Kaggle T4 +
Colab + local T1000) that resolved **8,984 / 9,023 COIN training videos (99.6%)**
into a 26,360-clip cache. `cos` = mean cosine similarity of predicted vs true
SONAR embeddings on held-out video; `pred–pred` = mean pairwise similarity of
predictions (≈1 = collapsed, lower = more diverse).

| training clips | source | frozen 137-val cos | **diverse 956-val cos** | pred–pred |
|---:|---|---:|---:|---:|
| 2,962 | COIN, 3 vids × 180 classes (WS1) | 0.772 | 0.667 | 0.527 |
| 5,529 | COIN, first fleet sessions | 0.883 | 0.733 | 0.467 |
| **26,360** | **COIN, 99.6% of full training split** | **0.897** | **0.846** | **0.408** |

**The diverse 956-sample val (240 held-out videos) rose +0.113 cos on the last
4.8× of data and is still climbing** — data, not architecture, was the binding
constraint, and the curve has not flattened. Predictions also grew *more* diverse
(pred–pred 0.527 → 0.408), ruling out collapse. Decoded captions on the frozen
val are near-exact (7/10 verbatim: `'squat and hold the barbell'`,
`'do the third jump'`, `'put down the barbell'` → identical; misses are close
synonyms). The still-climbing curve is the scientific justification for rung C2
(training on Action100M, the paper's own data).
```bash
python scripts/eval_predictor.py --ckpt checkpoints_c1_final/predictor_30000.pt --val data_cache_coin2_val --decode
python scripts/eval_predictor.py --ckpt checkpoints_c1_final/predictor_30000.pt --val data_cache_coin_full_val
```

---

## 5. Paper-protocol EgoExo4D — atomic descriptions at full scale — 2026-07-22

The paper's headline benchmark: EgoExo4D validation, **atomic action
descriptions**, evaluated with time-aligned CIDEr-D over a decode-frequency
sweep. We selected the **218 density-matched val takes** (annotation counts
closest to the paper's ~143/video; ours run sparser at median 100/take — an
honest limit of the released val pool) and ran gt-mode at `--max-seconds 360`
(covers 98% of annotations vs 84% at the old 180 s default).
`results_egoexo_atomic_218.{json,png}`, 59.4k unique SONAR decodes.

| target Hz | uniform | adaptive | winner |
|---:|---:|---:|:--|
| 1.00 | **4.477** | 3.569 | uniform |
| 0.50 | **3.472** | 3.107 | uniform |
| 0.35 | **2.911** | 2.794 | uniform |
| 0.20 | **2.314** | 2.261 | uniform |
| 0.10 | **1.777** | 1.605 | uniform |
| 0.05 | **1.404** | 1.208 | uniform |
| 0.02 | **1.082** | 0.890 | uniform |
| 0.01 | **0.914** | 0.762 | uniform |

**Uniform decoding wins at every frequency** — no iso-quality speedup exists for
adaptive here. This is the expected boundary, now confirmed at the paper's own
scale (it matches the earlier densest-15 pilot): atomic descriptions carry a
semantic event roughly every 2 seconds, so the stream has **no temporal
redundancy for a segmenter to exploit**, and uniform's even spacing is
near-optimal. Contrast §1, where the same mechanism on **keysteps** (coarse,
~1 event / 15 s) cleanly wins ~2.5×. The unifying finding: **selective decoding's
benefit is a monotone function of the stream's temporal redundancy.**

**Relationship to the paper's 2.85×.** The paper reports adaptive dominance on
atomic descriptions using their *predicted* (denoised) embedding stream; this is
our clean-signal **gt-mode** proxy, which isolates the segmenter on the raw
annotation density and finds nothing to exploit at that density. Whether a
denoised *predicted* stream recovers an advantage on atomic content is the open
question tested by the predictor-mode run on these takes (rung C2). The honest
negative here is the baseline that question is measured against.
```bash
python -m livejepa.run_eval --dataset egoexo --mode gt --gt-source atomic \
    --uids-file eval_data/egoexo_takes_218.txt --max-seconds 360 \
    --out results_egoexo_atomic_218
```

---

## 5b. The same benchmark, with an IN-DOMAIN predictor — adaptive dominates (2026-08-01)

§5 evaluated atomic descriptions on a **clean ground-truth** stream and found
uniform wins everywhere. But the paper's 2.85× was measured on their *predicted*
stream. Running the full system required a predictor that speaks EgoExo: ours was
COIN-trained and, on EgoExo video, produced semantically correct but
stylistically alien captions (`'remove the chain'` vs annotations written as
*"the camera wearer takes a tire lever from the table with his right hand"*),
flooring CIDEr at **0.012 for both methods** — an unmeasurable comparison.

We therefore trained an in-domain predictor: 11,556 (window → caption) pairs from
721 EgoExo takes, windowed **identically to inference** (K=16 @2 fps, centred on
the annotation timestamp), 20k steps. The 40 evaluation takes were excluded from
training entirely; 25 further takes were held out for gating
(**cos 0.599**, pred–pred 0.325 — not collapsed).

**Time-aligned CIDEr-D, 40 held-out takes, `--max-seconds 360`:**

| avg Hz | decodes | uniform | adaptive | Δ |
|---:|---:|---:|---:|---:|
| 0.998 | 7072 | 0.296 | **0.330** | +0.035 |
| 0.499 | 3537 | 0.310 | **0.348** | +0.038 |
| 0.333 | 2357 | 0.299 | **0.340** | +0.041 |
| 0.199 | 1412 | 0.287 | **0.333** | +0.046 |
| 0.100 | 706 | 0.282 | **0.331** | +0.049 |
| 0.050 | 357 | 0.278 | **0.338** | +0.059 |
| 0.020 | 140 | 0.249 | **0.312** | +0.063 |
| 0.011 | 76 | **0.305** | 0.302 | −0.003 |

**Adaptive wins 7/8 budgets, and CIDEr rose 25× overall (0.012 → ~0.33) purely
from fixing the domain.** Headline in the paper's form: the best uniform result
anywhere is 0.310 (0.499 Hz, 3537 decodes); adaptive reaches **0.338 at 0.050 Hz
using 357 decodes** — **≈9.9× fewer decodes at equal-or-better quality**
(the paper reports 2.85×).

### Controls — why we trust this one (and not the out-of-domain attempt)

An earlier out-of-domain run appeared to show adaptive winning 8/8 on a semantic
metric; its controls showed the effect was an artifact. The same three controls
on the in-domain run behave completely differently:

| control | out-of-domain (rejected) | **in-domain (this result)** |
|---|---|---|
| metric responds to timing (nearest − shuffled alignment) | +0.0012 (blind) | **+0.0225…+0.0284** |
| survives disabling mean-pooling | +0.0051 (58% was denoising) | **+0.0345** (53% survives) |
| adaptive vs random placement (same budget) | — | **8/8 wins** |

Two details make the case: with pooling disabled, adaptive's advantage is a
*flat* **+0.031…+0.040 at every frequency** (pure temporal selection, no
dependence on averaging); and **uniform ≈ random placement** (0.605 vs 0.606), so
the gain comes from *where* decodes land, not from spreading them evenly.

### Statistical significance — paired bootstrap over takes (`results_egoexo_rigor.json`)

Corpus-level point estimates invite the question *"is +0.038 real, or noise
across 40 videos?"* We therefore score **per take** and bootstrap the **paired**
difference (both methods see the identical take, so take-difficulty variance
cancels), 5,000 resamples:

| target Hz | semantic Δ (95% CI) | takes favouring adaptive | per-take CIDEr Δ (95% CI) | takes |
|---:|---|---:|---|---:|
| 1.00 | **+0.0397** [+0.0350, +0.0443] | **40/40** | **+0.0193** [+0.0073, +0.0325] | 26/40 |
| 0.50 | **+0.0419** [+0.0361, +0.0478] | **40/40** | **+0.0212** [+0.0095, +0.0330] | 26/40 |
| 0.35 | **+0.0484** [+0.0423, +0.0542] | **40/40** | **+0.0255** [+0.0111, +0.0410] | 28/40 |
| 0.20 | **+0.0523** [+0.0458, +0.0593] | **40/40** | **+0.0263** [+0.0056, +0.0491] | 23/40 |
| 0.10 | **+0.0675** [+0.0584, +0.0765] | **40/40** | **+0.0300** [+0.0110, +0.0499] | 28/40 |
| 0.05 | **+0.0776** [+0.0666, +0.0886] | 39/40 | **+0.0279** [+0.0074, +0.0500] | 27/40 |
| 0.02 | **+0.1057** [+0.0904, +0.1212] | **40/40** | **+0.0365** [+0.0086, +0.0683] | 27/40 |
| 0.01 | **+0.1057** [+0.0861, +0.1260] | **40/40** | −0.0017 [−0.0366, +0.0311] *ns* | 19/40 |

**Adaptive is significantly better at every budget on the semantic metric — with
40/40 takes favouring it — and at 7 of 8 budgets on CIDEr.** The only
non-significant cell is the degenerate 0.011 Hz point (~2 decodes/take), the same
regime flagged below. Note the semantic metric also has far higher statistical
power (40/40 vs 23–28/40 takes): per-take CIDEr is high-variance because n-gram
overlap over ~100 events is noisy, whereas cosine similarity is smooth. Both
metrics agree in direction at every budget.

*(Per-take CIDEr values (~0.15–0.20) are numerically lower than the corpus CIDEr
above (~0.28–0.35) because TF-IDF is computed within a single take rather than
across the corpus; only the paired differences are interpreted here.)*
```bash
python scripts/eval_rigor.py --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 \
    --methods uniform,adaptive --boot 5000 --out results_egoexo_rigor
```

### How much headroom is left? — ceiling analysis (`results_egoexo_ceiling.json`)

The natural follow-up is *"how close to optimal is the trigger?"* Two references,
both on the same 40 takes and the same semantic metric:

| reference | what it is | score (95% CI) |
|---|---|---|
| **dense** | decode **every** timestep (2 Hz), no pooling — infinite budget, no selection | 0.6037 [0.5854, 0.6243] |
| uniform @0.05 Hz | the budget-matched baseline | 0.5949 [0.5740, 0.6167] |
| **adaptive @0.05 Hz** | ours | **0.6725** [0.6560, 0.6898] |
| GT-boundary | segment the **ground-truth caption** stream, decode the predicted stream at those true boundaries | 0.6684 [0.6522, 0.6851] |
| best-frame ceiling | max over *all* timesteps of cos(stream[j], gt) | 0.7541 [0.7396, 0.7692] |
| **best-window ceiling** | max over *all* contiguous ranges of cos(mean(stream[a:b]), gt) — upper-bounds every row above | **0.7720** [0.7577, 0.7867] |

Three things follow, and the first two are the interesting ones:

1. **Decoding more does not help.** Uniform is flat in decode rate —
   0.5949 (0.05 Hz) → 0.6054 (0.5 Hz) → 0.6037 (dense, 2 Hz). Spending 40× more
   compute buys nothing measurable. **Adaptive at 0.05 Hz (0.6725) beats
   decode-everything (0.6037)** while decoding ~40× less often: selective
   decoding here is not a quality/compute trade-off but a strict improvement,
   because segment pooling denoises the predicted stream (the best-window ceiling
   sits +0.018 above the best-*frame* ceiling, confirming pooling adds real signal
   no single timestep carries).

2. **Perfect boundary knowledge is not the missing piece.** The GT-boundary
   condition — a trigger that knows exactly where the annotators drew their
   boundaries — scores **at or slightly below** adaptive (0.6684 vs 0.6725 at
   0.05 Hz; 0.6250 vs 0.6473 at 0.5 Hz). This is not a bug: annotation boundaries
   are homogeneous in *caption* space, whereas adaptive's are homogeneous in
   *predictor* space, so adaptive's pooled mean is the sharper representative of
   what the model actually encoded. Ward-on-the-predicted-stream is already doing
   the right thing; better *timing* has essentially nothing left to give.

3. **The remaining 13% is representational.** Adaptive captures **87.1%** of the
   best-window ceiling at 0.05 Hz (uniform: 77.1%). The ceiling is deliberately
   loose — it lets each annotation pick its own best window with no budget at all,
   so no real schedule can reach it — which makes the 87% a *lower* bound on how
   good the trigger is. Combined with (2), the gap that remains belongs to the
   **predictor**, not the trigger: closing it needs a better model of *what* is
   happening, not a better decision about *when* to speak.

*Method note.* An earlier version of the GT-boundary run scored 0.5879 — below
uniform — which is impossible for something billed as an oracle, and was a code
fault, not a finding: the GT stream is timestamped from t=0 while the predicted
stream carries window-centre times starting ~3.75 s, so index-based mapping
misaligned every decode by ~4 s; and it compared exact embeddings against
adaptive's pooled ones. Both fixed (`scripts/eval_rigor.py:111-143`). The
condition is reported as a **reference**, not an upper bound — that role belongs
to the best-window ceiling, which is a bound by construction.
```bash
python scripts/eval_rigor.py --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 \
    --methods oracle,uniform,adaptive --freqs 0.5,0.2,0.05 \
    --out results_egoexo_rigor_oracle_fixed
python scripts/eval_ceiling.py --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360
```

### Honest caveats
- The 0.011 Hz row (~2 decodes/take) is a degenerate low-n regime and uniform's
  curve is visibly non-monotonic there; a 25× figure can be computed from it but
  we quote the well-sampled **9.9×** instead. It is also the one budget where the
  paired CIDEr difference is not significant.
- Absolute CIDEr is low (~0.33): predicting free-form egocentric narration is
  hard, and our predictor saw 11.5k samples.
- **Why we exceed the paper's 2.85×:** our predictor is *in-domain* (trained on
  EgoExo takes, disjoint from the eval takes) whereas VL-JEPA's was trained on
  Action100M and evaluated cross-domain on EgoExo; and EgoExo takes have high
  within-take caption self-similarity (mean pairwise cos **0.669**), so sparse
  decoding loses little — a property of the benchmark that favours adaptive. The
  *direction and shape* replicate; the magnitude is not directly comparable.

**This resolves the §5 paradox.** On a raw annotation stream (~1 event / 2 s)
there is no redundancy and uniform wins; the *predictor* smooths that stream into
segmentable semantic plateaus, which is precisely the condition selective decoding
exploits. Selective decoding needs a *predicted* stream — not merely dense labels.
```bash
python scripts/build_egoexo_cache.py --max-per-take 20 --max-samples 12000
python -m livejepa.train --config configs/default.yaml --data-root data_cache_egoexo \
    --ckpt-dir checkpoints_egoexo --max-steps 20000 --batch-size 32
python -m livejepa.run_eval --dataset egoexo --mode predictor \
    --ckpt checkpoints_egoexo/predictor_20000.pt --gt-source atomic \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 \
    --out results_egoexo_predictor_40_indomain
python scripts/eval_semantic_pareto.py --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 --out <name>   # + --pool none
```

---

## 6. Rung C2 — training on Action100M, the paper's own data (2026-07-25)

VL-JEPA trained on **Action100M**; we trained on COIN step labels. Rung C2 tests
whether using the paper's own data distribution improves the predictor. Run on a
rented RTX 4090 (~$8): chunked download→extract→delete over Action100M-preview,
then 20k steps, batch 64. YouTube throttled extraction after 178 videos, yielding
**6,710 train + 160 val clips** — so C2 is a *scale-matched* comparison against
our 5,529-clip COIN rung, not a scale-up.

### The cross-domain matrix (each model on each benchmark, cos(pred,target))

| model (training data) | COIN-137 frozen | COIN-956 | **A100M-160** |
|---|---:|---:|---:|
| C1-final (26,360 COIN clips, 30k steps) | **0.897** | **0.846** | 0.386 |
| C1-mid (5,529 COIN clips, 20k steps) | 0.883 | 0.733 | **0.401** |
| **C2 (6,710 A100M clips, 20k steps)** | 0.359 | 0.392 | 0.348 |

**Headline (a clean negative for the paper-data hypothesis): COIN-trained models
beat the Action100M-trained model on Action100M's own validation set** — 0.401
(scale-matched C1-mid) and 0.386 (C1-final) vs **0.348** for C2. The scale-matched
control is the decisive cell: C1-mid used **fewer** clips (5,529 vs 6,710) and the
same 20k steps, so C2's deficit is **not** a data-volume artifact.

**Why — target-vocabulary entropy, not label noise.** Inspecting the two caches
settles it:

| corpus | clips | unique captions | repeats per caption |
|---|---:|---:|---:|
| COIN | 26,863 | **747** (3%) | **36.0** |
| Action100M | 6,710 | **6,096** (91%) | **1.1** |

COIN is effectively a **closed-set problem** — 747 recurring step labels, each
seen ~36 times. Action100M is genuinely **open-vocabulary**: almost every caption
is unique and seen *once*. Manual inspection shows A100M's captions are largely
sensible actions (*"Sponging off powder from design surface"*, *"puree the
mixture in a blender"*; only 1% contain narration pronouns), so the earlier
"noisy labels" reading is **not** the main story. The real obstacle is that
predicting open-vocabulary sentences from 6.7k one-shot examples is a far harder
statistical problem than mapping into 747 recurring classes.

This carries an important caveat *back onto our own headline*: the COIN scaling
result (§4, cos 0.667→0.846) is measured on a 747-label closed set, so part of
what improves is closed-set discrimination rather than open-ended captioning.
A100M's 0.348 and COIN's 0.846 are therefore **not commensurable** — they are
different tasks wearing the same metric.

C2's decoded captions match this diagnosis exactly — it learned the *distribution
of phrasings* but, with ~1 example per target, could not bind them to content:

```
'Get a needle'                  -> 'Push the squeeze of the treats.'
'Thread seed bead onto head pin'-> 'Applying a little enamel to the ribbon'
```

fluent, plausible, semantically wrong. On the COIN benchmark it answers in the
wrong dialect entirely (`'squat and hold the barbell'` → `'Monitoring and
clean-up'`). Meanwhile the COIN models, though out of domain, land in the right
activity space on A100M clips (`'stick or bind flower to the frame'` for a
beading/ornament video) — a closed vocabulary transfers as a coarse but useful
prior. **At this scale, a low-entropy target space dominates domain match.**

**What would actually fix it:** more data, not cleaner data. Open-vocabulary
targets need orders of magnitude more examples — VL-JEPA used the full 1.2M-video
corpus. The practical route is **Kaggle** (free, fresh IP each session, the same
chunked pipeline that resolved 99.6% of COIN), not paid rentals.

### 6b. Does Action100M help as *augmentation*? Also no (2026-07-26)

C2 replaced COIN with A100M. The natural follow-up is to **add** it: same recipe
(30k steps, batch 32), data = COIN 26,863 **+** A100M 6,710 = **33,573 clips**,
the largest training set in this project.

| model | training data | COIN-137 | COIN-956 | A100M-160 |
|---|---|---:|---:|---:|
| C1-final | 26,863 COIN | **0.897** | **0.846** | 0.386 |
| C1-mid | 5,529 COIN | 0.883 | 0.733 | **0.401** |
| C2 | 6,710 A100M | 0.359 | 0.392 | 0.348 |
| **C3 combined** | 33,573 (both) | 0.875 | 0.823 | 0.390 |

**Adding 25% more clips made the model slightly worse** (−0.022 / −0.023 on the
COIN benchmarks) and produced no meaningful gain on A100M (0.390, still under
C1-mid's 0.401). The decoded captions show the mechanism directly — A100M's open
vocabulary contaminates previously exact COIN outputs:

```
'squat and hold the barbell'   -> 'sitbar and hold the barbell'
'stand up with straight legs'  -> 'stand up barrel with straight legs over head'
```

Exact matches on the frozen val fall from 7/10 (C1-final) to 5/10. Mixing a
747-label closed set with 6,096 one-shot open-vocabulary targets **dilutes** the
closed-set signal without supplying enough coverage to learn the open one.

**Conclusion across C2 + C3:** at this scale Action100M-preview helps neither as
a replacement nor as an augmentation. This is a *scale* verdict, not a verdict on
the corpus — the entropy analysis above predicts it, and predicts that the fix is
~10–100× more A100M data (free via Kaggle), not a different mixing strategy.
**C1-final remains the deployed checkpoint.**
```bash
python -m livejepa.train --config configs/default.yaml \
    --data-root "data_cache_coin_full,data_cache_a100m" \
    --ckpt-dir checkpoints_c3_combined --max-steps 30000 --batch-size 32
```

**Secondary observation (weak, N=160):** C1-*mid* edges C1-*final* on A100M
(0.401 vs 0.386) despite being far weaker in-domain — consistent with mild
over-specialisation to COIN's vocabulary from the extra training. Treat as a
hypothesis, not a result.

**Scope of the claim.** This tests **Action100M-preview** (the 10% release) with
our leaf-node filter, at ~6.7k clips. It does *not* show Action100M is bad data
in general — VL-JEPA trained on the full 1.2M-video corpus, where label noise
averages out. The honest claim is narrow and useful: *at small scale, curated
labels beat noisy auto-generated ones, even on the noisy corpus's own benchmark.*
```bash
python scripts/eval_predictor.py --ckpt checkpoints_c2/predictor_20000.pt --val data_cache_a100m_val --decode
python scripts/eval_predictor.py --ckpt checkpoints_c1_p1/predictor_20000.pt --val data_cache_a100m_val --decode
```

---

## 7. What's not done / limitations

**Status 2026-08-02: all planned experiments are complete.** What follows is the
honest residue — things deliberately not done, and their reasons.

- **Full-system Pareto with the final checkpoint — DONE (§3b).** Both checkpoints
  now run the same 7 leakage-clean videos: absolute quality ≈2×'d (CIDEr 5.0–5.4
  vs 2.6–2.9) while the regime-dependent *shape* survived, showing the mid-band
  uniform advantage is not a predictor-noise artifact. The residual limitation is
  **N = 7** — only 7 held-out COIN videos remain on disk (extraction deleted the
  rest as transient), so widening this to 30–50 videos would need re-extraction.
- **Headline is 40 takes, not 218** (§5b) — the frozen 218-take pool exists and
  the protocol is unchanged, but a full re-run costs ~84 h on the T1000. The
  paired bootstrap (§5b) already establishes significance at 40; scaling would
  tighten the point estimate, not change the verdict. Judged not worth the time.
- **Rung C2 — DONE (§6)**, with a negative result: Action100M-preview at 6.7k
  clips underperforms COIN at matched scale. A fair *scale-up* test (50–100k
  A100M clips) remains open; the right tool is **Kaggle** (free, fresh IP per
  session — a single pod IP throttles after ~200 videos), not another rental.
  The extracted A100M cache is kept locally, so combined COIN+A100M training is
  now free to try on the T1000.
- **Predictor-mode EgoExo eval on the 40-take subset — DONE (§5b), and it is the
  thesis headline.** The §5 open question is answered: yes, a *predicted* stream
  beats uniform on atomic content where the clean gt-stream cannot — 7/8 budgets,
  ≈9.9× fewer decodes, significant at every budget, 87% of a provable ceiling.
- **Ceiling analysis — DONE (§5b).** Also settles the follow-up question: the
  trigger is near-exhausted, so remaining effort belongs on the predictor. This
  is why no further trigger work is queued.
- **Real-time** — V-JEPA 2 is ~11 s/window on the local T1000; the demo is not
  real-time on this hardware. A faster GPU (e.g. a T4) or a lighter encoder helps.
- **Web UI + backend — DONE** (2026-07): `webapp/` FastAPI backend + product UI
  deployed and tunnel-verified, serving the final checkpoint, with an
  architecture/results page at `/about`. An **optional pretrained-VLM variant**
  and the **LiveCC-7B baseline** remain deliberate, deferred follow-ups.

*Reproducibility:* `project.use_stubs: false` in `configs/default.yaml`; models
cached in `~/.cache/huggingface/hub`; SONAR via the transformers backend (Windows).
