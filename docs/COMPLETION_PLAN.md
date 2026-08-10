# LiveJEPA — Completion Plan (code-grounded, 2026-07-07)

> **⚠️ FULLY SUPERSEDED (2026-08-02).** WS1–WS5 are all complete, including WS5
> (packaging). Nothing in this file is actionable. Current state: `HANDOFF.md`;
> results: `RESULTS.md`; what's left to do: `thesis_materials/BUILD.md`.
>
> *Earlier note (2026-07-22).* This plan's workstreams WS1–WS5 are complete or
> overtaken by the approved ideal-route plan. WS1 (Kaggle retrain) grew into the
> full-COIN data-scaling study; WS2 (full-system Pareto) and WS3 (online trigger)
> are done; WS4 (demo) shipped as a deployed web app; WS5 (packaging) is in
> progress. **For current state and next steps read `HANDOFF.md` → newest
> `WORKLOG.md` entry → `RESULTS.md`.** Kept for historical context only.

*Written after a full read of the codebase, docs, and results files. This
supersedes §4 ("Next steps") of `STATUS_AND_NEXT_STEPS.md`, which predates the
ablation results and the EgoExo4D keystep run.*

## Context

LiveJEPA reconstructs VL-JEPA's selective-decoding mechanism (arXiv:2512.10942, unreleased) from released components: frozen V-JEPA 2 → small trained predictor → SONAR embedding stream → decode only on semantic change. The thesis claim is the **dominance relationship**: adaptive selective decoding Pareto-dominates uniform-interval decoding on time-aligned CIDEr.

