# LiveJEPA — Status & Next Steps

> **⚠️ SUPERSEDED as a status document (2026-08-02).** Every experiment and the
> thesis packaging are complete; the only remaining work is format conversion
> into the institute's template (`thesis_materials/BUILD.md`). The "next steps"
> below are historical. For current state read **`HANDOFF.md`** (which carries a
> 2026-08-02 update block), then the newest **`WORKLOG.md`** entry. Results are
> in **`RESULTS.md`**. This file is kept for the reasoning it records at the time
> — useful for a methodology chapter, not for knowing what to do next.

*Working assessment first written 2026-06-16; phase table last updated
**2026-07-22** after the full-COIN data-scaling study (rung C1) and the
paper-protocol EgoExo4D atomic eval (D.1). Read alongside `PROJECT_CONTEXT.md`
(the why), `LiveJEPA_Master_Project_Plan.md` (the spine), and the approved ideal
route in `HANDOFF.md` (state) / `WORKLOG.md` (daily log). All current numbers +
reproduce commands live in `RESULTS.md`.*

---

## 1. Where the project actually stands

| Phase | Status | Evidence |
|---|---|---|
| 0 — Component sanity | ✅ Done | V-JEPA 2, SONAR encoder+decoder downloaded; SONAR round-trip **exact**. Live webcam *capture* not run (no camera on the remote/institute box) |
| 1 — Selective decoding | ✅ Done | `selective/{offline,online,pooling}.py` + unit tests. **Dominance validated on clean GT/keystep streams** (COIN ~1.6×, EgoExo4D keysteps ~2.5×; `RESULTS.md` §1) with a documented low-freq crossover — not strict full-range Pareto |
| 2 — Predictor | ✅ Done + **scaled** | Data-scaling study (rung C1): full-COIN cache (26,360 clips, 99.6% of the training split) lifts held-out **cos 0.667 → 0.846** on a fixed 956-sample diverse val across 9× data, curve still climbing, not collapsed (pred–pred 0.408). `checkpoints_c1_final/predictor_30000.pt` (`RESULTS.md` §4) |
| 3 — Evaluate & ablate | ✅ Done | Time-aligned CIDEr + freq sweep + ablations + predictor-in-the-loop Pareto + trigger-tuning sweep + **paper-protocol EgoExo4D atomic at full 218-take scale (D.1)**. Honest finding: adaptive dominance scales with **temporal redundancy** — wins on keysteps (~2.5×), loses on hyper-dense atomic (uniform wins every rate; `RESULTS.md` §5), attenuates on the noisy predicted stream. Final-ckpt full-system Pareto + LiveCC baseline pending |
| 4 — Package/demo | ✅ Done | `demo.py` E2E + polished; **web UI + backend deployed** (`webapp/`, FastAPI + product UI + `/about` architecture page, tunnel-verified, serving the final checkpoint). Remaining: optional pretrained-VLM variant, thesis writeup |

**Environment:** local **NVIDIA T1000 8 GB**, Python 3.14, torch 2.10+cu126,
transformers 5.10. SONAR runs via the **transformers** backend (fairseq2 is
Linux-only). Heavy training is intended for **Kaggle/Colab free GPU**
(`notebooks/kaggle_colab_training.ipynb`).

---

## 2. The two issues found in Phase 2 — and what was done

### Issue A — SONAR native-scale mismatch (FIXED)
The predictor is trained with **scale-invariant** losses (InfoNCE + cosine), so
it learns embedding *direction* but not magnitude. Measured:

- cached SONAR target norms: **mean 0.196**, range 0.165–0.239
- raw predictor output norm: **~30** (≈150× too large)

The SONAR decoder **rejects off-scale vectors and emits empty strings** — so
decoding raw predictor output produced nothing. Rescaling each prediction to
the native norm (~0.196) produces real, grammatical captions.

**Fix:** `livejepa/predictor/infer.py` → `rescale_to_native()` +
`load_predictor()` (one callable used by both the demo and the evaluator);
`encoders.sonar.native_norm` added to `configs/default.yaml`.

