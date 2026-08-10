# LiveJEPA: Reconstructing and Stress-Testing Selective Decoding for Streaming Video Captioning

*Master's thesis draft — LiveJEPA. All experimental numbers are reproducible from
this repository (`RESULTS.md` gives the commands). This document is written in
Markdown for easy conversion to LaTeX/Word; figures referenced are the PNGs in the
repo root.*

---

## Abstract

Captioning a live video stream frame-by-frame is wasteful: most consecutive
frames carry the same meaning, yet a text decoder is invoked for every one. VL-JEPA
(Chen, Shukor et al., 2025; arXiv:2512.10942) proposes **selective decoding** —
maintain a continuous semantic embedding stream and invoke the caption decoder only
when the meaning *changes* — but its code and weights are unreleased. This thesis
presents **LiveJEPA**, a faithful reconstruction of that mechanism assembled entirely
from released components: a frozen **V-JEPA 2** video encoder, a small **trained
predictor**, and the invertible **SONAR** text-embedding space as decoder. On top of
this we implement two selective-decoding policies — an offline Ward-clustering
segmenter and a corrected online streaming trigger (`SegmentTrigger`) — and evaluate
them with the paper's **time-aligned CIDEr-D** metric.

Our central finding is nuanced and, we argue, more valuable than a clean win:
**selective decoding's benefit is a monotone function of the semantic stream's
temporal redundancy.** On **temporally redundant streams** (ground-truth COIN
steps, coarse EgoExo4D "keysteps") it **Pareto-dominates** uniform-interval
decoding, needing ≈1.6× fewer decodes on COIN and ≈2.5× fewer on keysteps at
equal quality — reproducing the paper's qualitative claim. On **hyper-dense
streams** (EgoExo4D *atomic* descriptions, ~1 event / 2 s), measured at the
paper's own 218-take scale, the advantage **inverts**: uniform wins at every
decode rate, because there is no redundancy for a segmenter to exploit. Crucially,
however, running the **full predicted pipeline** on that same benchmark — with a
predictor trained in-domain — **restores dominance decisively: ≈9.9× fewer
decodes at equal-or-better CIDEr**, adaptive winning 7 of 8 budgets and surviving
three adversarial controls. The predictor *smooths* a saturated annotation stream
into segmentable semantic plateaus, which is precisely the structure selective
decoding requires; the mechanism therefore needs a **predicted** stream, not
merely dense labels. That margin is significant at **every** decode budget under a
paired bootstrap over the 40 held-out takes, and a ceiling analysis places
adaptive at **87% of a provable upper bound** — *above* what decoding every single
frame achieves, at ~40× lower cost — which locates the remaining headroom in the
predictor rather than in the trigger. On COIN's predicted stream the effect is weaker and uniform
holds the mid-band (≈0.2 Hz), which a trigger-tuning sweep shows is fundamental
to predictor-stream noise rather than a tuning artifact. Separately, a **data-scaling study** on the full COIN training
split (9× more data, identical architecture) lifts held-out predictor accuracy
from cos 0.667 to **0.846** on a fixed diverse validation set, with the curve
still climbing — isolating data, not architecture, as the binding constraint on
caption quality. A further controlled experiment trains the same predictor on
**Action100M**, the corpus VL-JEPA itself used, and finds that at matched scale
the COIN-trained model **wins on Action100M's own validation set** (0.401 vs
0.348) — evidence that *supervision quality outweighs domain match* when data is
scarce. We conclude that selective decoding is a genuine efficiency mechanism
whose value is governed by the redundancy of the signal it operates on — a
concrete map of *when* an idealized mechanism pays off under real conditions.

---

## 1. Introduction

**Problem.** Real-time video understanding systems — smart glasses, robots,
procedural assistants, accessibility tools — need to *narrate* what is happening.
The naive approach runs a vision-language decoder on every frame (or every fixed
interval), which is expensive and largely redundant: within a single action, the
scene's meaning is stable, so re-decoding produces near-identical captions at full
cost.

**The VL-JEPA idea.** Rather than decode text continuously, maintain a **semantic
embedding stream** and decode a caption **only when the embedding shifts** — i.e.,
when the meaning actually changes. Decoding cost then scales with the number of
*semantic events*, not the number of frames. VL-JEPA reports that this selective
policy Pareto-dominates uniform decoding on time-aligned caption quality. But
VL-JEPA is unreleased (no code, no weights as of mid-2026), so the claim cannot be
directly reproduced or scrutinized.

**This thesis.** We reconstruct the mechanism from public parts and then *stress-test
the claim honestly*, including on the realistic setting the paper's headline numbers
gloss over (predicted rather than ground-truth streams). Concretely:

**Contributions.**
1. **A faithful, buildable reconstruction** of VL-JEPA-style selective decoding
   (frozen V-JEPA 2 → trained predictor → invertible SONAR decoder) that runs
   end-to-end on real video, including a live demo (§4, §6.4).
2. **A corrected online trigger** (`SegmentTrigger`) that fixes a subtle failure
   mode of the naive streaming trigger and recovers offline-quality selective
   decoding in a true streaming setting (§4.3, §6.2).
3. **An honest evaluation** with time-aligned CIDEr-D showing (i) clean Pareto
   dominance on idealized streams, but (ii) **regime-dependent** behavior on the
   predicted pipeline, backed by (iii) a trigger-tuning sweep proving the mid-band
   attenuation is fundamental, not a tuning failure (§6.3).
4. **A scaling result**: a wider, class-diverse predictor retrain lifts absolute
   caption quality ≈2.5× (§6.3a), extended to the full COIN split where held-out
   accuracy rises cos 0.667 → **0.846** on a fixed validation set with the curve
   still climbing — isolating *data*, not architecture, as the binding constraint
   (§6.5).
