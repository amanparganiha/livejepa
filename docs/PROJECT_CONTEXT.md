# PROJECT CONTEXT — LiveJEPA

> Read this first. It explains *what* you are building, *why* it makes sense, the *background* on the research it's based on, and the *findings* from the technical survey that shaped the plan. Hand this file (plus the plan) to any collaborator — or to a Claude Code / Cowork session — before starting work.

---

## 1. The one-paragraph summary

VL-JEPA (Meta FAIR / HKUST, Dec 2025, arXiv:2512.10942) is a vision-language model that, instead of generating text token-by-token like a normal VLM, *predicts a continuous embedding* of the answer and only decodes it to text when needed. Its most original and practical contribution is **selective decoding**: because it emits a continuous semantic embedding stream, it can decode a caption *only when the meaning actually changes*, instead of captioning every frame — ideal for real-time video (smart glasses, robots, live assistance). **VL-JEPA itself is not publicly released** (no code, no weights, as of June 2026). So this project, **LiveJEPA**, *reconstructs* a working version of that pipeline from released components and implements the selective-decoding mechanism ourselves, as deployable software with a reproducible evaluation.

---

## 2. Background: what is a JEPA, and why does VL-JEPA matter?

### 2.1 JEPA in general
A **Joint Embedding Predictive Architecture (JEPA)** learns by predicting the *representation* (embedding) of a target from the representation of a context — not by reconstructing raw pixels or raw tokens. The intuition (Yann LeCun's "world model" program): predicting in an abstract embedding space lets the model focus on meaningful structure and ignore unpredictable surface detail.

The JEPA family so far:
- **I-JEPA** (images, 2023) — predict embeddings of masked image regions.
- **V-JEPA / V-JEPA 2** (video, 2023 / 2025) — predict embeddings of masked spatio-temporal video regions. V-JEPA 2 is a strong self-supervised video encoder; **we use it as our frozen vision backbone.**
- **World-model JEPAs** (DINO-WM, etc.) — freeze an encoder, train an action-conditioned predictor over state embeddings, mostly in narrow domains (mazes, robot pick-and-place).

### 2.2 What VL-JEPA adds
VL-JEPA is the **first JEPA built for general vision-language tasks.** Architecture (4 parts):
1. **X-Encoder** maps visual input → visual embeddings (they use V-JEPA 2 ViT-L).
2. **Predictor** maps (visual embeddings + text query) → a *predicted target embedding* `Ŝ_Y` (they initialize it from Llama-3.2-1B layers).
3. **Y-Encoder** maps the target text → target embedding `S_Y` (they use EmbeddingGemma-300M).
4. **Y-Decoder** (used only at inference) turns a predicted embedding back into text.

Training minimizes distance in *embedding space* (`D(Ŝ_Y, S_Y)`) with an InfoNCE loss — **not** token cross-entropy.

### 2.3 Why this is a good idea (the paper's argument)
- **Simpler learning target.** For one input there are often many valid answers ("the lamp turns off" / "the room goes dark"). In token space these look orthogonal (no shared tokens); in embedding space they map to *nearby* points. The model fits one coherent mode instead of many scattered ones → more sample-efficient.
- **Cheaper.** No heavy autoregressive language-generation head during training → ~50% fewer trainable parameters than the matched VLM, and higher performance under identical data/compute (their controlled comparison, §4.5).
- **Real-time friendly.** A single forward pass yields a semantic embedding (no token-by-token decode). The embedding stream can be monitored continuously and decoded sparsely → **selective decoding**, ~2.85× fewer decode operations at the same quality.
- **Unified.** The same embedding space does open-vocab classification, text-to-video retrieval, *and* discriminative VQA — no architecture change. On their benchmarks VL-JEPA-Base beats CLIP / SigLIP2 / Perception Encoder on average across 8 classification + 8 retrieval datasets, with only 1.6B params.

### 2.4 The mechanism we focus on — selective decoding
The paper's most novel, *implementable* piece, and the heart of LiveJEPA:
- VL-JEPA produces a continuous stream of predicted embeddings `Ŝ_Y`, one per sliding window.
- **Offline / batch method:** partition the embedding stream into segments using **agglomerative clustering with a temporal-connectivity constraint and Ward (variance) linkage**, then decode once per segment at its **midpoint**, from the **average-pooled** segment embedding (pooling denoises).
- **Online / streaming method:** decode only when the **local-window variance** of the embedding stream exceeds a threshold (a semantic shift).
- **Result:** swept across decoding frequencies (2.0 Hz → 0.01 Hz on EgoExo4D, 218 procedural videos, ~6 min each, ~143 atomic-action annotations per video), adaptive selection **Pareto-dominates** uniform-interval decoding. Headline: 0.35 Hz adaptive ≈ 1 Hz uniform → **~2.85× fewer decodes** at equal CIDEr.

---

## 3. What the technical survey found (June 2026) — and how it shaped the plan

A focused survey of released components and tooling produced five decisions:

**Finding 1 — VL-JEPA is unreleased.** No `facebookresearch/VL-JEPA` repo; no `facebook/VL-JEPA` checkpoint. The authors released only the *dataset* infra (`facebookresearch/Action100M`, plus a 10% `facebook/action100m-preview`). A Hugging Face request for the weights (Action100M Issue #3, Jan 2026) is still open. The only third-party "VL-JEPA" repo (`Soumya-Chakraborty/VL-JEPA`) is an unofficial, weight-free scaffold.
→ **Decision:** we *reconstruct*, not reproduce. The project's framing is "first independent, working reconstruction of the selective-decoding mechanism."

**Finding 2 — every component model IS released.**
- V-JEPA 2 ViT-L 256px → `facebook/vjepa2-vitl-fpc64-256` (MIT). Our frozen vision encoder.
- EmbeddingGemma-300M → `google/embeddinggemma-300m` (Gemma license, gated).
- Llama-3.2-1B → `meta-llama/Llama-3.2-1B` (custom license, gated).
- SONAR text encoder+decoder → `facebook/SONAR` (CC-BY-NC-4.0).

**Finding 3 — EmbeddingGemma cannot be inverted to text.** It is encode-only; the paper never specifies its Y-Decoder's architecture or training. This is the single biggest reproduction gap.
→ **Decision:** use **SONAR** as the Y-space instead. SONAR ships *both* an encoder and a trained decoder, so predicted embeddings decode back to text *for free and exactly*. Our predictor learns V-JEPA-2-features → SONAR-embedding. This is what makes the system actually produce captions.

**Finding 4 — selective decoding is fully specified and light to build.** scikit-learn's `AgglomerativeClustering` with a banded connectivity graph gives temporally-constrained Ward clustering in ~20 lines; a deque-based windowed-variance trigger gives the online path; `ruptures` is an optional change-point alternative.
→ **Decision:** build the selective-decoding layer *first*, validated on clean ground-truth-caption embeddings, before training any predictor.

**Finding 5 — full VL-JEPA training is out of scope** (their run: 24×8 H200 for ~4 weeks). But the architecture is modular: freeze the released encoders, train only a small predictor head. That's single-GPU feasible.
→ **Decision:** train only a ~10–50M-param predictor from cached V-JEPA 2 features → SONAR targets, on a COIN / Action100M-preview subset.

**Context — competing streaming systems** (cite & optionally benchmark): VideoLLM-online (learned "streaming EOS" trigger), VideoLLM-MoD (mixture-of-depths efficiency), ProVideLLM (interleaved cache, procedural focus), Streaming Dense Video Captioning (Zhou et al., clustering memory + decoding points), LiveCC-7B (released, Apache-2.0 — our token-generative baseline). VL-JEPA's distinction: it triggers on **semantic shift in a predicted embedding stream**, not via a trained LLM head — and LiveJEPA is the first independent take on that.

---

## 4. The plan of action (condensed)

The full 12-week plan is in `docs/LiveJEPA_Master_Project_Plan.md` / `.pdf`. The spine:

- **Phase 0 (wk 1–2) — Sanity.** Load V-JEPA 2 + SONAR; confirm feature extraction and text round-trip; wire OpenCV capture. *Gate:* live window → V-JEPA 2 feature, and a caption round-trips through SONAR.
- **Phase 1 (wk 2–4) — Build selective decoding FIRST.** Implement offline Ward-clustering segmenter + online variance trigger; test on GT-caption embedding streams. *Gate:* adaptive Pareto-dominates uniform even on clean signal.
- **Phase 2 (wk 4–8) — Train the predictor.** Pre-cache V-JEPA 2 features; train the small head (InfoNCE + cosine) → SONAR space. *Gate:* coherent streaming captions on held-out video; full pipeline runs live.
- **Phase 3 (wk 8–11) — Evaluate & ablate.** Time-aligned CIDEr on EgoExo4D; sweep frequency; plot adaptive-vs-uniform Pareto; ablate pooling / trigger / window / threshold; add LiveCC token-generative baseline. *Gate:* adaptive dominates uniform; state a concrete iso-quality speedup.
- **Phase 4 (wk 11–12) — Package.** Polished live demo + reproducible eval + thesis writeup.

**Critical-path item:** apply for EgoExo4D access *now* (~48 h approval).

---

## 5. The honesty section (put a version of this in your thesis)

- VL-JEPA is unreleased; we reconstruct, not reproduce.
- The paper omits the Y-Decoder architecture, the numeric CIDEr values (only a curve), and the selective-decoding hyperparameters (window size, threshold, segment count). We set and document our own.
- SONAR ≠ EmbeddingGemma, so our embedding space differs by design → absolute numbers will diverge. **The claim is the *dominance relationship* (adaptive > uniform), not absolute parity.**
- Online clustering approximates offline Ward; we validate the online trigger tracks the offline segmentation on buffered data.

---

## 6. How this repo maps to the plan

```
livejepa/encoders/vision.py     ← Phase 0: V-JEPA 2 frozen feature extractor
livejepa/encoders/sonar.py      ← Phase 0: SONAR encode + decode (with stub fallback)
livejepa/selective/offline.py   ← Phase 1: Ward clustering + temporal connectivity
livejepa/selective/online.py    ← Phase 1: windowed-variance trigger (+ ruptures option)
livejepa/selective/pooling.py   ← Phase 1: smoothing / average pooling
livejepa/predictor/model.py     ← Phase 2: the trainable predictor head
livejepa/predictor/losses.py    ← Phase 2: InfoNCE + cosine regression
livejepa/data/cache.py          ← Phase 2: pre-extract & cache features
livejepa/data/egoexo.py         ← Phase 3: eval loader + annotation alignment
livejepa/train.py               ← Phase 2: train the predictor
livejepa/eval_pareto.py         ← Phase 3: CIDEr-vs-frequency Pareto evaluation
livejepa/demo.py                ← Phase 4: live 3-thread demo
configs/default.yaml            ← all hyperparameters
```

Everything ships runnable today with **stub fallbacks**: if the heavy models aren't installed yet, the encoders fall back to deterministic synthetic embeddings so you can develop and test the selective-decoding logic immediately. Swap stubs for real models when your env is ready (see `README.md`).
