# LiveJEPA — Results

All numbers use **real SONAR decode** + the paper's **time-aligned CIDEr-D**
(each GT annotation matched to the nearest decoded caption in time).

**The honest thesis claim (revised 2026-11-17).** On **clean** streams, adaptive
*placement* **dominates uniform-interval decoding across the mid-band when the
stream is temporally redundant** — COIN steps and EgoExo4D keysteps (§1), with
uniform recovering at the lowest rates — and **inverts** on a hyper-dense raw
annotation stream (EgoExo4D *atomic* descriptions, ~1 event / 2 s, at the paper's
full 218-take scale; §5). On the **predicted** stream (§5b), adaptive beats
uniform decoding of single points at 7/8 budgets, but the gain is **averaging,
not placement**: a uniform baseline given the same pooling — as VL-JEPA's own
protocol gives it — matches adaptive (6/8 ties, one significant win each way) and
reaches a higher best score, so the earlier "≈9.9× fewer decodes" headline does
not survive a like-for-like baseline. On COIN's predicted stream uniform holds the
mid-band (§3), which a trigger-tuning sweep shows is *fundamental, not a tuning
artifact*. Separately, a **data-scaling study** (§4)
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
| 1.00 | 8.81 | 8.81 |
| 0.50 | 8.47 | **8.79** |
| 0.35 | 7.92 | **8.67** |
| 0.20 | 6.83 | **7.72** |
| 0.10 | 4.94 | **5.27** |
| 0.05 | **3.77** | 3.53 |
| 0.02 | **3.54** | 2.29 |
| 0.01 | **3.46** | 2.04 |

Adaptive holds CIDEr ≈ 7.7 at 0.20 Hz, which uniform reaches only near ~0.31 Hz →
**≈1.6× fewer decodes at equal quality**. Honest crossover at ≤0.05 Hz.
```bash
python -m livejepa.run_eval --dataset coin --mode gt
```