### Issue B — Predictor: corrected diagnosis (2026-06-18)
An earlier note here claimed the predictor was "badly undertrained (val cos
0.425, captions wrong)". **That was a measurement artifact and is retracted.**
Two confounds, both now verified:
1. **Domain mismatch.** The 0.425 was measured on a val cache that mixed in
   *cooking* captions ("add raw materials") which the (sports-dominated) training
   set never contained — so of course a sports-trained model mis-mapped them. On
   in-distribution captions the predictor is fine.
2. **Train/val leakage in the old setup.** `predictor_1000` was trained on
   `data_cache/`, which overlaps **6 of 7** videos and **all 26 captions** with
   the old val — so its high val cosine was memorization, not generalization.

A clean, **leakage-free** retrain (`scripts/build_coin_cache.py` splits videos by
class; `data_cache_coin2{,_val}`) gives the first honest number: held-out video
**cos ≈ 0.81**, captions mostly correct with some garbling on harder steps
(`scripts/eval_predictor.py`). So the predictor **generalizes reasonably within
its trained action vocabulary**; the real limit is **vocabulary breadth** (only
11 classes / 41 captions available locally), not training quality. Captioning new
domains needs those classes in training → more diverse data (§5, the Kaggle
track). `predictor_1000.pt` remains the working checkpoint (trained on more,
full-step clips); `checkpoints_coin2/` is the leakage-free-measured variant.

None of this affects the thesis claim — the dominance relationship (§3) is
independent of absolute caption quality.

---

## 3. The headline result (real data)

