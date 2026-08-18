# Thesis Materials — index

Everything needed to format the thesis, in one place. Prose draft is
`docs/THESIS.md`; tables are `TABLES.md` (here); artifacts are in `figures/`.

**Last refreshed 2026-08-02** — after the ceiling/headroom analysis closed the
experimental programme. All planned experiments are complete; what remains is
formatting.

## Documents
| File | What it is |
|---|---|
| `../docs/THESIS.md` | Full thesis draft (prose, all sections) — **the working copy; edit this** |
| `thesis.tex` | LaTeX main file: preamble, title page, bibliography. Hand-written, safe to edit |
| `thesis_body.tex` | **GENERATED** from THESIS.md by `scripts/md_to_latex.py`. Never hand-edit |
| `references.bib` | Bibliography — **every entry needs verifying before submission** |
| `BUILD.md` | How to compile (Overleaf or local), how to swap in the institute template |
| `TABLES.md` | Every result table + architecture facts, ready to convert |
| `../RESULTS.md` | Consolidated results with reproduce commands |
| `../docs/PROJECT_CONTEXT.md` | The "why" / motivation background |
| `../HANDOFF.md` | Engineering state, file map, gotchas |
| `../WORKLOG.md` | Day-by-day record (useful for the methodology chapter) |

## The one-line story (for the abstract)

Selective decoding's benefit is a **monotone function of the stream's temporal
redundancy**, and it needs a **predicted** stream rather than dense labels. On
coarse streams it wins (≈1.6× COIN, ≈2.5× EgoExo4D keysteps); on *raw* atomic
annotations (~1 event / 2 s) it loses at every budget; but on the **predicted**
stream over those same atomic annotations, with an in-domain predictor, it wins
7/8 budgets at **≈9.9× fewer decodes** — significant at every budget over 40
held-out takes — and reaches **87% of a provable upper bound**, while *beating
decode-everything at ~40× lower cost*. The residual gap belongs to the predictor,
not the trigger.

## Figures (in `figures/`) → thesis section

### Core narrative
| Figure | Thesis § | Caption idea |
|---|---|---|
| `results_coin_gt.png` | §6.1 | COIN gt-mode Pareto: adaptive vs uniform (≈1.6×) |
| `results_egoexo_keystep.png` | §6.1 | EgoExo4D keysteps Pareto (≈2.5×; paper's benchmark) |
| `results_ablation_methods.png` | §6.2 | Method ablation incl. the online-trigger correction |
| `results_coin_predictor.png` | §6.3 | Predictor-in-the-loop Pareto: the mid-band where uniform wins |
| `results_coin_predictor_c1final.png` | §6.5 | Full predicted pipeline, final checkpoint |
| `results_coin_predictor_c1old.png` | §6.5 | Same protocol, weaker checkpoint — the data-scaling contrast |
| `demo_adaptive.mp4` / `demo_uniform.mp4` | §6.4 | Live demo: adaptive 5% vs uniform 10% decodes |

### The negative, and its resolution
| Figure | Thesis § | Caption idea |
|---|---|---|
| `results_egoexo_atomic_218.png` | §6.7 | Atomic descriptions, **clean GT** stream: uniform wins 8/8 — the redundancy limit |
| `results_egoexo_predictor_40_indomain.png` | **§6.8** | **HEADLINE.** Same benchmark, *predicted* stream, in-domain predictor: adaptive wins 7/8, ≈9.9× |
| `results_egoexo_predictor_40_indomain_semantic.png` | §6.8 | Style-robust semantic metric on the same takes |
| `results_egoexo_predictor_40_indomain_semantic_nopool.png` | §6.8 | Pooling disabled — isolates temporal *selection* from denoising |

### Rigor (new, 2026-08)
| Figure | Thesis § | Caption idea |
|---|---|---|
| `results_egoexo_rigor.png` | **§6.9** | Paired (adaptive − uniform) per budget, 95% bootstrap CIs. All 8 semantic budgets clear zero; the single ns CIDEr cell is circled |
| `results_egoexo_ceiling.png` | **§6.9** | Headroom: adaptive at 87.1% of the best-window upper bound, *above* decode-everything and above the GT-boundary reference |

### Rejected artifact — keep, the controls chapter needs it
| Figure | Thesis § | Caption idea |
|---|---|---|
| `results_egoexo_predictor_40_semantic.png` | §6.8 controls | Out-of-domain predictor: the apparent 8/8 win whose controls exposed it as denoising, not selection |
| `results_egoexo_predictor_40_semantic_nopool.png` | §6.8 controls | The same run with pooling off — the advantage collapses, which is why it was rejected |

## Raw data (in `figures/`, for regenerating plots/tables)
Every `.png` above ships with its `.json`. Additionally:
`results_ablations.json`, `results_adaptive_tuning.json` (§6.3 tuning sweep),
`results_egoexo_rigor.json` (per-take scores + paired bootstrap, 8 budgets),
`results_egoexo_rigor_oracle_fixed.json` (GT-boundary reference, 3 budgets),
`results_egoexo_ceiling.json` (per-take dense / best-frame / best-window).

## Regenerating the two new figures
```bash
python scripts/eval_rigor.py   --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 \
    --methods uniform,adaptive --boot 5000 --out results_egoexo_rigor
python scripts/eval_ceiling.py --ckpt checkpoints_egoexo/predictor_20000.pt \
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360
python scripts/make_thesis_figures.py
```

## To format later
The LaTeX conversion is **done** — see `BUILD.md`. Fastest path: upload
`thesis.tex`, `thesis_body.tex`, `references.bib` and `figures/` to Overleaf,
set the main document to `thesis.tex`, compile. Then swap the preamble for the
institute's template, place the figures, and verify the bibliography.

**Two things to carry into the viva.** (1) The negative in §6.7 and the positive
in §6.8 are the *same benchmark* differing only in whether the stream is
annotated or predicted — that pairing is the contribution, so keep them adjacent.
(2) §6.9's ceiling says the trigger is close to exhausted; if an examiner asks
"what next", the answer is predictor capacity and in-domain data (§6.5's curve
was still climbing), not trigger tuning (§6.3, negative).
