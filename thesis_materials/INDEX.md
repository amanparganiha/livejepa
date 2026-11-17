# Thesis Materials — index

Everything needed to format the thesis, in one place. Prose draft is
`docs/THESIS.md`; tables are `TABLES.md` (here); artifacts are in `figures/`.

**Last refreshed 2026-11-17** — the headline changed. The predicted-stream result
now includes the pooling-matched uniform baseline (**uniform+pool**) that VL-JEPA's
own protocol implies and ours had lacked; against it, adaptive's advantage
disappears. See WORKLOG 2026-11-17. (Earlier refreshes: 2026-08-02 after the
ceiling analysis; 2026-09-20 in the thesis fix pass.)

## Documents
| File | What it is |
|---|---|
| `../docs/THESIS.md` | Full thesis draft (prose, all sections) — **the working copy; edit this** |
| `thesis.tex` | LaTeX main file: preamble, title page, bibliography. Hand-written, safe to edit |
| `thesis_body.tex` | **GENERATED** from THESIS.md by `scripts/md_to_latex.py`. Never hand-edit |
| `paper_ieee.tex` | IEEE journal-format paper (IEEEtran, two-column) distilled from the thesis — **hand-maintained**; shares `figures/` and `references.bib`. Authors: A. Parganiha (CSE) and K. G. Atram (DSAI), IIIT Naya Raipur |
| `references.bib` | Bibliography — 28 entries, each verified against its arXiv / publisher page, every one cited inline |
| `BUILD.md` | How to compile (Overleaf or local), how to swap in the institute template |
| `TABLES.md` | Every result table + architecture facts, ready to convert |
| `../RESULTS.md` | Consolidated results with reproduce commands |
| `../docs/PROJECT_CONTEXT.md` | The "why" / motivation background |
| `../HANDOFF.md` | Engineering state, file map, gotchas |
| `../WORKLOG.md` | Day-by-day record (useful for the methodology chapter) |

## The one-line story (for the abstract)

What selective decoding gains **depends on the stream it reads**. On clean streams,
adaptive *placement* wins where the stream is redundant (≈1.6× COIN, ≈2.5× EgoExo4D
keysteps) and loses at every budget on *raw* atomic annotations (~1 event / 2 s).
On the **predicted** stream over those same atomic annotations, with an in-domain
predictor, adaptive beats single-point uniform decoding at 7/8 budgets — but a
uniform baseline with the **same pooling** matches it (6/8 ties, one significant
win each way, and the best score belongs to pooled uniform). The gain on a
predicted stream is **averaging, not placement**, and the benchmark barely rewards
timing: one caption per take scores about as well as uniform at 0.2 Hz.

## Figures (in `figures/`) → thesis section

