# Thesis Tables — ready to format (LaTeX/Word later)

All numbers are real, reproduced results. Sources in parentheses; every source
file is in `figures/`. Copy into the thesis and convert to the required style.

**Refreshed 2026-08-02.** Tables 7–14 are the work from 2026-07-19 onward and did
not exist in the previous version of this file. Section numbers refer to
`docs/THESIS.md`.

---

## Table 1 — Mechanism: adaptive vs uniform, COIN val (gt mode, 26 videos)
Source: `results_coin_gt.json`. Thesis §6.1.

| target Hz | uniform CIDEr | adaptive CIDEr |
|---:|---:|---:|
| 0.50 | 8.47 | 8.79 |
| 0.35 | 7.92 | 8.68 |
| 0.20 | 6.83 | 7.72 |
| 0.10 | 4.94 | 5.27 |

Takeaway: adaptive holds ≈7.7 at 0.20 Hz; uniform reaches it only near 0.31 Hz → **≈1.6× fewer decodes**.

---

## Table 2 — Mechanism: adaptive vs uniform, EgoExo4D val keysteps (10 takes)
Source: `results_egoexo_keystep.json`. Thesis §6.1. (The paper's own benchmark.)

| target Hz | uniform CIDEr | adaptive CIDEr |
|---:|---:|---:|
| 0.50 | 8.20 | 8.20 |
| 0.35 | 8.12 | 8.20 |
| 0.20 | 7.75 | 8.20 |
| 0.10 | 6.54 | 7.38 |
| 0.05 | 4.70 | 4.16 |

Takeaway: adaptive holds the 8.20 plateau to 0.20 Hz vs uniform's ~0.50 Hz → **≈2.5×** (paper: 2.85×). Crossover ≤0.05 Hz.

---

## Table 3 — Online-trigger correction (EgoExo4D keysteps, ~0.10 Hz)
Source: `results_ablations.json`. Thesis §6.2.

| method | CIDEr @0.10 Hz |
|---|---:|
| uniform | 6.06 |
| adaptive (offline Ward) | 6.72 |
| online — naive VarianceTrigger | ~3.5 |
| online — corrected SegmentTrigger | 7.2–7.7 |

Takeaway: the corrected streaming trigger recovers offline-level quality; the real-time path works.

---

## Table 4 — Predictor quality gate, wide retrain (historic; superseded by Table 7)
Source: Kaggle run log / `scripts/eval_predictor.py`. Thesis §6.3a.

| metric | value | reading |
|---|---:|---|
| mean cos(pred, target) | 0.636 | 1,118-sample class-diverse val |
| pred–pred cos | 0.504 | not collapsed |
| (local 137-sample val) cos | 0.772 | easier/smaller val, for reference |

Retained because §6.3b's Pareto was measured on this checkpoint. Table 7 supersedes it as the quality result.

---

## Table 5 — Predictor-in-the-loop Pareto, data scaling on the full system
Source: `results_coin_predictor_c1final.json`, `results_coin_predictor_c1old.json`.
Thesis §6.5. Same 7 leakage-clean held-out COIN videos, identical protocol; the
**only** variable is predictor quality.

| target Hz | old u | old a | **final u** | **final a** | winner |
|---:|---:|---:|---:|---:|:--|
| 1.00 | 2.611 | 2.658 | 5.046 | **5.359** | adaptive |
| 0.50 | 2.644 | 2.561 | **5.388** | 5.009 | uniform |
| 0.35 | 2.856 | 2.492 | **5.072** | 5.043 | uniform (near-tie) |
| 0.20 | 2.960 | 2.388 | **5.129** | 4.909 | uniform |
| 0.10 | 2.124 | 2.348 | 4.057 | **4.486** | adaptive |
| 0.05 | 2.191 | 2.090 | **3.385** | 3.115 | uniform |
| 0.01 | 1.960 | 0.977 | **3.500** | 2.159 | uniform |

Two takeaways: (i) data scaling **≈2×'d** absolute full-system quality (5.0–5.4 vs
2.6–2.9); (ii) the regime-dependent shape is **robust to predictor quality** — the
mid-band uniform advantage tracks COIN's intrinsic ~0.2 Hz step cadence, it is not
a noise artifact. Caveat: N = 7 videos.