**The core mechanism result is already achieved** (clean gt-mode streams): COIN ≈1.6× fewer decodes at equal quality (`results_coin_gt.json`, 26 videos) and EgoExo4D keysteps ≈2.5× (`results_egoexo_keystep.json`, 10 takes — the paper's benchmark, near its 2.85× headline). Phases 0–1 are done (8/8 tests pass), the eval driver (`livejepa/run_eval.py`) and ablations (`scripts/ablations.py` → `results_ablations.json`) exist and ran.

What's genuinely left, reconciled against what the code and results show today:

1. **Full-system result missing.** The predictor-in-the-loop Pareto ran on only 2 COIN videos with CIDEr ≤ 1.2 (`results_coin_predictor.json`) — not usable. Root cause is predictor vocabulary breadth (11 classes / 41 captions locally; honest held-out cos ≈ 0.81 in-vocabulary), i.e. data-limited, not architecture-limited.
2. **Online trigger gap (found by the ablations, newer than the status doc).** Offline Ward adaptive gets CIDEr ≈ 7.9 at 0.2 Hz; the online variance trigger only ≈ 3.5–3.8 at comparable rates. The docs' own honesty section requires "the online trigger tracks the offline segmentation" — currently it does not. This is the real-time story of the thesis and needs fixing.
3. **Kaggle training track not wired.** `notebooks/kaggle_colab_training.ipynb` cell 5 (`iter_clips`) is a template that raises `NotImplementedError`.
4. **Eval hygiene bug.** `iter_coin_videos` (`livejepa/run_eval.py`) yields ALL downloaded videos — predictor-mode COIN eval would mix training videos into the eval set.
5. Demo polish + docs/repo drift (unused `demo.show_decode_indicator`; README references `notebooks/01–03` and `scripts/download_egoexo_subset.sh` which don't exist).

Environment (fixed constraints): local NVIDIA T1000 8 GB (inference/dev only), Python 3.14, SONAR via **transformers backend** on Windows (fairseq2 is Linux-only); heavy training on **Kaggle/Colab free tier** (~30 GPU-h/wk Kaggle).

---

## Workstream 1 — Retrain the predictor at scale (Kaggle) — *critical path*

Goal: a predictor whose vocabulary covers enough COIN classes that held-out captions are coherent. Target gate: val cos(pred, target) ≥ 0.7 on a **class-diverse** held-out set + mostly-correct decoded captions.

1. **Widen the COIN download strategy.** `scripts/download_coin_subset.py` currently picks the N videos with the most steps (class-concentrated). Add a `--per-class N` mode that samples ~2–3 videos per class across many classes (~150–300 videos at 360p). Keep the existing dense mode as default fallback.
2. **Wire the Kaggle notebook.** Replace the `NotImplementedError` template in `notebooks/kaggle_colab_training.ipynb` with the COIN path reusing existing code: fetch `COIN.json` (URL already in `livejepa/data/coin.py:COIN_ANNOTATIONS_URL`), run `scripts/download_coin_subset.py --per-class`, then `scripts/build_coin_cache.py` (already leakage-free: splits videos by class, resume-friendly). Parameterize its hardcoded `TRAIN_DIR/VAL_DIR/MAX_STEPS_PER_VIDEO` via argparse so the notebook can point at `/kaggle/working`. Save the cache as a Kaggle Dataset so reruns skip extraction.
3. **Train to convergence**: `python -m livejepa.train --data-root <new cache> --ckpt-dir checkpoints_kaggle` with config defaults (20k steps, ckpt every 1000). ⚠️ Do **not** train on the default `train.data_root: ./data_cache` — that's the old leaky cache.
4. **Optional loss upgrade (small, high value):** add a norm-matching term to `livejepa/predictor/losses.py` (e.g. `w_norm * (‖pred‖ − ‖target‖)²`, weight ~0.1) so the predictor learns SONAR's native magnitude and the `rescale_to_native` hack in `livejepa/predictor/infer.py` becomes a no-op safety net. Keep rescale in place regardless.
5. **Gate check locally:** `python scripts/eval_predictor.py --ckpt <best> --val data_cache_coin2_val --decode` → report cos, pred-pred collapse, example captions.

## Workstream 2 — Full-system Pareto (predictor mode) — *the missing thesis result*

1. **Fix eval hygiene first:** give `iter_coin_videos` a split filter (reuse the class-based val split logic from `scripts/build_coin_cache.py`, or accept an explicit `--video-ids` list) so predictor-mode COIN eval uses only held-out videos.
2. **COIN full-system run:** `python -m livejepa.run_eval --dataset coin --mode predictor --ckpt <kaggle ckpt> --max-videos 10 --max-seconds 180`. Streams cache to `eval_data/streams/` so reruns are cheap. T1000 can do this (encode is the slow part; ~10 videos × 3 min is feasible overnight).
3. **EgoExo4D full-system run (paper's benchmark):** pick 5–10 val takes that have keystep annotations (already on disk under `eval_data/egoexo/annotations/`), download their 448p videos by uid (`egoexo -o ./eval_data/egoexo --parts downscaled_takes/448 --uids …`), then `run_eval --dataset egoexo --mode predictor --gt-source keystep` (and `atomic` for completeness). The loader (`livejepa/data/egoexo.py`) is already implemented.
4. **Gate:** adaptive ≥ uniform across the mid-band (~0.1–0.5 Hz) with the *predicted* stream; state the iso-quality speedup. This plus WS1 completes Phase 3 of the master plan.

## Workstream 3 — Close the online-trigger gap (local, parallel to WS1)

Diagnosis from `livejepa/selective/online.py`: when the trigger fires, it decodes the mean of a window that **straddles the event boundary** (mixture of old+new event embeddings) and timestamps it at the trigger time — vs. offline's per-segment mean at the segment midpoint. That plausibly explains 7.9 → 3.7.

1. Add a **segment-emission trigger** variant (new class in `selective/online.py`, keep `VarianceTrigger` unchanged as the paper-faithful baseline): accumulate the current segment's embeddings; when a shift fires, emit the **previous segment's mean** timestamped at that segment's midpoint (retrospective emission, latency = one window), then start a new segment; flush the final segment at stream end.
2. Optionally try adaptive τ (relative to running within-segment variance) and min-gap tuning.
3. Evaluate via `scripts/ablations.py` (add the new variant to the methods comparison). **Gate:** online CIDEr within ~15% of offline adaptive in the mid-band — satisfying the honesty-section requirement, and itself a nice thesis subsection (naive vs. corrected online realization).

## Workstream 4 — Demo polish (Phase 4)

`livejepa/demo.py` is print-only. Add an OpenCV display honoring the existing-but-unused `demo.show_decode_indicator` config: live frame window, current caption overlay, a "decode fired" flash, and a decodes-vs-steps counter (the efficiency argument made visible). Keep a `--no-display` headless path. Use the improved online trigger from WS3 once it lands.

## Workstream 5 — Packaging & thesis

1. **Fix docs/repo drift:** README "Build order" references `notebooks/01/02` and layout references `scripts/download_egoexo_subset.sh` — either add thin versions or update the text to the actual entry points (`scripts/sanity_phase0.py`, `scripts/validate_selective_gt.py`, `run_eval`, the egoexo CLI commands documented in STATUS §3).
2. **Results consolidation:** a `RESULTS.md` (or notebook) collecting the three Pareto plots + ablation tables + the new predictor-mode curves, each with its reproduce command.
3. **Update `docs/STATUS_AND_NEXT_STEPS.md`** after WS1–3 land: new predictor numbers, online-trigger fix, ablation summary (pooling helps mid-band +0.18, smoothing hurts on gt streams, W=8 best for online).
4. **Thesis writeup** per master plan §9 (contributions + honesty section — the language is already drafted in the docs).
5. **Stretch (recommend skipping unless GPU-hours remain):** LiveCC-7B token-generative baseline on Kaggle T4. Not feasible locally on 8 GB; the thesis stands without it (master plan lists it as optional).

---

## Verification

- Unit tests still green: `python -m pytest tests/ -q` (8 tests).
- Mechanism regression: `python -m livejepa.run_eval --dataset coin --mode gt --gt-noise 0.003` reproduces the COIN gt table (adaptive ≥ uniform, 0.1–0.5 Hz).
- WS1 gate: `scripts/eval_predictor.py --ckpt <new> --val data_cache_coin2_val --decode` → cos ≥ 0.7, coherent captions.
- WS2 gate: `results_coin_predictor.json` regenerated on ≥10 held-out videos showing mid-band dominance; same for `results_egoexo_*` predictor mode.
- WS3 gate: rerun `scripts/ablations.py` → new online variant within ~15% of offline adaptive mid-band.
- WS4: run `python -m livejepa.demo --source <video.mp4> --ckpt <new>` and observe captions + indicator firing on scene changes only.

## Risks / constraints

- **Kaggle quota (~30 GPU-h/wk):** caching dominates (~1–2 s/clip on T4); mitigate by saving the feature cache as a Kaggle Dataset (extraction runs once).
- **COIN video rot:** yt-dlp skips deleted/private videos — download more than needed; per-class sampling makes rot less concentrated.
- **EgoExo4D size:** never bulk-download; only per-uid 448p takes (few GB for 5–10 takes).
- **SONAR decode is the runtime bottleneck** in evals — `CachedDecoder` in `run_eval.py` already amortizes it; keep sweeps on shared streams.
- **License:** SONAR CC-BY-NC — fine for the thesis, flag in writeup (already in docs).

## Out of scope

Full VL-JEPA-scale pretraining; matching the paper's absolute CIDEr (dominance *shape* is the claim); fairseq2 backend on Windows; ruptures on py3.14/Windows (no wheel — cite as studied alternative only, `run_ruptures` stays optional).