### Core narrative
| Figure | Thesis § | Caption idea |
|---|---|---|
| `results_coin_gt.png` | §6.1 | COIN gt-mode Pareto: adaptive vs uniform (≈1.6×) |
| `results_egoexo_keystep.png` | §6.1 | EgoExo4D keysteps Pareto (≈2.5×; *not* the paper's benchmark — that is atomic descriptions, §6.7–6.8) |
| `results_ablation_methods.png` | §6.2 | Method ablation incl. the online-trigger correction |
| `results_coin_predictor.png` | §6.3 | Predictor-in-the-loop Pareto: the mid-band where uniform wins |
| `results_coin_predictor_c1final.png` | §6.5 | Full predicted pipeline, final checkpoint |
| `results_coin_predictor_c1old.png` | §6.5 | Same protocol, weaker checkpoint — the data-scaling contrast |
| `demo_adaptive.mp4` / `demo_uniform.mp4` | §6.4 | Live demo: adaptive 5% vs uniform 10% decodes |

### Placement on clean streams, averaging on predicted ones
| Figure | Thesis § | Caption idea |
|---|---|---|
| `results_egoexo_atomic_218.png` | §6.7 | Atomic descriptions, **clean GT** stream: uniform wins 8/8 — the redundancy limit |
| `results_egoexo_predictor_40_indomain_pooled.png` | **§6.8** | **HEADLINE.** Same benchmark, *predicted* stream: adaptive beats plain uniform 7/8, uniform+pool matches adaptive (higher at 6/8); the cross is one decode per take |
| `results_egoexo_predictor_40_indomain_semantic_pooled.png` | §6.8 | Semantic metric with the matched baseline: uniform+pool just above adaptive at every budget |
| `results_egoexo_predictor_40_indomain_semantic_nopool_pooled.png` | §6.8 | Pooling off but smoothing on: adaptive's flat lead over plain uniform vanishes against equally smoothed uniform — the margin was the smoothing |

### Rigor
| Figure | Thesis § | Caption idea |
|---|---|---|
| `results_egoexo_rigor.png` | **§6.9** | Paired (adaptive − baseline) per budget, 95% bootstrap CIs, against uniform (blue) and uniform+pool (orange) |
| `results_egoexo_ceiling.png` | **§6.9** | The semantic metric against its best-window bound: one decode per take (90.0%) scores above every adaptive budget (87.1%) — the bound cannot rank triggers |

### Rejected artifact — keep, the original §6.8 controls were defined against it
| Figure | Thesis § | Caption idea |
|---|---|---|
| `results_egoexo_predictor_40_semantic.png` | §6.8 controls | Out-of-domain predictor: the apparent 8/8 win whose controls exposed it as denoising, not selection |
| `results_egoexo_predictor_40_semantic_nopool.png` | §6.8 controls | The same run with pooling off — the advantage collapses, which is why it was rejected |

### Provenance — the earlier two-schedule versions (not placed in the thesis)
`results_egoexo_predictor_40_indomain.png`, `..._indomain_semantic.png`,
`..._indomain_semantic_nopool.png`: the uniform-vs-adaptive plots the 2026-08
headline was built on. Their numbers are unchanged; the `_pooled` files add the
matched baseline.

## Raw data (in `figures/`, for regenerating plots/tables)
Every `.png` above ships with its `.json`. Additionally:
`results_ablations.json`, `results_adaptive_tuning.json` (§6.3 tuning sweep),
`results_egoexo_rigor.json` (per-take scores + paired bootstrap vs uniform, 8 budgets),
`results_egoexo_rigor_pooled.json` (the same plus uniform+pool and one-decode-per-take,
paired against both baselines),
`results_egoexo_predictor_40_indomain_semantic_pooled_smooth1.json` (the semantic
comparison with pre-smoothing off),
`results_egoexo_rigor_oracle_fixed.json` (GT-boundary reference, 3 budgets),
`results_egoexo_ceiling.json` (per-take dense / best-frame / best-window).

## Regenerating the §6.8–6.9 results and figures
```bash
python -m livejepa.run_eval --dataset egoexo --mode predictor --gt-source atomic \
    --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 \
    --methods uniform,adaptive,uniform_pool,take_mean \
    --decode-cache eval_data/decode_cache_egoexo_indomain.jsonl \
    --out results_egoexo_predictor_40_indomain_pooled
python scripts/eval_rigor.py   --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 \
    --methods uniform,adaptive,uniform_pool,take_mean --boot 5000 \
    --out results_egoexo_rigor_pooled
python scripts/eval_ceiling.py --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360
python scripts/make_thesis_figures.py --rigor results_egoexo_rigor_pooled.json
```

## To format later
The LaTeX conversion is **done** — see `BUILD.md`. Fastest path: upload
`livejepa_thesis_overleaf.zip` (built by `scripts/make_overleaf_zip.py`) to
Overleaf and compile with pdfLaTeX. Figures are placed, tables are numbered and
captioned, and the bibliography is verified and cited inline; what remains is
swapping the preamble for the institute's template (`BUILD.md`).

**Three things to carry into the viva.** (1) The negative in §6.7 and the result
in §6.8 are the *same benchmark*: on exactly the 40 takes, the annotated stream
favours uniform at 7/8 budgets and the predicted stream favours adaptive over
*plain* uniform at 7/8 — but against uniform with the same pooling, adaptive ties.
Expect "did you pool your uniform baseline like the paper?" and answer with Table
9: yes, and that is the finding. (2) Why the earlier controls missed it: the
no-pooling control still smoothed the adaptive stream alone (§6.8, Table 10) — a
control is only as good as the match between its arms. (3) "What next" is
predictor capacity and in-domain data (the 25× in-domain gain, §6.5's
still-climbing curve), plus an evaluation that rewards timing — not trigger
tuning (§6.3, negative).