5. **The central pairing — a negative and its resolution on the same benchmark.**
   On the paper's own atomic-description protocol at full 218-take scale, adaptive
   **loses at every budget** when the stream is raw annotation (§6.7); on the
   *predicted* stream over those same annotations, with an in-domain predictor, it
   **wins 7/8 budgets at ≈9.9× fewer decodes** and survives three adversarial
   controls (§6.8). Selective decoding therefore requires a **predicted** stream,
   not merely dense labels — a distinction the original paper does not draw.
6. **Statistical and upper-bound analysis** rarely reported for this mechanism: a
   paired bootstrap over 40 held-out takes (significant at every budget), and a
   ceiling analysis placing adaptive at **87% of a provable upper bound**, *above*
   decode-everything at ~40× lower cost — which locates the residual headroom in
   the predictor rather than the trigger (§6.9).
7. **Two controlled negatives on the paper's own training corpus**: at matched
   scale, Action100M-trained predictors lose to COIN-trained ones on Action100M's
   own validation set, and adding Action100M as augmentation degrades the model —
   traced to target-vocabulary entropy rather than label noise (§6.6).

**Scope and honesty.** We do **not** claim absolute CIDEr parity with VL-JEPA: our
decoder lives in a different embedding space (SONAR, chosen because it is
*invertible*), so absolute numbers are not comparable by construction. The claim
under test is the **relationship** (adaptive vs uniform), not the absolute score.

---

## 2. Background and Related Work

**V-JEPA 2** (Assran et al., 2025) is a self-supervised video encoder trained with a
joint-embedding predictive objective; it produces strong, general video
representations without pixel reconstruction. We use the frozen `vjepa2-vitl-fpc64-256`
checkpoint (ViT-L, 1024-dim tokens) as the visual backbone.

**SONAR** (Duquenne et al., 2023) is a multilingual, multimodal sentence-embedding
space with a matching **decoder** that maps embeddings *back to text*. This
invertibility is the key enabler: it lets us treat "predict a caption" as "predict a
point in SONAR space, then decode it," so the selective layer operates entirely in
embedding space and only pays for text generation on demand. A practical subtlety
(§4.4): the SONAR decoder is trained on the encoder's *native* output scale (mean L2
norm ≈ 0.196) and returns empty strings for unit-normalized inputs.

**VL-JEPA** (Chen, Shukor et al., 2025) is the method we reconstruct. It couples a
JEPA-style video predictor with an embedding-space caption decoder and introduces the
selective-decoding policy. Because it is unreleased, LiveJEPA rebuilds the pipeline
and re-implements the selective layer as the thesis's core engineering contribution.

**Relation to keyframe / adaptive sampling.** Selective decoding is conceptually
related to keyframe selection and shot-boundary detection, but operates in a learned
*semantic* embedding space rather than on pixel differences, and is evaluated by the
downstream captioning quality it preserves, not by boundary accuracy.

---

## 3. Datasets and Metric

**COIN** — a large instructional-video dataset (~180 task classes) with
time-stamped step annotations. We use it both to train the predictor (captions =
step labels) and to evaluate selective decoding. Held-out evaluation uses a
**class-based split** (`--coin-split val`) so evaluation videos are never seen in
training.

**EgoExo4D** — an egocentric activity dataset. We evaluate on the **keystep**
annotations (~27 per take, coarse and temporally stable) — the regime the paper's
headline benchmark uses. We deliberately do **not** use the dense **atomic**
descriptions (~89/take, ~1 every 2 s): they are too fine-grained for any
change-detection segmenter, since selective decoding presupposes temporally-stable
meaning (a documented negative in §6.1).

**Metric — time-aligned CIDEr-D.** Following the paper, each ground-truth annotation
is matched to the nearest decoded caption *in time*, and CIDEr-D is computed over
those aligned pairs. This rewards saying the right thing *at the right time*, which
is exactly what a streaming captioner must do, and it penalizes both wrong captions
and captions at the wrong moment.

---

## 4. Method

### 4.1 Pipeline

```
video frames ──▶ [frozen V-JEPA 2] ──▶ visual tokens
                                          │
                                          ▼
                              [trained predictor] ──▶ SONAR-space embedding stream
                                          │
                              [selective decoding layer]  ← contribution
                                          │ (fires only on semantic change)
                                          ▼
                                   [SONAR decoder] ──▶ caption
```

Frames are processed in sliding windows of **K = 16** frames at a working rate of
**2 fps** (matching how features are cached and how the predictor is trained). Each
window yields one embedding in the stream; the selective layer decides which stream
positions get decoded to text.

### 4.2 The predictor

A small transformer maps V-JEPA 2 tokens (1024-dim) to a SONAR embedding
(1024-dim): hidden dim 768, depth 4, 8 heads, dropout 0.1 (~29.9M parameters). It is
trained with a combined **InfoNCE** (temperature 0.07) + **cosine-regression** loss
(both scale-invariant), Adam, lr 3e-4, weight decay 0.05, 500-step warmup, 20k steps.
Because both loss terms are scale-invariant, the predictor's raw output norm is
arbitrary and must be rescaled to SONAR's native norm at inference (§4.4).

### 4.3 Selective decoding: offline and online

**Offline (Ward).** Given the full embedding stream, we run agglomerative
(Ward-linkage) clustering with a **temporal-connectivity** constraint into a target
number of segments, then decode **one pooled (mean) embedding per segment at its
midpoint**. This is the idealized "we can see the whole stream" policy.

