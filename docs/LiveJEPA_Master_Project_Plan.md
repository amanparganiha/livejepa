# LiveJEPA — Master's Project Plan & Build Guide

> **⚠️ HISTORICAL (written 2026-06-10; the project finished 2026-08-02).** This is
> the original 12-week spine. It is preserved as the record of what was *planned*,
> which is worth reading against what actually happened — several of its
> assumptions were overturned by measurement (most notably: selective decoding
> turned out to need a *predicted* stream rather than dense labels, and the
> binding constraint was training data, not architecture). **Do not follow the
> schedule or the next-steps here.** Current state: `HANDOFF.md`. Results:
> `RESULTS.md`. Thesis: `docs/THESIS.md`. Remaining work: `thesis_materials/BUILD.md`.

**Project:** A real-time, embedding-driven video captioning system that *only speaks when something changes* — a buildable reconstruction of VL-JEPA's selective-decoding mechanism.

**Tagline for your thesis:** *"Selective Decoding in Embedding Space: Real-Time Event-Driven Video Captioning without Per-Frame Generation."*

---

## 0. What this project is (and is not)

You are **not** reusing VL-JEPA — it has no public code or weights (verified June 2026; the Hugging Face checkpoint request is still open). You are **reconstructing** the pipeline from released components and implementing the paper's genuinely novel, well-specified contribution yourself: **embedding-guided selective decoding**.

The system has two halves:

1. **The streaming embedding producer** (reused components): frozen V-JEPA 2 vision encoder → small trained predictor head → a SONAR sentence-embedding stream. SONAR is chosen over EmbeddingGemma because SONAR is *invertible to text* (it ships a decoder); EmbeddingGemma is encode-only.
2. **The selective-decoding layer** (your contribution): watch the embedding stream, decide *when* to decode using (a) temporally-constrained Ward clustering offline and (b) a windowed-variance trigger online, then decode only at those points via the SONAR decoder.

**Success criterion** (the thesis result): your adaptive selective-decoding curve **Pareto-dominates** uniform-interval decoding on a CIDEr-vs-decoding-frequency plot (EgoExo4D), reproducing the *shape* of VL-JEPA Figure 4. You will not match their absolute numbers (different encoder/decoder, undocumented hyperparameters) — and that's fine and expected.

---

## 1. System architecture

```
                         ┌─────────────────────────────────────────────┐
   Live video / file     │              LiveJEPA pipeline               │
   ───────────────►      │                                              │
                         │  [Capture thread]   OpenCV @ fixed FPS       │
                         │        │ sliding window of K frames          │
                         │        ▼                                     │
                         │  [Encode]  V-JEPA 2 ViT-L  (FROZEN)          │
                         │        │ visual tokens                       │
                         │        ▼                                     │
                         │  [Predict] small Transformer head (TRAINED)  │
                         │        │ predicted SONAR embedding  Ŝ_Y      │
                         │        ▼                                     │
                         │  ===== EMBEDDING STREAM (cheap, every step)  │
                         │        │                                     │
                         │  [Selective decoder]  ◄── YOUR CONTRIBUTION  │
                         │    online: windowed-variance trigger         │
                         │    offline: Ward clustering + midpoints      │
                         │        │ decode only at selected points      │
                         │        ▼                                     │
                         │  [Decode] SONAR text decoder (FROZEN)        │
                         │        │                                     │
                         │        ▼  caption + timestamp                │
                         └─────────────────────────────────────────────┘
```

Three decoupled threads keep the expensive decoder off the hot path: capture+encode runs continuously, prediction+change-detection is cheap and runs every step, and decoding fires rarely.

---

## 2. Components, model IDs, licenses

| Role | Model | HF / repo | Params | License | Notes |
|---|---|---|---|---|---|
| X-Encoder (vision) | V-JEPA 2 ViT-L 256px | `facebook/vjepa2-vitl-fpc64-256` | 304M | MIT | Frozen. 64-frame checkpoint; subsample for streaming. |
| Predictor | Small Transformer (you build) | — | ~10–50M | yours | The only trained part. |
| Y-space + decoder | SONAR text enc/dec | `facebook/SONAR` (fairseq2) or `cointegrated/SONAR_200_text_encoder` + `raxtemur/SONAR_200_text_decoder` | ~600M | CC-BY-NC-4.0 | 1024-dim, invertible to text. Academic use OK. |
| (Optional) baseline VLM | LiveCC-7B | `chenjoya/LiveCC-7B-Instruct` | 7B | Apache-2.0 | Token-generative streaming baseline for comparison. |
| (Optional) Y-encoder to mirror paper | EmbeddingGemma-300M | `google/embeddinggemma-300m` | 300M | Gemma (gated) | Encode-only; use only if you build a separate decoder. |