---

## Table 6 — Trigger-tuning sweep (does smoothing recover the mid-band? No)
Source: `results_adaptive_tuning.json`. Thesis §6.3. Mid-band mean Δ vs uniform.

| adaptive config | wins/4 | mean Δ vs uniform |
|---|---:|---:|
| smooth=1, ward (baseline) | 2/4 | −0.061 (best) |
| smooth=3, ward | 1/4 | −0.199 |
| smooth=5, ward | 1/4 | −0.262 |
| smooth=7, ward | 1/4 | −0.211 |
| smooth=1, average | 0/4 | −0.269 |
| smooth=3, average | 0/4 | −0.421 |
| smooth=5, average | 0/4 | −0.564 |
| smooth=7, average | 0/4 | −0.542 |

Takeaway: smoothing makes the mid-band *worse*; the un-smoothed baseline is best.
Read together with Table 12: trigger tuning is the wrong lever.

---

## Table 7 — Data-scaling study (the quality lever)
Source: `scripts/eval_predictor.py`. Thesis §6.5. Architecture (29.9M), recipe
(30k steps, InfoNCE + cosine) and **both** validation sets held identical across
rows; only training-data volume grows.

| training clips | source | frozen 137-val cos | **diverse 956-val cos** | pred–pred |
|---:|---|---:|---:|---:|
| 2,962 | COIN, 3 vids × 180 classes | 0.772 | 0.667 | 0.527 |
| 5,529 | COIN, first fleet sessions | 0.883 | 0.733 | 0.467 |
| **26,360** | **COIN, 99.6% of full train split** | **0.897** | **0.846** | **0.408** |

Takeaway: **+0.113 cos on the last 4.8× of data and still climbing** — data, not
architecture, was the binding constraint. Predictions grew *more* diverse
(0.527 → 0.408), ruling out collapse. 7/10 frozen-val decodes are verbatim.

---

## Table 8 — Paper-protocol EgoExo4D, atomic descriptions, **clean GT stream**
Source: `results_egoexo_atomic_218.json`. Thesis §6.7. 218 density-matched val
takes, `--max-seconds 360`, 59.4k unique SONAR decodes.

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

Takeaway (**the negative**): uniform wins at **every** frequency. Atomic
descriptions carry an event ~every 2 s, so the raw stream has no temporal
redundancy to exploit. Contrast Table 2 (keysteps, ~1 event / 15 s, adaptive wins
2.5×). Unifying claim: *selective decoding's benefit is a monotone function of the
stream's temporal redundancy.*

---

## Table 9 — Same benchmark, **predicted stream**, in-domain predictor ★ HEADLINE
Source: `results_egoexo_predictor_40_indomain.json`. Thesis §6.8. 40 held-out
takes (excluded from predictor training), `--max-seconds 360`. Predictor gate:
cos **0.599**, pred–pred 0.325 on 25 further held-out takes.

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

Takeaway: adaptive wins **7/8**; absolute CIDEr rose **25×** (0.012 → ~0.33)
purely from fixing the domain. In the paper's reporting form: best uniform
anywhere = 0.310 (0.499 Hz, 3537 decodes); adaptive reaches 0.338 at 0.050 Hz on
**357** decodes → **≈9.9× fewer decoder invocations at equal-or-better quality**
(paper: 2.85×). Caveat: the 0.011 Hz row is a degenerate ~2-decodes/take regime
where uniform is non-monotonic; a 25.3× figure is computable there and is *not*
quoted.

---

## Table 10 — Controls: why Table 9 is trusted and the earlier attempt was not
Source: `results_egoexo_predictor_40_indomain_semantic{,_nopool}.json` vs
`results_egoexo_predictor_40_semantic{,_nopool}.json`. Thesis §6.8.