**EgoExo4D val keysteps** — 10 takes, `results_egoexo_keystep.png/.json` (not the
paper's benchmark: VL-JEPA reports on atomic descriptions, §5–5b):

| target Hz | uniform | adaptive |
|---:|---:|---:|
| 0.50 | 8.20 | 8.20 |
| 0.35 | 8.12 | **8.20** |
| 0.20 | 7.75 | **8.20** |
| 0.10 | 6.54 | **7.38** |
| 0.05 | **4.70** | 4.16 |
| 0.02 | **2.37** | 1.58 |
| 0.01 | **1.49** | 0.74 |

Adaptive holds the 8.20 plateau down to 0.20 Hz vs uniform's ~0.50 Hz →
**≈2.5× fewer decodes** (not comparable to the paper's 2.85×, which is on atomic
descriptions). Crossover at ~0.05 Hz.
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
adaptive, so adaptive is if anything slightly under-shown here. A wider COIN full-system
Pareto (30–50 held-out videos) was planned for the C2 rental but never run: C2's
time went to Action100M (§6), and widening it now would need re-extraction (§7).
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
*predicted* stream recovers an advantage on atomic content is answered in §5b:
against single-point uniform decoding it does, but against a uniform baseline with
the same pooling it does not — the gain is averaging. The honest negative here is
the baseline that answer is measured against.
```bash
python -m livejepa.run_eval --dataset egoexo --mode gt --gt-source atomic \
    --uids-file eval_data/egoexo_takes_218.txt --max-seconds 360 \
    --out results_egoexo_atomic_218
```

---

## 5b. The same benchmark on the PREDICTED stream — averaging, not placement (2026-08-01; corrected 2026-11-17)

§5 evaluated atomic descriptions on a **clean ground-truth** stream and found
uniform wins everywhere. But the paper's 2.85× was measured on their *predicted*
stream. Running the full system required a predictor that speaks EgoExo: ours was
COIN-trained and, on EgoExo video, produced semantically correct but stylistically
alien captions (`'remove the chain'` vs annotations written as
*"the camera wearer takes a tire lever from the table with his right hand"*),
flooring CIDEr at **0.012 for both methods** — an unmeasurable comparison.

We therefore trained an in-domain predictor: 11,556 (window → caption) pairs from
627 EgoExo takes (extraction hit its 12,000-sample cap before the 721-take
candidate pool was exhausted), windowed **identically to inference** (K=16 @2 fps,
centred on the annotation timestamp), 20k steps. The 40 evaluation takes were
excluded from training by take; 25 further takes were held out for gating
(**cos 0.599**, pred–pred 0.325 — not collapsed). Caveat found 2026-09-19: the 40
takes share participants (40/40) and recording sessions (39/40) with training
takes; a participant-disjoint retrain keeps 483 takes / 8,822 pairs.

**The correction (2026-11-17).** Adaptive decodes the *mean* of each Ward segment
of a 3-step-smoothed stream; the original uniform baseline decoded a *single raw
step*. VL-JEPA §4.6 decodes "either the exact embedding or the average-pooled
embedding within the segment" and reports that "average pooling provides
consistent gains for both strategies" — its uniform baseline pools too. So we added
**uniform+pool** (`--methods uniform_pool`): the same decode count and timestamps
as uniform, each decoded from the mean of its fixed block of the same smoothed
stream. Adaptive and uniform+pool differ only in where span boundaries fall. As a
timing-free reference, `take_mean` decodes the whole stream's mean once per take.

**Time-aligned CIDEr-D, 40 held-out takes, `--max-seconds 360`
(`results_egoexo_predictor_40_indomain_pooled.json`):**

| avg Hz | decodes | uniform | adaptive | uniform+pool |
|---:|---:|---:|---:|---:|
| 0.998 | 7072 | 0.296 | 0.330 | **0.335** |
| 0.499 | 3537 | 0.310 | **0.348** | 0.342 |
| 0.333 | 2357 | 0.299 | 0.340 | **0.358** |
| 0.199 | 1412 | 0.287 | 0.333 | **0.341** |
| 0.100 | 706 | 0.282 | 0.331 | **0.338** |
| 0.050 | 357 | 0.278 | **0.338** | 0.319 |
| 0.020 | 140 | 0.249 | 0.312 | **0.314** |
| 0.011 | 76 | 0.305 | 0.302 | **0.322** |

`take_mean` (one caption per take, 40 decodes in all): **0.284**.

- **Against plain uniform** adaptive wins 7/8 budgets, and CIDEr rose 25× overall
  (0.012 → ~0.33) from training in-domain (partly same-session familiarity; see
  the caveat above). Anchored on plain uniform's best score (0.310 at 3537
  decodes), adaptive matches it at 0.050 Hz with 357 decodes — the **≈9.9×** this
  document used to headline.
- **Against uniform+pool the advantage disappears.** Pooling alone lifts uniform
  by +5% to +26% at every budget; uniform+pool is higher than adaptive at 6/8
  budgets, and its best score (0.358 at 2357 decodes) exceeds adaptive's best
  anywhere (0.348), so no efficiency multiple survives. Per take (below): tied at
  6/8, adaptive significantly better at 0.05 Hz, significantly worse at 0.35 Hz.
- **The benchmark barely rewards timing.** One caption per take (0.284) scores
  about what plain uniform gets with 1,412 decodes (0.287 at 0.2 Hz).