License takeaway: MIT (V-JEPA 2) + CC-BY-NC (SONAR) = fine for a thesis, blocks commercialization. For a commercial path later, train your own embedding-inversion decoder and avoid SONAR.

---

## 3. Repository layout

```
livejepa/
├── README.md
├── requirements.txt
├── configs/
│   └── default.yaml              # all hyperparameters in one place
├── livejepa/
│   ├── __init__.py
│   ├── encoders/
│   │   ├── vision.py            # V-JEPA 2 wrapper, windowed feature extraction
│   │   └── sonar.py             # SONAR encode + decode wrappers
│   ├── predictor/
│   │   ├── model.py             # the trainable predictor head
│   │   └── losses.py            # InfoNCE + cosine regression
│   ├── selective/
│   │   ├── offline.py           # Ward clustering + temporal connectivity
│   │   ├── online.py            # windowed-variance trigger, ruptures option
│   │   └── pooling.py           # average pooling / smoothing
│   ├── data/
│   │   ├── coin.py              # training dataset loader
│   │   ├── egoexo.py            # eval dataset loader + annotation alignment
│   │   └── cache.py             # pre-extract & cache V-JEPA 2 features
│   ├── train.py                 # train the predictor
│   ├── eval_pareto.py           # CIDEr-vs-frequency Pareto evaluation
│   └── demo.py                  # live webcam/file demo (3-thread)
├── scripts/
│   ├── extract_features.py
│   └── download_egoexo_subset.sh
└── notebooks/
    ├── 01_component_sanity.ipynb
    ├── 02_selective_on_gt.ipynb
    └── 03_results_plots.ipynb
```

---

## 4. Phase-by-phase plan (12 weeks)

### Phase 0 — Environment & component sanity (Weeks 1–2)

**Goal:** every released piece loads, runs, and round-trips. No novelty yet — just de-risk the stack.

Tasks:
1. Set up env (Section 5). Confirm GPU visible to PyTorch.
2. Load V-JEPA 2; extract visual features from a test clip; confirm output shape.
3. Load SONAR; encode a sentence → 1024-d vector → decode back to text. Confirm faithful reconstruction.
4. Wire OpenCV webcam capture → rolling buffer of K frames.

**Gate:** you can encode a live window to a V-JEPA 2 feature, and round-trip a caption through SONAR.

Sanity code (SONAR round-trip):
```python
from sonar.inference_pipelines.text import (
    TextToEmbeddingModelPipeline, EmbeddingToTextModelPipeline)
t2vec = TextToEmbeddingModelPipeline("text_sonar_basic_encoder", "text_sonar_basic_encoder", device="cuda")
vec2t = EmbeddingToTextModelPipeline("text_sonar_basic_decoder", "text_sonar_basic_encoder", device="cuda")
emb  = t2vec.predict(["a person slices a tomato on a board"], source_lang="eng_Latn")
print(vec2t.predict(emb, target_lang="eng_Latn", max_seq_len=64))
```

V-JEPA 2 feature extraction:
```python
import torch, numpy as np
from transformers import AutoVideoProcessor, AutoModel
model = AutoModel.from_pretrained("facebook/vjepa2-vitl-fpc64-256",
            torch_dtype=torch.float16, device_map="cuda", attn_implementation="sdpa").eval()
proc  = AutoVideoProcessor.from_pretrained("facebook/vjepa2-vitl-fpc64-256")

@torch.no_grad()
def encode_window(frames):              # frames: list of HxWx3 uint8 (RGB)
    inputs = proc(frames, return_tensors="pt").to("cuda", torch.float16)
    feats  = model.get_vision_features(inputs["pixel_values_videos"])  # (1, N_tokens, D)
    return feats
```

---

### Phase 1 — Build the selective-decoding layer FIRST (Weeks 2–4)