| control | out-of-domain (REJECTED) | in-domain (accepted) |
|---|---|---|
| metric responds to timing (nearest vs random alignment) | +0.0012 — effectively blind | **+0.0225 … +0.0284** |
| survives pooling removal | +0.0051 (58% was denoising) | **+0.0345** (53% survives) |
| beats random placement | — | **8/8 budgets** |

Without pooling adaptive's lead is a **flat +0.031 … +0.040 at every frequency**
(pure temporal selection). **Uniform ≈ random placement (0.605 vs 0.606)** — the
gain comes from *where* decodes land, not from spreading them evenly.

---

## Table 11 — Statistical significance: paired bootstrap over 40 takes
Source: `results_egoexo_rigor.json`, figure `results_egoexo_rigor.png`. Thesis
§6.9. Per-take scores, 5,000 resamples of the **paired** difference (both methods
see the identical take, so take-difficulty variance cancels).

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

Takeaway: significant at **8/8** budgets on the semantic metric and **7/8** on
CIDEr; the sole exception is the degenerate 0.011 Hz point. The semantic metric
has far higher power (40/40 vs 23–28/40 takes) because n-gram overlap over ~100
events is high-variance while cosine is smooth — an argument for reporting both.
*(Per-take CIDEr ≈0.15–0.20 is numerically below the corpus CIDEr of Table 9
because TF-IDF is computed within a take; only paired differences are interpreted.)*

---

## Table 12 — Headroom: how much is left for the trigger?
Source: `results_egoexo_ceiling.json`, `results_egoexo_rigor_oracle_fixed.json`;
figure `results_egoexo_ceiling.png`. Thesis §6.9. Same 40 takes, semantic metric.

| reference | what it is | score (95% CI) | % of ceiling |
|---|---|---|---:|
| uniform @0.05 Hz | budget-matched baseline | 0.5949 [0.5740, 0.6167] | 77.1% |
| **dense** | decode **every** timestep (2 Hz) — infinite budget, no selection | 0.6037 [0.5854, 0.6243] | 78.2% |
| GT-boundary | segment the *ground-truth caption* stream, decode the predicted stream there | 0.6684 [0.6522, 0.6851] | 86.6% |
| **adaptive @0.05 Hz** | ours | **0.6725** [0.6560, 0.6898] | **87.1%** |
| best-frame ceiling | max over all timesteps of cos(stream[j], gt) | 0.7541 [0.7396, 0.7692] | 97.7% |
| **best-window ceiling** | max over all contiguous ranges of cos(mean(stream[a:b]), gt) — upper-bounds every row | **0.7720** [0.7577, 0.7867] | 100% |

Three takeaways:

1. **Decoding more does not help.** Uniform is flat in decode rate: 0.5949
   (0.05 Hz) → 0.6054 (0.5 Hz) → 0.6037 (dense). **Adaptive at 0.05 Hz beats
   decode-everything** at ~40× fewer decoder calls — here selective decoding is not
   a quality/compute trade-off but a strict improvement. Pooling denoises: the
   best-*window* ceiling sits +0.018 above the best-*frame* ceiling.
2. **Perfect boundary knowledge is not the missing piece.** A trigger handed the
   annotators' own boundaries scores at/below adaptive, because annotation
   boundaries are homogeneous in *caption* space while adaptive's are homogeneous
   in *predictor* space. Timing has little left to give.
3. **The residue is representational.** 87.1% of a bound no real schedule can
   reach (each annotation may pick its own window, under no budget), so 87% is a
   *conservative* reading. The remaining gap belongs to the **predictor** — which
   is why Table 6's trigger tuning failed and Table 7's still-climbing curve is
   the live lever.

---

## Table 13 — Rung C2/C3: training on the paper's own data (Action100M)
Source: `scripts/eval_predictor.py` on each cache. Thesis §6.6. Rented RTX 4090
(~$8); YouTube throttling capped extraction at 6,710 train + 160 val clips, which
makes C2 a **scale match** to the 5,529-clip COIN rung, not a scale-up.

