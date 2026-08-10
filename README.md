# LiveJEPA

**Real-time, embedding-driven video captioning that only speaks when something changes.**

A buildable reconstruction of VL-JEPA's *selective decoding* mechanism. Instead of
captioning every frame, LiveJEPA produces a continuous semantic embedding stream and
decodes a caption only when the meaning shifts — ideal for live video (smart glasses,
robots, procedural assistance).

> **Why a reconstruction?** VL-JEPA (arXiv:2512.10942) is not publicly released (no code,
> no weights, as of June 2026). LiveJEPA rebuilds the pipeline from released components
> (frozen V-JEPA 2 + SONAR) and implements the novel selective-decoding layer itself.
> **Start with `HANDOFF.md`** (state, file map, gotchas), then the newest `WORKLOG.md`
> entry. `docs/PROJECT_CONTEXT.md` is the background "why".

## Headline result

Selective decoding's benefit is a **monotone function of the stream's temporal
redundancy**, and it needs a **predicted** stream rather than dense labels. On the
paper's own EgoExo4D atomic-description benchmark, adaptive **loses at every budget**
against raw annotations — but wins **7 of 8 budgets at ≈9.9× fewer decoder calls**
once the same annotations are approached through a predicted stream from an in-domain
predictor. Significant at every budget over 40 held-out takes, and at **87% of a
provable upper bound** — *above* what decoding every single window achieves, at ~40×
lower cost. Full numbers: **`RESULTS.md`**; thesis: **`docs/THESIS.md`**.

---

## Quickstart (no heavy models needed)

The repo ships with **stub fallbacks**: every encoder falls back to deterministic
synthetic embeddings when `project.use_stubs: true` (the default), so you can develop and
test the selective-decoding logic immediately — no GPU, no downloads.

```bash
pip install numpy scipy scikit-learn pyyaml          # minimal core
python -m livejepa.eval_pareto                        # synthetic Pareto smoke test
python -m pytest tests/ -q                            # unit tests for selective decoding
```

`eval_pareto` builds a synthetic 5-event stream and prints CIDEr vs decoding frequency for
both uniform and adaptive decoding — you should see adaptive hold quality at lower frequency.

---

## Going real

1. Install everything: `pip install -r requirements.txt` (use `--break-system-packages`
   on managed machines if needed, or a conda env).
2. Set `project.use_stubs: false` in `configs/default.yaml`.
3. Accept licenses / `huggingface-cli login` for gated models if you use them.
4. Apply for **EgoExo4D** access now (~48h) — it's the evaluation dataset.

### Build order (mirrors the plan) — status as of 2026-08-02: **all phases complete**
- **Phase 0 — sanity ✅:** load V-JEPA 2 + SONAR; confirm round-trips (`scripts/sanity_phase0.py`).
- **Phase 1 — selective decoding ✅:** `livejepa/selective/` implemented + unit-tested
  (13/13); mechanism validated on GT/keystep streams. See **`RESULTS.md` §1**.
- **Phase 2 — train predictor ✅ + scaled:** full-COIN data-scaling study (rung C1) —
  99.6% of the training split (26,360 clips) lifts held-out **cos 0.667 → 0.846**,
  curve still climbing → **`checkpoints_c1_final/predictor_30000.pt`** (**`RESULTS.md` §4**).
  Rungs **C2** (Action100M) and **C3** (combined) are documented *negatives* (**§6**, **§6b**),
  explained by target-vocabulary entropy.
- **Phase 3 — evaluate ✅:** COIN + EgoExo4D sweeps, ablations, tuning sweep,
  paper-protocol atomic at 218-take scale (**§5**), the in-domain predictor headline
  (**§5b**), paired-bootstrap significance and the ceiling/headroom analysis.
- **Phase 4 — demo ✅ + deployed:** headless `demo.py` (`--save-video`) **and** a
  deployed web app (`webapp/`, FastAPI + product UI + `/about`, plus a `/ws_cam`
  live-webcam path) serving the final checkpoint.
- **Phase 5 — packaging ✅:** `thesis_materials/` (14 tables, 20 figures, LaTeX
  conversion + `references.bib` + `BUILD.md`). Remaining work is format conversion
  into the institute's template — see `thesis_materials/BUILD.md`.

---

## Layout

```
livejepa/
  encoders/vision.py    V-JEPA 2 frozen feature extractor (+ stub)
  encoders/sonar.py     SONAR encode/decode — invertible text space (+ stub)
  selective/offline.py  Ward clustering + temporal connectivity  ← contribution
  selective/online.py   variance + segment-emission streaming triggers ← contribution
  selective/pooling.py  smoothing / average pooling
  predictor/model.py    the trainable predictor head
  predictor/infer.py    load ckpt + rescale to SONAR native norm
  predictor/losses.py   InfoNCE + cosine regression
  data/cache.py         pre-extract & cache features
  data/egoexo.py        EgoExo4D loader + time-aligned CIDEr
  train.py              train the predictor
  run_eval.py           real video → embedding stream → Pareto eval driver
  eval_pareto.py        adaptive-vs-uniform sweep helpers (+ synthetic smoke test)
  demo.py               live streaming demo
configs/default.yaml    all hyperparameters
webapp/                 FastAPI backend + product UI + /about + /ws_cam webcam path
scripts/
  eval_rigor.py         per-take scores, paired bootstrap, GT-boundary reference
  eval_ceiling.py       dense / best-frame / best-window upper bounds (no SONAR needed)
  eval_semantic_pareto.py  style-robust semantic metric + controls
  build_egoexo_cache.py    in-domain EgoExo training pairs (windowed as at inference)
  make_thesis_figures.py   the two rigor figures
  md_to_latex.py        docs/THESIS.md -> thesis_materials/thesis_body.tex
  bench_live.py         seconds/window + what the live demo will feel like
docs/                   context, design, status, and THESIS.md (the thesis draft)
thesis_materials/       figures, 14 tables, LaTeX conversion, BUILD.md
RESULTS.md              consolidated results + reproduce commands
HANDOFF.md              start here: state, file map, hard-won gotchas
WORKLOG.md              day-by-day record (newest first)
tests/                  unit tests (run in stub mode) — 13/13
```

## Licenses
V-JEPA 2 (MIT) + SONAR (CC-BY-NC-4.0) → fine for academic/thesis use, not commercial.
For a commercial path, train your own embedding-inversion decoder and skip SONAR.

## Citation context
Built on VL-JEPA (Chen, Shukor et al., 2025), V-JEPA 2 (Assran et al., 2025),
SONAR (Duquenne et al., 2023). See `docs/PROJECT_CONTEXT.md`.