Same-takes control (2026-09-20): on exactly these 40 takes the ground-truth stream
favours uniform at 7/8 budgets (adaptive edges it only at 0.20 Hz, 2.381 vs 2.352;
all from the 218-take run's decode cache), so the reversal against *plain* uniform
belongs to the stream, not to the take sample — but what the predicted stream
rewards is averaging its noise, which uniform+pool does as well.

### Controls — why the original three missed it

The three controls below were designed against an earlier out-of-domain artifact
and repeated in-domain. Each compared adaptive with an **unpooled** baseline:

| control | out-of-domain (rejected) | in-domain, as published | **in-domain, matched (2026-11-17)** |
|---|---|---|---|
| metric responds to timing (nearest − shuffled alignment) | +0.0012 (blind) | +0.0225…+0.0284 | unchanged — a metric property |
| advantage with mean-pooling disabled | +0.0051 | +0.031…+0.040 (flat) | **−0.0025…+0.0028** once uniform gets the same 3-step smoothing |
| adaptive vs random placement | — | 8/8 wins | random points were unpooled too |

The decisive one is the second. Disabling pooling left the 3-step pre-smoothing on
the *adaptive* stream only, so each "exact" adaptive point was still a three-step
average; the flat margin we read as "pure temporal selection" was the smoothing.
Removing the smoothing altogether does not rescue placement: adaptive then trails
uniform+pool on the semantic metric at all 8 budgets (−0.009 to −0.016;
`results_egoexo_predictor_40_indomain_semantic_pooled_smooth1.json`).

Against plain uniform, the result is robust to the smoothing (2026-09-20): with
`smoothing_window: 1` adaptive still leads uniform at 8/8 budgets on the semantic
metric (+0.013 at 1 Hz rising to +0.102), wins the same 7/8 on CIDEr, and the
9.9× cell is unchanged (0.3379 vs 0.3378).

### Statistical significance — paired bootstrap over takes (`results_egoexo_rigor_pooled.json`)

Per-take scores, **paired** differences (adaptive − baseline), 5,000 resamples;
bold = 95% CI excludes zero; brackets = takes favouring adaptive, of 40:

| target Hz | vs uniform: semantic | vs uniform: CIDEr | vs uniform+pool: semantic | vs uniform+pool: CIDEr |
|---:|---:|---:|---:|---:|
| 1.00 | **+0.0397** (40) | **+0.0193** (26) | **−0.0013** (12) | −0.0055 (21) |
| 0.50 | **+0.0419** (40) | **+0.0212** (26) | **−0.0017** (12) | −0.0004 (24) |
| 0.35 | **+0.0484** (40) | **+0.0255** (28) | **−0.0027** (7) | **−0.0113** (11) |
| 0.20 | **+0.0523** (40) | **+0.0263** (23) | **−0.0043** (3) | −0.0026 (15) |
| 0.10 | **+0.0675** (40) | **+0.0300** (28) | **−0.0070** (2) | −0.0062 (21) |
| 0.05 | **+0.0776** (39) | **+0.0279** (27) | **−0.0066** (5) | **+0.0143** (29) |
| 0.02 | **+0.1057** (40) | **+0.0365** (27) | **−0.0099** (5) | −0.0035 (13) |
| 0.01 | **+0.1057** (40) | −0.0017 (19) | **−0.0111** (1) | −0.0076 (9) |

Against plain uniform: significant at 8/8 on the semantic metric and 7/8 on CIDEr
(the 0.011 Hz cell is null; the two metrics disagree in direction there). Against
uniform+pool: the semantic metric favours uniform+pool significantly at **all 8**;
CIDEr is tied at 6/8, with one significant win each way (0.05 Hz: +0.0143
[+0.0057, +0.0229]; 0.35 Hz: −0.0113 [−0.0203, −0.0024]). CIDEr has much lower
power than the semantic metric (n-gram overlap over ~100 events is noisy).

*(Per-take CIDEr values (~0.15–0.20) are numerically lower than the corpus CIDEr
above (~0.28–0.36) because TF-IDF is computed within a single take rather than
across the corpus; only the paired differences are interpreted here.)*
```bash
python scripts/eval_rigor.py --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 \
    --methods uniform,adaptive,uniform_pool,take_mean --boot 5000 \
    --out results_egoexo_rigor_pooled
```

### Headroom — what the ceiling analysis can and cannot show (`results_egoexo_ceiling.json`)

Semantic metric, 40 takes, per-take means with 95% bootstrap CIs:

| reference | what it is | score (95% CI) | % of ceiling |
|---|---|---|---:|
| uniform @0.05 Hz | single raw step per decode | 0.5949 [0.5740, 0.6167] | 77.1% |
| **dense** | decode **every** timestep (2 Hz), no pooling | 0.6037 [0.5854, 0.6243] | 78.2% |
| GT-boundary | segment the **ground-truth caption** stream, pool the predicted stream over those spans | 0.6684 [0.6522, 0.6851] | 86.6% |
| adaptive @0.05 Hz | Ward segments, pooled | 0.6725 [0.6560, 0.6898] | 87.1% |
| uniform+pool @0.05 Hz | fixed blocks, pooled | 0.6791 [0.6626, 0.6963] | 88.0% |
| **take_mean** | ONE decode per take, the whole stream's mean | 0.6950 [0.6791, 0.7117] | **90.0%** |
| best-frame ceiling | max over *all* timesteps of cos(stream[j], gt) | 0.7541 [0.7396, 0.7692] | 97.7% |
| **best-window ceiling** | max over *all* contiguous ranges of cos(mean(stream[a:b]), gt) — bounds every row above | **0.7720** [0.7577, 0.7867] | 100% |

1. **Pooling beats decoding more.** Single-point decoding is flat in rate — uniform
   0.5949 (0.05 Hz) → 0.6054 (0.5 Hz) → 0.6037 (dense, 2 Hz) — while every pooled
   schedule beats decode-everything at a fraction of the cost. On a noisy predicted
   stream, averaging before decoding gives a *better* answer, not just a cheaper
   one (the +0.018 best-window over best-frame gap says the same).
2. **Where the boundaries fall barely matters.** Ward (0.6725), the annotators'
   boundaries (0.6684) and fixed blocks (0.6791) are within 0.011 of one another.
3. **The bound cannot rank triggers (corrected 2026-11-17).** This section used to
   read adaptive's 87.1% as a near-exhausted trigger, "so the remaining headroom is
   the predictor". A policy with **no trigger at all** — one mean per take —
   reaches 90.0%, above every adaptive budget: EgoExo takes are repetitive enough
   that a take-level summary sits close to most captions. The semantic metric
   rewards averaging in itself; it compares schedules at matched pooling, but it
   cannot certify a trigger.

With the default pre-smoothing the pooled schedules average the *smoothed* stream;
the smoothed-stream ceiling is 0.7661 and the per-annotation union of both is
0.7721 (vs 0.7720), so the raw-stream figure still bounds every row (2026-09-20).

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
python scripts/make_thesis_figures.py --rigor results_egoexo_rigor_pooled.json
```

### Honest caveats
- The 0.011 Hz row (~2 decodes/take) is a degenerate low-n regime and plain
  uniform's curve is visibly non-monotonic there.
- Absolute CIDEr is low (~0.33): predicting free-form egocentric narration is
  hard, and our predictor saw 11.5k samples.
- **The non-replication is specific to our reconstruction.** Our predictor (29.9M,
  in-domain) and embedding space (SONAR) differ from VL-JEPA's (490M, Action100M,
  its own space); a predictor with crisper semantic structure might restore a
  placement advantage at matched pooling. The paper does not say over what window
  its uniform baseline pools; ours (one decode interval around each point) is one
  reasonable choice.

**What this does to the §5 paradox.** On a raw annotation stream (~1 event / 2 s)
there is no redundancy and uniform placement wins. On the predicted stream the
reversal against *plain* uniform is real, but it is not evidence that the
predictor creates segmentable plateaus: the predicted stream is *noisy*, and
averaging that noise before decoding is the active ingredient — fixed blocks
capture it as well as Ward segments. Selective decoding's placement advantage is a
clean-stream, redundant-stream phenomenon in this reconstruction.
```bash
python scripts/build_egoexo_cache.py --max-per-take 20 --max-samples 12000
python -m livejepa.train --config configs/default.yaml --data-root data_cache_egoexo \
    --ckpt-dir checkpoints_egoexo --max-steps 20000 --batch-size 32
python -m livejepa.run_eval --dataset egoexo --mode predictor \
    --ckpt checkpoints_egoexo/predictor_20000.pt --gt-source atomic \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 \
    --methods uniform,adaptive,uniform_pool,take_mean \
    --decode-cache eval_data/decode_cache_egoexo_indomain.jsonl \
    --out results_egoexo_predictor_40_indomain_pooled
python scripts/eval_semantic_pareto.py --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 \
    --methods uniform,adaptive,random,uniform_pool --out <name>   # + --pool none
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
| C1-final | 26,360 COIN | **0.897** | **0.846** | 0.386 |
| C1-mid | 5,529 COIN | 0.883 | 0.733 | **0.401** |
| C2 | 6,710 A100M | 0.359 | 0.392 | 0.348 |
| **C3 combined** | 33,573 (both) | 0.875 | 0.824 | 0.390 |

(COIN-956 = the 956 val files that predate the 2026-07-19 late merge; C3's earlier
0.823 was measured on the 977-file directory. Re-derived 2026-09-20.)

**Adding 25% more clips made the model slightly worse** (−0.022 on both
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
in general — VL-JEPA trained on the full 1.2M-video corpus, where each
open-vocabulary target is far better covered. The honest claim is narrow and
useful: *at small scale, a low-entropy closed target vocabulary beats an
open-vocabulary one, even on the open corpus's own benchmark.*
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
- **The predicted-stream comparison is 40 takes, not 218** (§5b) — the frozen
  218-take pool exists and the protocol is unchanged, but a full re-run costs
  ~84 h on the T1000. The paired bootstrap (§5b) separates the schedules where
  they differ; more takes would tighten the ties between adaptive and
  uniform+pool.
- **Rung C2 — DONE (§6)**, with a negative result: Action100M-preview at 6.7k
  clips underperforms COIN at matched scale. A fair *scale-up* test (50–100k
  A100M clips) remains open; the right tool is **Kaggle** (free, fresh IP per
  session — a single pod IP throttles after ~200 videos), not another rental.
  The extracted A100M cache is kept locally, so combined COIN+A100M training is
  now free to try on the T1000.
- **Predictor-mode EgoExo eval on the 40-take subset — DONE (§5b), corrected
  2026-11-17.** Against single-point uniform, adaptive wins 7/8 budgets
  (significant 8/8 semantic, 7/8 CIDEr). Against uniform with the same pooling —
  the paper's own protocol — it ties at 6/8 with one significant win each way, and
  the best score belongs to pooled uniform: the gain on a predicted stream is
  averaging, not placement.
- **Ceiling analysis — DONE (§5b), reinterpreted 2026-11-17.** One decode per
  take reaches 90.0% of the bound (adaptive 87.1%), so the bound measures how well
  pooled summaries match captions and cannot certify the trigger. The case that
  the predictor is the lever now rests on the 25× in-domain gain and the scaling
  curve (§4), not on the ceiling.
- **Open: an evaluation that rewards timing.** On EgoExo atomic descriptions one
  caption per take scores CIDEr 0.284, about what uniform gets with 1,412 decodes;
  a protocol that scores only take-atypical annotations, or reports every schedule
  against that one-caption reference, would let placement show its value.
- **Real-time** — V-JEPA 2 is ~11 s/window on the local T1000; the demo is not
  real-time on this hardware. A faster GPU (e.g. a T4) or a lighter encoder helps.
- **Web UI + backend — DONE** (2026-07): `webapp/` FastAPI backend + product UI
  deployed and tunnel-verified, serving the final checkpoint, with an
  architecture/results page at `/about`. An **optional pretrained-VLM variant**
  and the **LiveCC-7B baseline** remain deliberate, deferred follow-ups.

*Reproducibility:* `project.use_stubs: false` in `configs/default.yaml`; models
cached in `~/.cache/huggingface/hub`; SONAR via the transformers backend (Windows).