**Online (`SegmentTrigger`).** For true streaming we need a causal trigger. A naive
`VarianceTrigger` decodes the mean of the last *W* embeddings whenever a shift is
detected — but that window **straddles the event boundary** (old + new meaning
mixed) and timestamps the decode *on* the boundary, which tracks the offline result
poorly (§6.2: only ~3.5 CIDEr @0.1 Hz). Our corrected `SegmentTrigger` instead
**accumulates the current segment and, when a shift fires, emits the *previous*
segment's mean at its midpoint index** (retrospective, one-window latency). Same
detector, better emission — it recovers offline-level quality (§6.2). Parameters:
window W = 8, shift threshold τ = 0.15, minimum gap = 4 steps.

### 4.4 SONAR native-scale handling

The SONAR decoder rejects unit-norm vectors (empty strings) because it was trained
on the encoder's native scale (norm ≈ 0.196). Two consequences are handled
throughout: (i) the selective layer clusters/triggers on *normalized* embeddings
(scale-invariant) but **pools and returns embeddings at native scale** for decoding;
(ii) the predictor's arbitrarily-scaled output is **rescaled to the native norm**
before decoding. Getting this wrong silently produces empty captions.

---

## 5. Experimental Setup

- **Hardware:** local NVIDIA T1000 (8 GB) for inference/eval; the wide predictor
  retrain (§6.3a) runs on a free Kaggle GPU. V-JEPA 2 encoding is ~11 s/window on
  the T1000, so the pipeline is not real-time on this hardware (§7).
- **Software:** Python 3.14, PyTorch 2.10; SONAR via the transformers backend
  (fairseq2 is Linux-only). Stub fallbacks let the selective logic be unit-tested
  with no heavy models.
- **Evaluation modes:** `gt` (stream built from ground-truth captions — isolates the
  selective *mechanism*) and `predictor` (full V-JEPA 2 → predictor → SONAR — the
  end-to-end system). Frequency sweep in Hz; adaptive is budget-matched to uniform at
  each frequency for a fair comparison.

---

## 6. Results

### 6.1 Mechanism: adaptive vs uniform on clean streams (Pareto dominance holds)

On **GT streams**, selective decoding Pareto-dominates uniform.

*COIN val, gt mode, 26 videos:*

| target Hz | uniform | adaptive |
|---:|---:|---:|
| 0.50 | 8.47 | **8.79** |
| 0.35 | 7.92 | **8.68** |
| 0.20 | 6.83 | **7.72** |
| 0.10 | 4.94 | **5.27** |

Adaptive holds CIDEr ≈ 7.7 at 0.20 Hz, which uniform reaches only near 0.31 Hz →
**≈1.6× fewer decodes at equal quality**.