**Why first:** it's your contribution and it doesn't need a trained predictor. Validate it on a *clean* signal — SONAR embeddings of ground-truth EgoExo4D captions — before any noise from prediction.

**Offline segmenter** (Ward + temporal connectivity → midpoints + pooled embeddings):
```python
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from scipy.sparse import diags

def temporal_connectivity(n):
    # chain graph: each node connects only to immediate temporal neighbors
    return diags([np.ones(n-1)]*2, [-1, 1], shape=(n, n)).tocsr()

def selective_decode_points(emb, n_segments):
    """emb: (T, d) L2-normalized predicted embeddings.
       returns decode indices (segment midpoints) and pooled embeddings."""
    emb = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-8)
    conn = temporal_connectivity(len(emb))
    seg = AgglomerativeClustering(n_clusters=n_segments, linkage="ward",
              connectivity=conn).fit_predict(emb)
    points, pooled = [], []
    for s in np.unique(seg):
        idx = np.where(seg == s)[0]
        points.append(int(np.median(idx)))      # midpoint
        pooled.append(emb[idx].mean(0))          # average-pooled = denoised target
    order = np.argsort(points)
    return [points[i] for i in order], np.stack([pooled[i] for i in order])
```
Sweep `n_segments` few→many to trace the frequency axis. Ward needs Euclidean distance; on L2-normalized vectors this is monotone in cosine distance, matching the InfoNCE space.

**Online trigger** (true streaming — the most faithful real-time realization):
```python
import numpy as np
from collections import deque

class VarianceTrigger:
    def __init__(self, window=8, tau=0.15, min_gap=4):
        self.buf = deque(maxlen=window)
        self.tau, self.min_gap = tau, min_gap
        self.since_decode = min_gap

    def step(self, e):                          # e: (d,) L2-normalized
        self.buf.append(e); self.since_decode += 1
        if len(self.buf) < self.buf.maxlen:
            return None
        c = np.mean(self.buf, axis=0)
        shift = 1.0 - float(np.dot(self.buf[-1], c) /
                            (np.linalg.norm(self.buf[-1])*np.linalg.norm(c)+1e-8))
        if shift > self.tau and self.since_decode >= self.min_gap:
            self.since_decode = 0
            return np.mean(self.buf, axis=0)    # decode the pooled (denoised) embedding
        return None
```

Optional change-point alternative with `ruptures` (`rpt.Window(model="rbf")` or `rpt.Pelt`) — use the windowed-variance trigger for lowest latency; cite ruptures as a studied alternative.

**Gate:** on GT-embedding streams, your adaptive curve already Pareto-dominates uniform sampling. If it doesn't even on clean signal, fix the segmenter before training anything.

---

### Phase 2 — Train the predictor (Weeks 4–8)

**The only training in the project.** Map frozen V-JEPA 2 visual tokens → SONAR sentence embedding.

**Predictor model:**
```python
import torch, torch.nn as nn

class Predictor(nn.Module):
    def __init__(self, vis_dim=1024, d=768, out_dim=1024, depth=4, heads=8):
        super().__init__()
        self.in_proj = nn.Linear(vis_dim, d)
        layer = nn.TransformerEncoderLayer(d, heads, 4*d, batch_first=True,
                                           activation="gelu", norm_first=True)
        self.enc = nn.TransformerEncoder(layer, depth)
        self.query = nn.Parameter(torch.randn(1, 1, d))   # learned pooling query
        self.out_proj = nn.Linear(d, out_dim)

    def forward(self, vis_tokens):                # (B, N, vis_dim)
        x = self.in_proj(vis_tokens)
        q = self.query.expand(x.size(0), -1, -1)
        x = self.enc(torch.cat([q, x], dim=1))
        return self.out_proj(x[:, 0])            # (B, out_dim) predicted SONAR emb
```

**Loss** (VL-JEPA uses InfoNCE; add cosine regression for stability):
```python
import torch.nn.functional as F

def info_nce(pred, tgt, temp=0.07):
    p = F.normalize(pred, dim=-1); t = F.normalize(tgt, dim=-1)
    logits = p @ t.t() / temp
    labels = torch.arange(len(p), device=p.device)
    return 0.5*(F.cross_entropy(logits, labels) + F.cross_entropy(logits.t(), labels))

def loss_fn(pred, tgt, w_cos=1.0):
    return info_nce(pred, tgt) + w_cos*(1 - F.cosine_similarity(pred, tgt).mean())
```