`livejepa/run_eval.py` is the missing glue: it turns a video into a stream of
predicted SONAR embeddings, runs adaptive vs. uniform decoding across a
frequency sweep, decodes with SONAR, and scores **time-aligned CIDEr** against
the ground-truth annotations (the paper's protocol, not whole-video CIDEr).

Two stream modes:
- **`gt`** — SONAR embeddings of the GT captions over time. Isolates the
  selective mechanism on a clean signal (Phase 1 validation on real data).
- **`predictor`** — V-JEPA 2 → trained predictor → rescale (the full system).

**COIN, gt mode — adaptive Pareto-dominates uniform** (see
`results_coin_gt.png` / `.json`):

**COIN val (26 videos, 664 atomic steps), gt-mode clean signal — time-aligned CIDEr-D:**

| target Hz | uniform | adaptive | Δ |
|---:|---:|---:|---:|
| 1.00 | 8.81 | 8.81 | 0 (both decode ~all) |
| 0.50 | 8.47 | **8.79** | +0.32 |
| 0.35 | 7.92 | **8.68** | +0.76 |
| 0.20 | 6.83 | **7.72** | +0.89 |
| 0.10 | 4.94 | **5.27** | +0.33 |
| 0.05 | 3.77 | 3.53 | −0.24 |
| 0.02 | 3.55 | 2.29 | −1.26 |

Adaptive **Pareto-dominates uniform across the operationally useful band
(~0.1–0.5 Hz)**: it holds CIDEr ≈ 7.7 at 0.20 Hz, which uniform only reaches
near ~0.31 Hz → **≈1.6× fewer decodes at equal quality**. At very low
frequencies (≤0.05 Hz, ~1 decode per 5-min video) the segmenter has too few
points and uniform's even spacing wins — an honest limit at extreme sparsity.
(The paper reports ~2.85× on EgoExo4D with their encoder/decoder; we reproduce
the *shape and direction*, not the magnitude, by design — different embedding
space and dataset.) With ~50% injected noise (`--gt-noise 0.003`) the advantage
narrows but the mid-band ordering holds, and average-pooling's denoising is what
preserves it — motivating the pooling ablation in §4.

The gain comes from two things the paper highlights: adaptive decode points land
on segment boundaries (uniform misses short events), and average-pooling each
segment **denoises** the embedding before decoding.

**EgoExo4D — the paper's own benchmark** (`results_egoexo_keystep.png` / `.json`).
Real val ground truth loaded: 786 takes of atomic descriptions, 182 of keysteps.
A key finding on *granularity*: the paper's **atomic descriptions are very dense**
(~89/take, ~1 every 2 s) → a clean stream built from them has no temporally-stable
structure for the segmenter to exploit, so adaptive shows little/no gain there.
The **keystep** annotations (~27/take, ~1 every 15 s — coarse, stable, like COIN
steps) are the right structure, and there adaptive cleanly dominates:

| target Hz | uniform | adaptive | Δ |
|---:|---:|---:|---:|
| 0.50 | 8.20 | 8.20 | 0 |
| 0.35 | 8.12 | **8.20** | +0.08 |
| 0.20 | 7.75 | **8.20** | +0.45 |
| 0.10 | 6.54 | **7.38** | +0.84 |
| 0.05 | 4.70 | 4.16 | −0.54 |

Adaptive holds its CIDEr ≈ 8.20 plateau down to **0.20 Hz**, which uniform reaches
only near **0.50 Hz** → **~2.5× fewer decodes at equal quality** (10 val takes),
close to the paper's headline 2.85×. Same honest crossover below ~0.06 Hz. The
takeaway: selective decoding's advantage requires temporally-stable meaning —
which keysteps (and a smooth *predicted* stream) provide, but raw dense atomic
annotations do not.

### How to reproduce
```bash
# clean-signal mechanism check on real COIN annotations (fast)
python -m livejepa.run_eval --dataset coin --mode gt --gt-noise 0.003

# full system (V-JEPA 2 + predictor) on a few videos (heavier; streams cached)
python -m livejepa.run_eval --dataset coin --mode predictor \
       --ckpt checkpoints/predictor_1000.pt --max-videos 3 --max-seconds 120

# EgoExo4D, the paper's benchmark — gt mode on coarse keysteps (no video needed).
# First fetch annotations (needs the ~/.aws/credentials profile from the portal):
#   egoexo -o ./eval_data/egoexo --parts annotations metadata --benchmarks keystep --splits val -y
python -m livejepa.run_eval --dataset egoexo --mode gt --gt-source keystep \
       --max-videos 10 --max-seconds 300

# predictor mode on EgoExo4D needs a few takes' video (448p is 438 GB for ALL —
# fetch only by uid): egoexo -o ./eval_data/egoexo --parts downscaled_takes/448 --uids <uid1> <uid2> -y
python -m livejepa.run_eval --dataset egoexo --mode predictor --ckpt checkpoints/predictor_XXXX.pt
```
Outputs: `results_<dataset>_<mode>.png` (Pareto plot) + `.json` (numbers).
Predictor-mode streams are cached under `eval_data/streams/`.

---

## 4. Ablations (Phase 3)

Run on **EgoExo4D val keysteps** (6 takes, light stream noise ≈ 0.001) via
`livejepa/run_eval.py` — same clean-stream protocol as the §3 keystep Pareto.
Numbers in `results_ablations.json`. Each row below is a thesis subsection.

**(a) Method — offline Ward vs uniform vs online (naive vs corrected).** Adaptive
beats uniform in the operational mid-band and **loses at extreme sparsity** (the
same crossover as §3). The **naive** online `VarianceTrigger` is an honest
**negative** result — it decodes a boundary-straddling *window* mean at the
trigger time and does *not* track offline Ward. The **corrected** `SegmentTrigger`
(WS3, 2026‑07‑07 — accumulates the whole segment and emits the *previous
segment's* mean at its *midpoint*, one-window latency) **recovers offline-level
quality**. Plot: `results_ablation_methods.png`.

| avg Hz | uniform | adaptive (Ward) | online (naive) | online_seg (corrected) |
|---:|---:|---:|---:|---:|
| ~0.33 | 7.75 | **7.97** | — | — |
| ~0.20 | 7.18 | **7.95** | — | — |
| ~0.10 | 6.06 | 6.72 | 3.5–4.3 | **7.2–7.7** |
| ~0.05 | **4.23** | 3.55 | — | 6.14 |

So the real-time trigger, done right, reaches **~7.2–7.7 CIDEr at ~0.1 Hz** —
matching (here edging out) offline Ward's 6.72 — vs the naive trigger's ~3.5. The
gap was an *emission* bug, not a fundamental limit of streaming; `SegmentTrigger`
in `livejepa/selective/online.py` (unit-tested, `tests/test_selective.py`) is the
deployable real-time path. "Naive vs. corrected online realization" is itself a
thesis subsection.

**(b) Pooling — segment-mean vs exact-midpoint embedding.** Mean-pooling
**denoises** and helps at 0.2–0.35 Hz (**+~0.18** CIDEr, e.g. 7.95 vs 7.77 @0.20 Hz),
but **hurts at 0.1 Hz** (6.72 vs 6.94) — there segments are coarse and averaging
blends multiple keysteps. So pooling is a mid-band win, not universal.

**(c) Online W × τ sweep.** Window **W = 8 is the sweet spot** (~3.79 CIDEr @0.118 Hz);
**W = 16 fires more** (up to ~0.23 Hz) but **quality drops** (~2.1–2.5 CIDEr);
threshold τ has only a modest effect. Consistent with (a): even tuned, online
trails offline.

**(d) Stream smoothing (moving-average window 1/3/5 @~0.20 Hz).** **Hurts here**
(7.95 → 7.55 → 7.50): at keystep granularity smoothing blurs boundaries more
than it denoises, so the segmenter lands worse decode points.

*Caveat:* these use **clean keystep streams** (the Phase-1 mechanism regime),
not the predictor-in-the-loop deliverable — see §3 and §6.

---

## 5. Next steps, in priority order (2026-07-22, following the ideal-route plan)

Rung C1 (retrain predictor on full COIN) and the demo are **done** (§4 table,
`RESULTS.md` §4). What remains, per `HANDOFF.md` / plan Phases D–E:

1. **Full-system Pareto with the final checkpoint** (local T1000, next). Re-run
   `run_eval --dataset coin --mode predictor --ckpt checkpoints_c1_final/predictor_30000.pt --coin-split val`
   on 30–50 held-out videos. Tests plan Phase D.3: does the better-trained,
   less-noisy predicted stream recover adaptive's mid-band advantage that the
   old cos-0.636 checkpoint lost? The headline full-system deliverable.
2. **Rung C2 — Action100M on a rented 4090** (weekend, ~₹800–1,500; user
   approved). Train on the paper's own data distribution; the still-climbing
   scaling curve (`RESULTS.md` §4) justifies the spend. Bundle the predictor-mode
   EgoExo eval on the 40-take subset — the open question from the atomic D.1
   negative (`RESULTS.md` §5): does a denoised predicted stream beat uniform on
   atomic content where the clean gt-stream cannot?
3. **Thesis writeup** — `docs/THESIS.md` updated with the scaling study and the
   D.1 boundary result; consolidate `thesis_materials/`.
4. **Optional / deferred:** LiveCC-7B token-generative baseline (qualitative
   only); pretrained-VLM variant; cloud serving tier (Modal) for an
   always-available public demo.

---

## 6. Honesty notes (carry into the thesis)
- VL-JEPA is unreleased — this is a **reconstruction**, not a reproduction.
- We use **SONAR** (invertible) instead of EmbeddingGemma (encode-only), so the
  embedding space differs by design; absolute CIDEr will diverge from the paper.
  **The claim is the dominance relationship (adaptive > uniform), not parity.**
- "Pareto-dominates" here means **mid-band** dominance (~0.1–0.5 Hz) with an
  honest **low-frequency crossover** — uniform's even spacing wins at ≤0.05 Hz,
  in both the §3 curves and the §4 method ablation. Not strict full-range Pareto.
- The headline **COIN / EgoExo4D curves (§3) and the ablations (§4) use clean
  GT/keystep streams** — they are the **Phase-1 gate on real data**, i.e. the
  selective *mechanism*, **not** the Phase-3 predictor-in-the-loop deliverable.
  The `predictor`-mode curve reflects the *full system* and is currently limited
  by predictor caption quality (§2B), not by the selective layer.
- The earlier "predictor undertrained (cos 0.425)" claim was **retracted** — it
  was a domain-mismatch + train/val leakage artifact; the honest leakage-free
  number is **cos ≈ 0.81** (§2B).