*EgoExo4D val keysteps, 10 takes (the paper's own benchmark):*

| target Hz | uniform | adaptive |
|---:|---:|---:|
| 0.50 | 8.20 | 8.20 |
| 0.35 | 8.12 | **8.20** |
| 0.20 | 7.75 | **8.20** |
| 0.10 | 6.54 | **7.38** |
| 0.05 | 4.70 | 4.16 |

Adaptive holds the 8.20 plateau down to 0.20 Hz vs uniform's ~0.50 Hz →
**≈2.5× fewer decodes** (the paper reports 2.85×). Both show an honest low-frequency
**crossover** (≤0.05 Hz), where uniform's even spacing wins — so this is *mid-band*
dominance, not strict full-range Pareto. **Granularity finding:** the same segmenter
fails on EgoExo4D *atomic* descriptions (too dense) — selective decoding needs
temporally-stable meaning.

### 6.2 Online trigger correction

At ~0.10 Hz on EgoExo4D keysteps: uniform 6.06, offline Ward 6.72, **naive online
~3.5**, **corrected `SegmentTrigger` 7.2–7.7**. The correction closes the gap between
naive streaming and the offline oracle and even edges it out — the real-time path
works. (13/13 unit tests pass, including the trigger.)

### 6.3 Full predicted pipeline

**(a) Wide-predictor retrain — the quality lever.** Retraining for 20k steps on
class-diverse COIN (2962 train / 1118 val samples, ~180 classes) gives held-out
**cos(pred,target) = 0.636** on the 1118-sample diverse val, with **pred–pred cos =
0.504 (not collapsed)**. Captions capture the right action manifold with fuzzy object
detail (e.g., "open the car key cover" → "open the back lid"; "stand up with straight
legs" → exact). This lifted absolute end-to-end quality **≈2.5×** vs the earlier
narrow predictor (below). *This was the first rung of a larger data-scaling study,
§6.5.*

**(b) Predictor-in-the-loop Pareto — 7 held-out COIN val videos.**

| target Hz | uniform | adaptive | winner |
|---:|---:|---:|:--|
| 1.00 | 2.611 | **2.814** | adaptive |
| 0.50 | 2.644 | **2.779** | adaptive |
| 0.35 | **2.856** | 2.735 | uniform |
| 0.20 | **2.960** | 2.411 | uniform |
| 0.10 | 2.124 | **2.415** | adaptive |
| 0.05 | 2.191 | 2.150 | ~tie |
| 0.01 | **1.960** | 0.977 | uniform |

Two things stand out. First, absolute CIDEr is now **2.6–3.0**, versus ≤1.2 for the
pre-retrain narrow predictor — the retrain, not the selective layer, drove that.
Second, **adaptive no longer cleanly dominates**: it wins at high (≥0.5 Hz) and sparse
(0.1 Hz) rates, but **uniform peaks at 0.20 Hz (2.96)** and wins the mid-band. The
reliable band is 0.2–1.0 Hz (n = 200–1000 decodes); the low-Hz tail (n = 10–53) is
noise. N = 7 videos.

**(c) Is the mid-band loss a tuning artifact? No.** We swept the trigger's
`smoothing_window ∈ {1,3,5,7}` × `linkage ∈ {ward, average}` on the cached streams,
using the *identical* SONAR decoder and CIDEr (the harness self-validates: the
`smooth=1, ward` cell reproduces (b) to 3 decimals). **Every** smoothing setting made
the mid-band *worse*; the best config is the un-smoothed baseline (mean Δ = −0.061
vs uniform). At 0.20 Hz, uniform (2.96) beats **all eight** adaptive configurations.
The attenuation is therefore **fundamental to predictor-stream noise**, not a
mis-tuned trigger — a clean negative result.

**Interpretation.** On GT/keystep streams the segment structure is crisp, so adaptive
places decodes exactly where meaning changes and wins. On the predicted stream the
structure is fuzzy (predictor noise), so change-detection fires imperfectly; meanwhile
0.20 Hz ≈ one decode per 5 s ≈ the datasets' step cadence, where uniform's even
spacing gives near-optimal coverage. The mechanism's advantage is real but **erodes
as the upstream signal degrades**.

### 6.4 Live demo (Phase 4)

`demo.py` runs the full pipeline on webcam or video, decoding only when
`SegmentTrigger` fires, with an annotated overlay (caption, a "DECODE" flash when the
decoder actually runs, and a decodes/steps efficiency counter). It was verified
end-to-end on real video; a bug was found and fixed where frames were sampled at
native fps (near-duplicate windows) instead of subsampled to the working rate. On a
COIN clip, adaptive decoded 2/40 windows (5%) vs uniform 4/40 (10%) — **half the
decodes** — with sensible captions (e.g., "lift the barbell directly over the head").
A headless `--save-video` path renders the deliverable without a display.

### 6.5 Data-scaling study

Because §6.3 identified predictor caption quality (a *data* property) as the limit
on the full-system result, we scaled the predictor's training data while holding
the architecture (29.9M params), recipe (30k steps, InfoNCE + cosine), and both
validation sets fixed. A three-lane extraction fleet (free Kaggle T4 + Colab +
local T1000, working one shared video list) resolved **8,984 / 9,023 COIN training
videos (99.6%)** into a 26,360-clip feature cache.

| training clips | frozen 137-val cos | diverse 956-val cos | pred–pred |
|---:|---:|---:|---:|
| 2,962 | 0.772 | 0.667 | 0.527 |
| 5,529 | 0.883 | 0.733 | 0.467 |
| **26,360** | **0.897** | **0.846** | **0.408** |

On the diverse 956-sample validation set (240 held-out videos) accuracy rose
**+0.113 cos over the final 4.8× of data and had not saturated**; predictions grew
*more* diverse (pred–pred 0.527 → 0.408), excluding collapse. This isolates **data,
not architecture or the selective layer, as the binding constraint** on caption
quality, and motivates training on the paper's own data distribution
(Action100M) as the next rung. It is also, to our knowledge, the first reported
data-scaling curve for a VL-JEPA-style predictor.

### 6.6 Training on the paper's own data (Action100M): a controlled negative

VL-JEPA trains on **Action100M**; we trained on COIN step labels. To test whether
that difference matters we rented an RTX 4090 (~$8), extracted Action100M-preview
features with a chunked download→extract→delete pipeline, and trained an
otherwise identical predictor (20k steps, batch 64). YouTube rate-limiting capped
extraction at **6,710 train / 160 val clips**, which — fortuitously — makes this
a near-exact *scale match* to our 5,529-clip COIN rung rather than a scale-up.

| model (training data) | COIN-137 | COIN-956 | **A100M-160** |
|---|---:|---:|---:|
| C1-final (26,360 COIN, 30k steps) | **0.897** | **0.846** | 0.386 |
| C1-mid (5,529 COIN, 20k steps) | 0.883 | 0.733 | **0.401** |
| C2 (6,710 A100M, 20k steps) | 0.359 | 0.392 | 0.348 |

**Both COIN-trained models outperform the Action100M-trained model on
Action100M's own validation set.** The scale-matched control is decisive: C1-mid
saw *fewer* clips (5,529 vs 6,710) for the same 20k steps yet scores 0.401 vs
0.348, so the gap is not explained by training-set size.

Measuring the two corpora explains why, and the explanation is not the obvious
one:

| corpus | clips | unique captions | repeats per caption |
|---|---:|---:|---:|
| COIN | 26,863 | 747 (3%) | **36.0** |
| Action100M | 6,710 | 6,096 (91%) | **1.1** |

COIN is effectively **closed-set**: 747 recurring step labels, each observed ~36
times. Action100M is genuinely **open-vocabulary**: nearly every caption is
unique and observed once. Inspection confirms A100M's captions are mostly
sensible actions (*"Sponging off powder from design surface"*, *"puree the
mixture in a blender"*), so this is not primarily a label-noise effect. The
decoded outputs match the entropy explanation: C2 acquired the *distribution of
phrasings* but, with roughly one example per target, could not bind phrasing to
content (`'Get a needle'` → `'Push the squeeze of the treats.'`), while the
COIN models' closed vocabulary transfers out of domain as a coarse but useful
prior.

**This qualifies our own headline.** The scaling result of §6.5 is measured on a
747-label closed set, so a portion of the gain is improved closed-set
discrimination rather than open-ended captioning ability. Cosine scores across
the two corpora are therefore **not commensurable** — they are different tasks
sharing a metric. We report both rather than collapsing them.

**Augmentation does not rescue it either.** Replacing COIN with A100M loses; the
natural remedy is to *add* it. Training the identical recipe on the union
(26,863 COIN + 6,710 A100M = 33,573 clips, the largest set in this work) gives
COIN-137 **0.875**, COIN-956 **0.823**, A100M **0.390** — slightly *worse* on
both COIN benchmarks than COIN alone, and no better than COIN alone on A100M.
The captions expose the mechanism: open-vocabulary targets contaminate
previously exact closed-set outputs (`'squat and hold the barbell'` →
`'sitbar and hold the barbell'`), and exact matches on the frozen benchmark fall
from 7/10 to 5/10. A 25% increase in data volume is outweighed by the entropy
mismatch it introduces.

**Scope and the corrected lesson.** This evaluates the 10% *preview* release at
~6.7k clips; VL-JEPA used the full 1.2M-video corpus, where an open vocabulary
is adequately covered. The defensible claim is narrow but useful: *open-
vocabulary supervision requires orders of magnitude more data than closed-set
supervision to reach comparable predictive accuracy* — so a low-resource
reconstruction is better served by a small closed-vocabulary corpus, and the
apparent "win" of a closed set partly reflects an easier task.

### 6.7 Paper-protocol EgoExo4D — atomic descriptions at scale (the boundary)

We finally ran the paper's exact headline benchmark: EgoExo4D validation, **atomic
action descriptions**, time-aligned CIDEr-D over a frequency sweep, on the **218
density-matched validation takes** (annotation counts closest to the paper's
~143/video; our pool runs sparser at median 100). This is the density regime the
paper's 2.85× headline is quoted on.

| target Hz | uniform | adaptive |
|---:|---:|---:|
| 1.00 | **4.48** | 3.57 |
| 0.50 | **3.47** | 3.11 |
| 0.35 | **2.91** | 2.79 |
| 0.20 | **2.31** | 2.26 |
| 0.10 | **1.78** | 1.61 |
| 0.05 | **1.40** | 1.21 |

**Uniform wins at every frequency** — there is no iso-quality speedup for adaptive
on atomic descriptions. Far from contradicting the mechanism, this **completes**
the picture from §6.1: keysteps (~1 event / 15 s) are redundant and adaptive wins
~2.5×; atomic descriptions (~1 event / 2 s) are saturated with change and adaptive
loses. The benefit tracks temporal redundancy monotonically. The gap to the paper's
positive atomic result is instructive and honest: our measurement is a clean
**gt-mode** stream that isolates the segmenter on raw annotation density, whereas
the paper's number comes from their *predicted* (denoised) stream. Whether a
denoised predicted stream recovers an advantage at atomic density is the precise
question our next rung (predictor-mode on these takes) is designed to answer; the
result here is the baseline it will be measured against.

---

### 6.8 The predicted stream restores dominance on the paper's own benchmark

§6.7 evaluated atomic descriptions on a *clean* ground-truth stream and found
uniform superior at every budget. VL-JEPA's headline, however, was measured on
their **predicted** stream. Testing that required a predictor able to caption
EgoExo: our COIN-trained model produced semantically correct but stylistically
alien output ("remove the chain" against annotations phrased "the camera wearer
takes a tire lever from the table with his right hand"), collapsing CIDEr to
**0.012 for both methods** — an unmeasurable comparison rather than a result.

We therefore trained an in-domain predictor on 11,556 (window, caption) pairs
drawn from 721 EgoExo takes, windowed identically to inference, for 20k steps.
The 40 evaluation takes were excluded from training; 25 further takes were held
out for gating (cos **0.599**, pred–pred 0.325).

| avg Hz | decodes | uniform | adaptive |
|---:|---:|---:|---:|
| 0.499 | 3537 | 0.310 | **0.348** |
| 0.199 | 1412 | 0.287 | **0.333** |
| 0.050 | 357 | 0.278 | **0.338** |
| 0.020 | 140 | 0.249 | **0.312** |

Adaptive wins 7 of 8 budgets, and absolute quality rises **25×** (0.012 → 0.33)
purely from correcting the domain. In the paper's reporting form: the best
uniform score anywhere is 0.310 (0.499 Hz, 3537 decodes), which adaptive exceeds
at 0.050 Hz using 357 decodes — **≈9.9× fewer decoder invocations at
equal-or-better quality** (the paper reports 2.85×).

**Three controls distinguish this from the artifact we rejected.** An earlier
out-of-domain attempt appeared to show adaptive winning on a semantic metric;
its controls revealed the effect was denoising, not selection. Repeating those
controls here: the metric's sensitivity to *timing* rises from +0.0012
(out-of-domain, effectively blind) to **+0.0225–0.0284**; disabling mean-pooling
leaves a **flat +0.031–0.040 advantage at every frequency** (versus collapse
previously), isolating temporal selection from averaging; and adaptive beats
random placement at **8/8** budgets while uniform is statistically
indistinguishable from random placement (0.605 vs 0.606) — establishing that the
gain arises from *where* decodes are placed.

**Interpretation.** This resolves the apparent contradiction with §6.7. A raw
atomic-annotation stream is saturated with change and offers nothing to segment;
the predictor, being a smooth function of video, converts it into a stream with
genuine semantic plateaus. Selective decoding is therefore not a property of
dense supervision but of *predicted* representations — a distinction the original
paper does not draw explicitly, and one that our negative and positive results
together isolate. We do not claim magnitude parity: our predictor is in-domain
whereas VL-JEPA's was cross-domain, and EgoExo takes are internally repetitive
(mean pairwise caption similarity 0.669), both of which favour sparse adaptive
decoding.

### 6.9 Significance, and how much headroom remains

Two questions a reader will put to §6.8: *is the margin real across only 40
videos*, and *how close to optimal is the trigger?*

**Significance.** We score every take separately and bootstrap the **paired**
difference (adaptive − uniform) over 5,000 resamples; pairing is the correct
design because both methods see the identical take, so take-difficulty variance
cancels. The semantic margin is significant at **all eight** budgets, with
**40/40 takes favouring adaptive** at seven of them (Δ = +0.040 at 1 Hz rising to
+0.106 at 0.02 Hz). Per-take CIDEr agrees in direction at every budget and is
significant at seven of eight; the exception is the degenerate 0.011 Hz point
(~2 decodes per take). CIDEr has visibly lower statistical power here — n-gram
overlap over ~100 events is high-variance, whereas cosine similarity is smooth —
which is itself an argument for reporting the semantic metric alongside it.

**Headroom.** We then bound what any trigger could achieve. The *best-window
ceiling* takes, for each annotation, the maximum over all contiguous ranges of
cos(mean(stream[a:b]), gt); since every method in this work decodes a pooled mean
of a contiguous span, this upper-bounds every row of the Pareto table. It is
deliberately loose — each annotation may choose its own window under no budget —
so the fraction of it a real schedule attains is a *conservative* measure of
trigger quality.

| reference | score (95% CI) | % of ceiling |
|---|---|---:|
| uniform @0.05 Hz | 0.5949 [0.5740, 0.6167] | 77.1% |
| dense — decode **every** timestep, no selection | 0.6037 [0.5854, 0.6243] | 78.2% |
| GT-boundary — segment the *ground-truth caption* stream | 0.6684 [0.6522, 0.6851] | 86.6% |
| **adaptive @0.05 Hz (ours)** | **0.6725** [0.6560, 0.6898] | **87.1%** |
| best-frame ceiling | 0.7541 [0.7396, 0.7692] | 97.7% |
| **best-window ceiling** (upper bound) | **0.7720** [0.7577, 0.7867] | 100% |

Three findings follow.

*Decoding more does not help.* Uniform quality is flat in decode rate — 0.5949 at
0.05 Hz, 0.6054 at 0.5 Hz, 0.6037 decoding every timestep. Adaptive at 0.05 Hz
(0.6725) **exceeds decode-everything** while invoking the decoder ~40× less
often. On this benchmark selective decoding is therefore not a quality/compute
trade-off but a strict improvement: segment pooling denoises the predicted
stream, and the +0.018 gap between the best-window and best-*frame* ceilings
confirms that a pooled span carries signal no individual timestep does.

*Perfect boundary knowledge is not the missing piece.* A trigger given the
annotators' own boundaries scores at or slightly **below** adaptive (0.6684 vs
0.6725). The explanation is that annotation boundaries are homogeneous in
*caption* space while adaptive's are homogeneous in *predictor* space, so
adaptive's pooled mean better represents what the encoder actually saw.
Ward-on-the-predicted-stream is already near the limit of what timing can buy.

*The residue is representational.* Adaptive attains 87.1% of a bound no real
schedule can reach, and the boundary oracle cannot improve on it. The remaining
gap therefore belongs to the predictor rather than the trigger: further progress
requires a better model of *what* is happening, not a better decision about
*when* to speak. This is a useful negative for the research programme — it says
that effort spent tuning trigger thresholds (§6.3's sweep, which also came back
negative) is misdirected, and that the lever is predictor capacity and in-domain
data, exactly the axis on which §6.5's scaling curve was still climbing.

*Provenance note.* Our first implementation of the boundary oracle returned a
score **below uniform**, which is impossible for an upper bound and was a code
fault rather than a result: the ground-truth stream is timestamped from t = 0
while the predicted stream carries window-centre times beginning ~3.75 s in, so
index-based mapping misaligned every decode by ~4 s, and the oracle compared
exact embeddings against adaptive's pooled ones. Both were corrected before the
numbers above were produced. We record it because the diagnostic generalises: an
upper bound that loses to the method it bounds is a bug, not a finding.

## 7. Discussion

The headline lesson is about **where an idealized mechanism meets reality**, and it
arrives in two parts that must be read together.

**Selective decoding needs a predicted stream, not merely dense labels.** Our
sharpest pair of results sits on a single benchmark — EgoExo4D atomic
descriptions, the paper's own protocol — differing in exactly one respect. On the
*raw annotation* stream, adaptive loses at every budget (§6.7): an event lands
roughly every two seconds, so there is no temporal redundancy for a segmenter to
exploit and uniform's even spacing is near-optimal. On the *predicted* stream over
those same annotations, adaptive wins 7 of 8 budgets at ≈9.9× fewer decodes
(§6.8). The predictor, being a smooth function of video, converts a saturated
annotation stream into one with genuine semantic plateaus — precisely the
structure the mechanism consumes. This is a distinction the original paper does
not draw explicitly, and it is only visible because we ran the negative first.

**But the benefit is still bounded by redundancy.** The two predicted-stream
results are not in tension. On COIN, uniform holds the 0.2–0.5 Hz mid-band even
with a 2×-better predictor (§6.3, §6.5), because 0.2 Hz ≈ COIN's intrinsic step
cadence — even spacing matches the true event rate. On EgoExo, takes are
internally repetitive (mean pairwise caption similarity 0.669), leaving long
plateaus that reward sparse, well-placed decodes. Both are the same monotone law:
*the value of selective decoding tracks the redundancy of the stream it operates
on*, and a predictor is one way — not the only way — to create that redundancy.

**Where the remaining headroom lives.** §6.9 answers this directly rather than by
speculation. Adaptive attains 87% of a provable upper bound, a trigger handed the
annotators' own boundaries cannot beat it, and trigger tuning was already a clean
negative (§6.3). The lever is therefore predictor capacity and in-domain data —
the axis on which §6.5's scaling curve had not flattened. That §6.9 also shows
adaptive *beating* decode-everything at ~40× lower cost reframes the mechanism:
on a noisy predicted stream, segment pooling is not merely a way to spend less
compute, it is a way to get a **better** answer.

This clarifies what is a *predictor* problem versus a *mechanism* problem. Caption
correctness (vocabulary, object detail) is a predictor/data-scale property; the
selective policy decides *when* to decode, not *what*. Separating these two axes
is, we think, the most transferable result here — and §6.6's entropy analysis
sharpens it further, showing that what looked like a domain-match question was
really a question about the entropy of the target vocabulary.

**A methodological note.** Three times in this project a positive result did not
survive its own controls, and saying so is part of the contribution. An earlier
out-of-domain semantic win proved to be denoising rather than selection, and was
reported as inconclusive (§6.8). A "noisy labels" explanation for the Action100M
negative was contradicted by measurement and replaced by the entropy account
(§6.6). An upper bound that lost to the method it bounded turned out to be a
time-alignment bug, and when the corrected version *still* did not exceed
adaptive, the right conclusion was that the label "oracle" was wrong, not the
number (§6.9). Adversarial controls — shuffled alignment, pooling ablation,
random placement, paired bootstrap — did more work in this thesis than any
individual experiment.

---

## 8. Limitations

- **Small COIN predicted-stream eval (N = 7 videos).** The §6.3/§6.5 conclusions
  rest on 7 held-out videos; the low-frequency tail is explicitly noise. Uniform's
  0.20 Hz peak is robust to trigger tuning but not to sample size. (The EgoExo
  headline, §6.8–6.9, is on 40 takes with per-take CIs and does not share this
  weakness.)
- **The headline is 40 takes, not 218.** §6.8 uses 40 held-out takes; the frozen
  218-take pool exists and the same protocol would run on it, at ~84 h on the
  local T1000. The paired bootstrap makes 40 sufficient for significance, but the
  point estimate would tighten.
- **Magnitude is not comparable to the paper's 2.85×.** Our predictor is
  *in-domain* (EgoExo takes, disjoint from the eval takes) whereas VL-JEPA's was
  Action100M-trained and evaluated cross-domain; and EgoExo takes are internally
  repetitive (caption self-similarity 0.669), which favours sparse decoding. The
  *direction and shape* replicate; the number should not be read as a beat.
- **The ceiling is loose by construction.** §6.9's upper bound lets each
  annotation choose its own contiguous window under no budget, so no real schedule
  can attain it; 87% is a conservative reading of trigger quality, not a claim that
  13% is recoverable.
- **Different embedding space.** SONAR (chosen for invertibility) is not VL-JEPA's
  space, so absolute CIDEr is not comparable — only the adaptive-vs-uniform
  relationship is.
- **Two predictors, two vocabularies.** The COIN predictor is trained on ~180
  closed-set classes; the EgoExo predictor on 11.5k in-domain pairs. Neither is
  open-domain, and §6.6 shows why that gap is a data-scale problem: open-vocabulary
  targets at ~1 example each are not learnable at our budget.
- **Action100M conclusions are scoped to the preview release** (~6.7k clips after
  throttling), not the full 1.2M-video corpus VL-JEPA used.
- **CIDEr has low statistical power at these scales** (§6.9: 23–28/40 takes vs
  40/40 on the semantic metric); we report both metrics for this reason, and the
  semantic metric is ours, not the paper's.
- **Not real-time on the test hardware.** V-JEPA 2 is ~11 s/window on a T1000.
- **Granularity dependence.** Selective decoding requires temporally-stable
  meaning; it fails on very dense *annotation* streams — though §6.8 shows a
  predictor can manufacture the stability that raw annotations lack.

---

## 9. Conclusion and Future Work

We reconstructed VL-JEPA's selective-decoding mechanism from released components,
corrected its online realization, and stress-tested it against its own claims.

Selective decoding **Pareto-dominates uniform on temporally redundant streams**
(≈1.6× on COIN steps, ≈2.5× on EgoExo4D keysteps). On the paper's own
atomic-description benchmark it **loses at every budget when the stream is raw
annotation** — and **wins 7 of 8 budgets at ≈9.9× fewer decodes when the same
annotations are approached through a predicted stream**, significantly at every
budget over 40 held-out takes. The mechanism therefore requires a *predicted*
stream, not merely dense labels, and its benefit tracks the redundancy of whatever
stream it is given. A ceiling analysis places our trigger at **87% of a provable
upper bound**, above what decoding every frame achieves at ~40× the cost,
locating the remaining headroom in the predictor; a data-scaling study on the full
COIN split (cos 0.667 → **0.846**, still climbing) shows that lever is far from
exhausted, while two controlled negatives on Action100M show it is a question of
target-vocabulary entropy rather than domain match. The project is a working,
reproducible system with a defensible — and, where the evidence demanded it,
negative — scientific story.

**Future work,** ordered by what the evidence above actually recommends.
(1) **Predictor capacity and in-domain data**, which §6.9 identifies as the binding
constraint and §6.5 shows is still paying off; §6.6 predicts the route is ~10–100×
more open-vocabulary data (free via Kaggle), not a different mixing strategy.
(2) **Scale the headline from 40 to 218 takes** on the frozen pool, tightening the
point estimate. (3) A **hybrid policy** — a uniform floor plus adaptive extra
decodes on detected change — as the most plausible way to recover dominance in
COIN's mid-band, the one regime where uniform still holds. (4) A **pretrained-VLM
variant**: the trigger is decoder-agnostic, so pairing it with a strong pretrained
captioner would give open-domain accuracy while keeping decode-on-change
efficiency. (5) The optional **LiveCC token-generative baseline** for a
like-for-like comparison. (6) A **deployable web UI + backend** — already
prototyped (§6.4) — as the practical product form on non-real-time hardware.

---

## Appendix A — Reproducibility

Set `project.use_stubs: false` in `configs/default.yaml`; models cache in
`~/.cache/huggingface/hub`. Key commands (full list in `RESULTS.md`):

Two checkpoints are referenced throughout: `checkpoints_c1_final/predictor_30000.pt`
(the COIN model, cos 0.846, also the deployed one) and
`checkpoints_egoexo/predictor_20000.pt` (the in-domain EgoExo model used for
§6.8–6.9 only). Earlier sections were measured on `checkpoints_kaggle/predictor_20000.pt`
(cos 0.636); that is noted where it matters, and §6.5 reports both.

```bash
# Mechanism (clean GT streams)                                          -> 6.1
python -m livejepa.run_eval --dataset coin --mode gt
python -m livejepa.run_eval --dataset egoexo --mode gt --gt-source keystep --max-videos 10 --max-seconds 300
# Ablations + tests                                                     -> 6.2
python scripts/ablations.py
python -m pytest tests/ -q                      # 13/13
# Predictor quality, data-scaling rungs                                 -> 6.5
python scripts/eval_predictor.py --ckpt checkpoints_c1_final/predictor_30000.pt --val data_cache_coin2_val --decode
python scripts/eval_predictor.py --ckpt checkpoints_c1_final/predictor_30000.pt --val data_cache_coin_full_val
# Full predicted-pipeline Pareto + tuning sweep                         -> 6.5, 6.3
python -m livejepa.run_eval --dataset coin --mode predictor --ckpt checkpoints_c1_final/predictor_30000.pt --coin-split val --max-videos 7 --max-seconds 180
python scripts/tune_adaptive.py --ckpt checkpoints_kaggle/predictor_20000.pt
# Action100M rungs C2 / C3                                              -> 6.6
python scripts/eval_predictor.py --ckpt checkpoints_c2/predictor_20000.pt --val data_cache_a100m_val --decode
python -m livejepa.train --config configs/default.yaml --data-root "data_cache_coin_full,data_cache_a100m" \
    --ckpt-dir checkpoints_c3_combined --max-steps 30000 --batch-size 32
# Atomic descriptions, clean GT stream (the negative)                   -> 6.7
python -m livejepa.run_eval --dataset egoexo --mode gt --gt-source atomic \
    --uids-file eval_data/egoexo_takes_218.txt --max-seconds 360 --out results_egoexo_atomic_218
# In-domain predictor: build cache, train, then the headline Pareto     -> 6.8
python scripts/build_egoexo_cache.py --max-per-take 20 --max-samples 12000 \
    --exclude-uids eval_data/egoexo_takes_pred40.txt
python -m livejepa.train --config configs/default.yaml --data-root data_cache_egoexo \
    --ckpt-dir checkpoints_egoexo --max-steps 20000 --batch-size 32
python -m livejepa.run_eval --dataset egoexo --mode predictor --gt-source atomic \
    --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 \
    --out results_egoexo_predictor_40_indomain
python scripts/eval_semantic_pareto.py --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 --out <name>   # + --pool none
# Significance, headroom, figures                                       -> 6.9
python scripts/eval_rigor.py   --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 \
    --methods uniform,adaptive --boot 5000 --out results_egoexo_rigor
python scripts/eval_ceiling.py --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360
python scripts/make_thesis_figures.py
# Live demo (headless annotated MP4)                                    -> 6.4
python -m livejepa.demo --source <video.mp4> --ckpt checkpoints_c1_final/predictor_30000.pt \
    --no-display --save-video demo_adaptive.mp4 --mode adaptive
```

## Appendix B — Figures and artifacts

All are collected in `thesis_materials/figures/`, indexed by
`thesis_materials/INDEX.md`; every `.png` ships with the `.json` it was plotted
from, and `thesis_materials/TABLES.md` holds every table in this chapter.

| § | Figures |
|---|---|
| 6.1 | `results_coin_gt.png`, `results_egoexo_keystep.png` |
| 6.2 | `results_ablation_methods.png` |
| 6.3 | `results_adaptive_tuning.json` (tuning sweep, table only) |
| 6.4 | `demo_adaptive.mp4`, `demo_uniform.mp4` |
| 6.5 | `results_coin_predictor_c1final.png`, `results_coin_predictor_c1old.png` |
| 6.7 | `results_egoexo_atomic_218.png` |
| 6.8 | `results_egoexo_predictor_40_indomain.png` **(headline)**, `results_egoexo_predictor_40_indomain_semantic.png`, `results_egoexo_predictor_40_indomain_semantic_nopool.png`; the rejected out-of-domain run is kept as `results_egoexo_predictor_40_semantic.png` and `results_egoexo_predictor_40_semantic_nopool.png` for the controls discussion |
| 6.9 | `results_egoexo_rigor.png` (paired CIs), `results_egoexo_ceiling.png` (headroom) |

## References (to be formatted to the institute's citation style)

- Chen, Shukor, et al. *VL-JEPA.* arXiv:2512.10942, 2025.
- Assran, et al. *V-JEPA 2.* 2025.
- Duquenne, et al. *SONAR: Sentence-Level Multimodal and Language-Agnostic Representations.* 2023.
- Vedantam, Zitnick, Parikh. *CIDEr: Consensus-based Image Description Evaluation.* CVPR 2015.
- Tang, et al. *COIN: A Large-scale Dataset for Comprehensive Instructional Video Analysis.* CVPR 2019.
- Grauman, et al. *EgoExo4D.* 2024.