**Training procedure:**
1. **Pre-cache features** (critical for speed): run V-JEPA 2 once over your COIN / Action100M-preview subset, save visual tokens + the SONAR embedding of each ground-truth caption to disk. Then training is a cheap regression — no encoder in the loop, no video decoding per step.
2. Train predictor with AdamW, lr ~3e-4 cosine, batch 256–1024 (you only backprop the small head), 10–50k steps.
3. Validate by decoding predicted embeddings on held-out clips — captions should be coherent, not necessarily perfect.

**Gate:** the trained predictor produces coherent streaming captions on held-out video, and the full pipeline (predict → cluster/trigger → SONAR decode) runs end-to-end on a live feed.

---

### Phase 3 — Evaluate & ablate (Weeks 8–11)

**Reproduce VL-JEPA's exact protocol** (time-aligned CIDEr, not whole-video CIDEr):

1. Run the system over each EgoExo4D validation video → decoded captions with timestamps `[(t̂₁,ŷ₁), …]`.
2. For each GT atomic-action annotation `(tᵢ,yᵢ)` (~143/video), align to nearest decoded output in time: `argmin |tᵢ − t̂|`.
3. Compute CIDEr (`pycocoevalcap`) over matched pairs; average.
4. **Sweep decoding frequency** 2.0 Hz → 0.01 Hz (0.5 s → 100 s mean interval) by varying `n_segments` (adaptive) and stride (uniform).
5. **Plot Pareto:** x = avg decoding frequency, y = avg CIDEr, two curves (uniform vs adaptive). Report iso-quality speedup (paper: 0.35 Hz adaptive ≈ 1 Hz uniform ⇒ ~2.85×).

```python
def time_aligned_cider(decoded, gt, scorer):
    # decoded: [(t_hat, text)], gt: [(t, text)]
    gts, res = {}, {}
    for i,(t,y) in enumerate(gt):
        j = min(range(len(decoded)), key=lambda k: abs(decoded[k][0]-t))
        gts[i] = [y]; res[i] = [decoded[j][1]]
    return scorer.compute_score(gts, res)[0]   # CIDEr-D
```

**Ablations (each is a thesis subsection):**
- exact-embedding vs average-pooled decoding at midpoints (paper says pooling helps)
- Ward clustering vs windowed-variance threshold vs ruptures change-point
- sensitivity to window W and threshold τ
- effect of embedding smoothing
- **token-generative baseline:** wrap LiveCC-7B decoding every window → embed with SONAR → run your selective layer on top. Mirrors the paper's embedding-vs-token comparison.

**Gate:** adaptive Pareto-dominates uniform on EgoExo4D; you can state a concrete iso-quality speedup.

---

### Phase 4 — Package the deliverable (Weeks 11–12)

- Polished `demo.py`: webcam/RTSP in, live event-driven captions out, with the 3-thread architecture and an on-screen "decode fired" indicator.
- Clean README, configs, reproducible eval notebooks, Pareto plots.
- Thesis writeup (Section 9).

---

## 5. Environment setup

```bash
conda create -n livejepa python=3.11 -y && conda activate livejepa
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install transformers accelerate sentence-transformers
pip install fairseq2 sonar-space          # SONAR (fairseq2 backend)
pip install scikit-learn scipy ruptures
pip install opencv-python decord torchcodec
pip install pycocoevalcap                 # CIDEr
pip install pyyaml tqdm matplotlib einops
huggingface-cli login                     # for gated models if used
```

If `fairseq2`/`sonar-space` is fiddly on your cluster, fall back to the Transformers-format SONAR ports (`cointegrated/SONAR_200_text_encoder`, `raxtemur/SONAR_200_text_decoder`) which load via plain `transformers`.

---

## 6. Datasets