| model | training data | COIN-137 | COIN-956 | **A100M-160** |
|---|---|---:|---:|---:|
| C1-final | 26,863 COIN | **0.897** | **0.846** | 0.386 |
| C1-mid | 5,529 COIN | 0.883 | 0.733 | **0.401** |
| **C2** | 6,710 A100M | 0.359 | 0.392 | 0.348 |
| C3 combined | 33,573 (both) | 0.875 | 0.823 | 0.390 |

Takeaway (**clean negative**): COIN-trained models beat the Action100M-trained
model **on Action100M's own validation set** (0.401 / 0.386 vs 0.348). The
scale-matched cell is decisive — C1-mid used *fewer* clips and the same 20k steps,
so C2's deficit is not a data-volume artifact. Adding A100M as augmentation (C3)
made things slightly *worse* (−0.022/−0.023 on COIN) and exact frozen-val matches
fell 7/10 → 5/10. **C1-final remains the deployed checkpoint.**

Scope: this tests **Action100M-preview** (the 10% release) at ~6.7k clips. It does
not show Action100M is bad data — VL-JEPA used the full 1.2M-video corpus. The
narrow claim: *at small scale, curated labels beat noisy auto-generated ones, even
on the noisy corpus's own benchmark.*

---

## Table 14 — Why C2 failed: target-vocabulary entropy (not label noise)
Source: cache inspection. Thesis §6.6.

| corpus | clips | unique captions | repeats per caption |
|---|---:|---:|---:|
| COIN | 26,863 | **747** (3%) | **36.0** |
| Action100M | 6,710 | **6,096** (91%) | **1.1** |

COIN is effectively a **closed-set** problem; Action100M is genuinely
**open-vocabulary**, nearly every caption seen once. Manual inspection shows
A100M's captions are largely sensible (only 1% contain narration pronouns), so
"noisy labels" is **not** the story — predicting open-vocabulary sentences from
6.7k one-shot examples is simply a much harder statistical problem.

**Caveat this places on our own headline:** Table 7's scaling result is measured
on a 747-label closed set, so part of what improves is closed-set discrimination
rather than open-ended captioning. A100M's 0.348 and COIN's 0.846 are **not
commensurable** — different tasks wearing the same metric.

---

## Architecture facts (for the Method section)
Source: `configs/default.yaml`.

- **Vision (frozen):** V-JEPA 2 ViT-L (`facebook/vjepa2-vitl-fpc64-256`), 326.0M params, K=16 frames/window, res 256, 1024-dim.
- **Predictor (the only trained part):** transformer, 1024 → hidden 768 → 1024, depth 4, heads 8, dropout 0.1, **29.9M params**.
- **Training:** InfoNCE (temp 0.07) + cosine (weight 1.0), lr 3e-4, wd 0.05, warmup 500, batch 32. C1-final 30k steps; EgoExo in-domain 20k steps.
- **Text (frozen):** SONAR encoder 766.1M / decoder 1,370.6M, embed_dim 1024, **native norm ≈0.196** (the decoder returns empty strings on unit-norm input — predictor output is rescaled), beam 5, `eng_Latn`.
- **Selective (offline):** Ward linkage + temporal connectivity, mean-pool per segment, decode at segment midpoint.
- **Selective (online, SegmentTrigger):** window W=8, **τ=0.15**, min_gap=4.
- **Windowing convention:** K=16 @2 fps (8 s span) timestamped at **window centre** — training windows are centred on the annotation timestamp to match inference.
- **Evaluation:** time-aligned CIDEr-D (each GT annotation matched to the nearest decoded timepoint) plus a style-robust semantic metric (same alignment, SONAR cosine instead of n-gram overlap).
- **Working rate:** 2 fps; V-JEPA 2 ≈11 s/window on the local T1000 (not real-time on that hardware).