| Dataset | Use | Access | Size note |
|---|---|---|---|
| **EgoExo4D** | Evaluation (paper's benchmark) | Sign license at ego-exo4d-data.org (~48h), `pip install ego4d`, `egoexo` CLI | Download annotations + a validation subset only (full set ~14 TiB) |
| **COIN** | Training the predictor | coin-dataset.github.io | Mid-size, step-segmented |
| **Action100M-preview** | Optional training (closest to paper) | `facebook/action100m-preview` (HF datasets, streamable) | 10% preview |
| **YouCook2 / ActivityNet** | Secondary eval (no license wait) | public | standard dense-captioning CIDEr |
| **MSR-VTT / MSVD** | Quick captioning sanity | public | small |

Start: **COIN (train) + EgoExo4D val (eval)**. Add Action100M-preview for closer paper fidelity. If EgoExo4D access stalls, evaluate on YouCook2/ActivityNet.

---

## 7. Hardware

- **Inference (frozen encoders):** ≤12–16 GB fp16. A 24 GB card (3090/4090/L4/A5000) is comfortable.
- **Training the predictor:** single A100/H100 (40–80 GB) is ample; even 24 GB works with cached features + grad accumulation (you only backprop the small head). Hours-to-days on a COIN-scale subset.
- **If you add LiveCC-7B baseline:** ~18–24 GB fp16, or 4-bit to ~8–10 GB.
- **Do NOT** attempt full VL-JEPA-scale pretraining (their run was 24×8 H200 for ~4 weeks). Out of scope and unnecessary.

---

## 8. Streaming / latency design

- Run capture+encode at fixed FPS (2 FPS, as LiveCC / VideoLLM-online do).
- Sliding window of K frames (8–32) at 256px; reuse overlapping computation.
- Bound the embedding buffer (e.g., last 30 s) so memory is constant regardless of stream length.
- Decode (the expensive step) only at triggered points — that's the whole efficiency argument.
- Reference latencies to beat: VideoLLM-online >10 FPS on A100; LiveCC-7B ~0.16 s/frame text gen on H100. Selective decoding wins by decoding far less often.

---

## 9. Thesis framing & contributions

State these explicitly:
1. **First independent reconstruction** of VL-JEPA's selective-decoding mechanism as working, deployable software (VL-JEPA itself is unreleased).
2. A **modular embedding-stream captioner** built from frozen released encoders + a lightweight trained predictor into an invertible (SONAR) space.
3. An **empirical Pareto study** showing embedding-guided selective decoding dominates uniform decoding on EgoExo4D, with a concrete iso-quality decoding-cost reduction.
4. **Ablations** isolating what drives the gain (pooling, trigger choice, window/threshold).
5. A **real-time demo** (smart-glasses / procedural-assistance scenario) — event-driven narration.

Honesty section (include it — graders reward it): VL-JEPA unreleased; you reconstruct, not reproduce. Paper omits Y-decoder architecture, numeric CIDEr values, and selective-decoding hyperparameters; you set and document your own. SONAR ≠ EmbeddingGemma, so absolute numbers diverge by design — the *dominance relationship* is the claim. Online clustering is an approximation of offline Ward; validate the online trigger tracks the offline segmentation on buffered data.

---

## 10. Risk register & fallbacks

| Risk | Trigger | Fallback |
|---|---|---|
| Predictor captions too weak after Phase 2 | incoherent held-out captions | Option B: use LiveCC-7B as the captioner; run selective decoding on *its* output. Your novel layer still stands. |
| EgoExo4D access stalls | no license/data by Week 6 | Evaluate on YouCook2/ActivityNet (no wait). |
| `fairseq2`/SONAR install issues | cluster conflicts | Use Transformers-format SONAR ports. |
| SONAR's CC-BY-NC blocks a commercial goal | you want a product | Train your own permissively-licensed embedding-inversion decoder; init predictor from scratch (skip Llama). |
| **Official VL-JEPA weights get released** | watch Action100M Issue #3 / `facebook` HF org | Pivot to using them directly to reproduce exact numbers — highest-value thing to monitor. |

---

## 11. Immediate next actions (this week)

1. Create the conda env (Section 5) and confirm GPU.
2. Run the two sanity snippets in Phase 0 (V-JEPA 2 feature, SONAR round-trip).
3. Apply for EgoExo4D access today (the ~48 h approval is your critical path).
4. Scaffold the repo (Section 3) and put all hyperparameters in `configs/default.yaml`.
5. Start Phase 1 — implement `selective/offline.py` and `selective/online.py` and test them on synthetic embedding streams before real data.

---

*Plan generated from the VL-JEPA paper (arXiv:2512.10942) and a verified June-2026 survey of released components (V-JEPA 2, SONAR, EmbeddingGemma, LiveCC) and tooling.*
