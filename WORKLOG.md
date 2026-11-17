# LiveJEPA — Daily Worklog

Maintained by Claude, one entry per working day (newest first). Each entry: what was
done, key numbers, decisions, and what's queued next. Entries before 2026-07-16 are
backfilled summaries.

---

## 2026-11-17 (Tuesday)

**Theme: a fresh-session review of the whole project, after seven weeks idle,
found that the headline's uniform baseline was never pooled. Adaptive decodes
segment means of a smoothed stream, and VL-JEPA pools both schedules. Against a
pooling-matched uniform the headline does not hold. Everything was measured
read-only in the session scratchpad; the only repo change is this entry.**

### State re-verified
- Still the college T1000 machine. All caches and checkpoints are on disk, and
  the GPU was free. `pytest tests/ -q`: 13/13.
- Git is as 09-30 left it: 13 modified files plus 2 untracked
  (`reference paper/`, `thesis_materials/paper_ieee.tex`), all uncommitted.
  `thesis.pdf` (32 pp) and `paper_ieee.pdf` (12 pp) are current with their sources.
- `LiveJEPA_KaggleAutopilot` is **still enabled**. It attempted a run today at
  17:28 (result 0x800710E0) and is next due 2026-11-18 12:00. Its last successful
  5.2 GB re-download of `coin_cache_p7.tar` was 2026-10-07. Not disabled (user's call).

### Finding: the uniform baseline was never pooled
- In code, `select_points('uniform')` decodes single raw stream points. Adaptive
  decodes the mean of each Ward segment of the 3-step-smoothed stream.
- VL-JEPA section 4.6 (read from the PDF in `reference paper/`): decoding uses
  "either the exact embedding or the average-pooled embedding within the
  segment", and "average pooling provides consistent gains for both strategies".
  The paper's uniform baseline is pooled; ours never was. (On 09-30 I read the
  same sentence as support for our setup and missed this.)
- The "no-pooling" control is not exact-point either. With `pool=none`, adaptive
  still decodes points of the *smoothed* stream while uniform decodes raw ones.
  THESIS 6.8 and paper_ieee.tex:962-965 describe it as exact points and conclude
  "temporal selection, not pooling, carries the margin".
- **The harness was validated first.** Before any new number was trusted, it
  reproduced every published value exactly:
  - three semantic curves (uniform, adaptive, no-pool), to 4 dp at all 8 budgets;
  - the rigor run's per-take means, exactly;
  - all 10 CIDEr cells (both methods at 5 budgets), from a scratch *copy* of
    `decode_cache_egoexo_indomain.jsonl`.
- "uniform+pool" below means fixed blocks of length `stride`, mean-pooled, with
  the same count and the same timestamps as uniform, and the same smoothing as
  adaptive.

**Semantic metric (40 takes):**
- No-pool control with equal smoothing on both sides: -0.0025 to +0.0028.
  Published, with smoothing on adaptive only: +0.031 to +0.040. With no
  smoothing on either side: -0.0048 to +0.0083.
- uniform+pool beats adaptive at 8/8 budgets, and the paired bootstrap is
  significant at 8/8: from -0.0013 [-0.0019, -0.0007] at 1 Hz to -0.0111
  [-0.0179, -0.0052] at 0.01 Hz. Only 1-12 of 40 takes favour adaptive.
- **One decode per take** (the whole-take mean) scores **0.6950**. That is above
  adaptive at every budget (its best is 0.6825) and 90.0% of the 0.7720 "ceiling".
  The metric rewards averaging itself.

**CIDEr, the sparse half (corpus CIDEr; per-take paired bootstrap of adaptive
minus uniform+pool):**

| Hz | decodes | uniform | adaptive | uniform+pool | adaptive - (uniform+pool), 95% CI | takes |
|---:|---:|---:|---:|---:|---|---:|
| 0.20 | 1412 | 0.2873 | 0.3330 | **0.3410** | -0.0026 [-0.0124, +0.0083] ns | 15/40 |
| 0.10 | 706 | 0.2820 | 0.3315 | **0.3381** | -0.0062 [-0.0178, +0.0054] ns | 21/40 |
| 0.05 | 357 | 0.2783 | **0.3378** | 0.3192 | **+0.0143 [+0.0057, +0.0229]** | 29/40 |
| 0.02 | 140 | 0.2493 | 0.3118 | **0.3135** | -0.0035 [-0.0168, +0.0097] ns | 13/40 |
| 0.01 | 76 | 0.3052 | 0.3024 | **0.3218** | -0.0076 [-0.0214, +0.0062] ns | 9/40 |

**One caption per take** (40 decodes in total) scores CIDEr **0.2844**, roughly
plain uniform at 0.2 Hz (0.2873 with 1,412 decodes). On this benchmark,
time-aligned CIDEr barely rewards timing.

### What it means
- **Against a pooled uniform, adaptive wins at one budget only.** It is
  significantly better at 1 of the 5 sparse budgets (0.05 Hz). The other 4 are
  statistical ties, and uniform+pool is numerically ahead at all 4.
- **The 9.9x claim does not hold against the fair baseline.** It is anchored on
  plain uniform. The best pooled-uniform score so far is 0.341, at 1,412 decodes.
  Adaptive first exceeds that at 0.5 Hz (0.348, 3,537 decodes). The dense half
  (1.0/0.5/0.35 Hz, about 13k decodes) is not yet run for uniform+pool.
- **Most of the gain over plain uniform is averaging.** The predicted stream is
  noisy, and both schedules can average it. "87% of a provable ceiling" is
  weakened as an argument about trigger quality, since a schedule with no timing
  at all reaches 90%.
- **Unaffected:**
  - the reconstruction;
  - the `SegmentTrigger` fix;
  - the scaling study;
  - C2 and C3;
  - the clean-stream results (COIN 1.6x, keysteps 2.5x, the atomic-218 negative);
  - the demo.

### Doc errors that survived the 09-20 pass
- `RESULTS.md:359-360` says both metrics "agree in direction at every budget",
  which is false at 0.01 Hz.
- `RESULTS.md:574-578` still uses the label-noise framing, against the entropy
  account in the same file.
- `RESULTS.md:164-165` says the definitive COIN Pareto was "bundled into C2"; it
  never was.
- The `BUILD.md` status header says 30 pp and 16 refs; the actual figures are
  32 pp and 28.
- `TABLES.md:232` says "pure temporal selection".
- HANDOFF.md still has the stale "server RUNNING" and "finish the week plan" lines.

### Later the same day: the fair baseline in the real harness, all 8 budgets
- **Snapshot.** The user approved a snapshot commit and Step 1. I created branch
  `thesis-reframe` and committed `8ea0da6`: the 13 modified files plus
  `paper_ieee.tex`. `reference paper/` is deliberately left untracked, because it
  holds a colleague's paper and an arXiv PDF. `main` is untouched and still equals
  `origin/main` (682c5db).
- **Code changes (on the branch, not yet committed):**
  - `select_points` gains `uniform_pool`: uniform placement with adaptive's
    smoothing and pooling, using blocks from the new `eval_pareto.uniform_blocks`.
  - `select_points` gains `take_mean`: one decode per video, as a reference.
  - `run_eval --methods`, with the default unchanged.
  - V-JEPA 2 now loads only when a stream actually has to be built.
  - The SonarSpace encoder now loads lazily, like the decoder. Decode-only work
    then fits the 8 GB T1000, at about 145-230 decodes/min.
  - `eval_rigor` pairs adaptive against every baseline that was run. The
    `paired_adaptive_minus_uniform` key is unchanged; a new
    `paired_adaptive_minus_uniform_pool` key sits beside it.
  - `eval_semantic_pareto --methods`; extras must come after the defaults so the
    shared RNG still reproduces the published curves.
  - Tests: 13 -> 16, all passing.
- **Regression checks:**
  - Semantic curves, with pool `mean` and `none`, are bit-exact against the
    published files, including the shuffled floor and random placement.
  - `uniform_pool` is bit-exact against the scratch run.
  - All 16 published CIDEr cells reproduce.
  - eval_rigor's adaptive-minus-uniform table reproduces exactly.
- **Decode cache.** I backed it up to the scratchpad, then appended the 2,626
  scratch decodes after checking that the scratch copy extends it byte for byte.
  The run grew `decode_cache_egoexo_indomain.jsonl` from 29,960 to 40,850 entries
  (about 63 min of decoding).

**Headline benchmark: corpus CIDEr, 40 takes, plus a per-take paired bootstrap of
adaptive minus uniform+pool:**

| Hz | decodes | uniform | adaptive | uniform+pool | adaptive - (uniform+pool), 95% CI | takes |
|---:|---:|---:|---:|---:|---|---:|
| 1.00 | 7072 | 0.296 | 0.330 | **0.335** | -0.0055 [-0.0157, +0.0028] ns | 21/40 |
| 0.50 | 3537 | 0.310 | **0.348** | 0.342 | -0.0004 [-0.0087, +0.0073] ns | 24/40 |
| 0.35 | 2357 | 0.299 | 0.340 | **0.358** | **-0.0113 [-0.0203, -0.0024]** | 11/40 |
| 0.20 | 1412 | 0.287 | 0.333 | **0.341** | -0.0026 [-0.0124, +0.0083] ns | 15/40 |
| 0.10 | 706 | 0.282 | 0.331 | **0.338** | -0.0062 [-0.0178, +0.0054] ns | 21/40 |
| 0.05 | 357 | 0.278 | **0.338** | 0.319 | **+0.0143 [+0.0057, +0.0229]** | 29/40 |
| 0.02 | 140 | 0.249 | 0.312 | **0.314** | -0.0035 [-0.0168, +0.0097] ns | 13/40 |
| 0.01 | 76 | 0.305 | 0.302 | **0.322** | -0.0076 [-0.0214, +0.0062] ns | 9/40 |

`take_mean`, one caption per take with 40 decodes in total, scores corpus CIDEr
0.284 and semantic 0.6950. On the semantic metric uniform+pool is significantly
better than adaptive at 8/8 budgets.

**Verdict.**
- Against the like-for-like baseline, adaptive is significantly better at 1/8
  budgets (0.05 Hz), significantly worse at 1/8 (0.35 Hz), and tied at 6/8.
- On corpus CIDEr, uniform+pool is higher at 6/8.
- Its best score (0.358, 2,357 decodes) is above adaptive's best anywhere (0.348),
  so the "9.9x fewer decodes" claim cannot be restated against it.
- The published gain over plain uniform (+0.03 to +0.06) is the averaging, which
  gives +6% to +26% CIDEr at every budget. Adaptive placement adds nothing
  consistent on top.
- VL-JEPA's "adaptive Pareto-dominates even with pooling on both" does not
  replicate in our reconstruction.

Outputs are gitignored at the root:
- `results_egoexo_predictor_40_indomain_pooled.{json,png}`
- `results_egoexo_rigor_pooled.json`
- `logs/run_eval_pooled_20261117.log` and `logs/eval_rigor_pooled_20261117.log`

### Paper author block filled
The user supplied his guide's profile and his own details. The block uses the
institute's format, taken from a colleague's IIIT-NR paper:
- **A. Parganiha:** Department of Computer Science and Engineering, IIIT Naya
  Raipur, 493661 India, aman25300@iiitnr.edu.in.
- **K. G. Atram:** Department of Data Science and Artificial Intelligence, IIIT
  Naya Raipur, gaurav@iiitnr.edu.in. He is now listed by his full name, "Kumar
  Gaurav Atram".

### Later still: Step 2, the reframe, drafted for review
The user approved committing Step 1 (`35f7b01`) and starting Step 2. The Step 2
work is **uncommitted** on `thesis-reframe`, waiting for review.

**Thesis** (`docs/THESIS.md` -> `thesis_body.tex`):
- **Rewritten:** the abstract and contributions 5-6.
- **New material:**
  - §2 now states that VL-JEPA pools under both schedules.
  - §3 gains a caveat on the semantic metric.
  - §4.3 defines the baselines (uniform+pool, and one decode per take).
- **Cross-references fixed** in §5, §6.1, §6.3 and §6.7.
- **§6.8 rewritten** as "The predicted stream: averaging, not placement", with
  a three-schedule table and a "why the original controls missed this"
  paragraph.
- **§6.9 rewritten:**
  - a new paired table against both baselines;
  - the ceiling table gains two rows;
  - its third finding is now "the bound cannot rank triggers".
- **§7-9 rewritten.** The methodological note now lists four positive results
  that failed their controls. Future work adds an evaluation that rewards timing.
- **Appendix A:** new commands, and tests 16/16.
- **Appendix B:** the figure map is updated.
- `check_thesis_tex.py` PASS: 14 figures, 22 labels, 30 refs, 11 tables, 28
  citations.

**IEEE paper:**
- Rewritten: the abstract, the contributions, the method (baselines defined,
  Fig. 2 caption), the headline section, the controls, the significance section
  (new `tab:sigpool`), the headroom section, and the discussion, limitations,
  future work and conclusion.
- `fig:ablation`, `fig:rigor` and `fig:ceiling` were never referenced (they
  weren't in the snapshot either); they are now.
- A scratch static check passes: 40 labels, 36 refs, 13 figure files, 27
  citation keys, balanced environments and braces, ASCII.

**Supporting docs:**
- RESULTS.md §5b is rewritten. Its intro claim, the §5 forward reference, the
  stale §3b C2 note, the §6b label-noise framing and §7 are fixed.
- README: the headline is rewritten.
- TABLES.md: Tables 9-12 are rewritten.
- INDEX.md is rewritten.
- BUILD.md status: last compiled 09-20 (32 pp, 28 refs); a rebuild is needed.
- HANDOFF.md gets an update block, and its stale lines are fixed.
- All five audit doc errors from this morning are now gone.

**Web app:**
- `index.html`: the "up to 9.9x" chip is now "up to 2.5x" on redundant streams,
  and its footnote is rewritten.
- `about.html`: new KPI cards, a rewritten headline finding, a 5-bar chart that
  adds fixed-interval pooled, and a rewritten result finding.

**Figures:**
- `make_thesis_figures.py`:
  - the paired figure plots both baselines;
  - the headroom figure adds uniform+pool and one decode per take;
  - the ceiling bars are recoloured purple to stay distinct from uniform+pool's
    orange.
- New curated files in `figures/`:
  - `*_pooled.{json,png}`;
  - `results_egoexo_rigor_pooled.json`;
  - `..._semantic_pooled_smooth1.{json,png}`.

**Verification:**
- **368 numeric cells** across THESIS, RESULTS, TABLES and the paper were
  machine-checked against their JSON sources at the printed precision. All
  match.
- **Negative control:** four perturbations were injected into the sources, and
  each was caught in every document that prints that value. The first version of
  the checker silently skipped the bold `take_mean` row; it now reports any row
  it cannot find.
- Old-headline phrases grep clean everywhere except the WORKLOG.

**PDF build.** The first Tectonic download was denied by the permission system.
The user then approved it, and Tectonic 0.17.0 went into the scratchpad (nothing
installed, nothing in the repo).
- **Thesis:** the first build of the new text exited 0, but the new paired table
  overran the page by **169.8pt**: five long bold headers. It is now a raw-LaTeX
  block with a two-level header ("vs uniform" / "vs uniform+pool" over
  semantic / CIDEr) in `\small`. The checker was taught to read it, and the
  negative control still catches perturbations there.
- **Final thesis build:** exit 0, **0 overfull**, 0 undefined, 0 errors,
  **34 pages**. The remaining underfull warnings are cosmetic, mostly Appendix
  B's long file names.
- **Paper:** exit 0, 0 overfull, 0 undefined, **13 pages** (was 12; the extra
  page is the new table).
- **Extracted PDF text:** no `??`, no leaked LaTeX, no control characters, and
  every remaining "9.9x" is in its corrected context.
- **Page by page:** I read thesis pp. 15-23 and paper pp. 1 and 8-12. The tables,
  the three-curve headline figure, the controls, the significance and headroom
  figures, the author block and the conclusion all render correctly.
- **Overleaf zips:** both were rebuilt (thesis 1.15 MB, paper 0.78 MB). Each was
  compiled from an empty directory; exit 0, and the PDF text is identical to the
  main build.
- **Gotcha, once more:** Git Bash halves backslashes in heredocs, which mangled
  `\best` and `\textbf` in a generator's printout. Only the display was
  affected; the rows were rebuilt by hand from the printed values. Scripts with
  LaTeX go in files, via the Write tool.

**Queued next (the user decides):**
1. Review the draft (the PDFs in `thesis_materials/`) and commit Step 2 when
   happy.
2. Paperwork: template, date and declaration.
3. The viva deck.
4. Disable the autopilot task.

---

## 2026-09-30 (Wednesday)

**Theme: the IEEE paper restyled against two reference PDFs the user supplied --
the real VL-JEPA paper and a colleague's paper -- plus the first chance to check
our VL-JEPA claims against the source rather than against web fetches.**

### The source paper confirms what we wrote about it
`reference paper/2512.10942v2.pdf` is the actual VL-JEPA paper. Verified directly:
- "selective decoding at 0.35 Hz (i.e., 2.85s interval) matches the performance of
  uniform decoding at 1 Hz" and "adaptive selection consistently Pareto-dominates
  uniform sampling" -- our description and our "no crossover" contrast are right.
- "218 videos with an average duration of 6 minutes and about T = 143 atomic
  action annotations per video" -- matches.
- Agglomerative clustering with temporal-connectivity constraints, segments of
  high intra-segment monosemanticity measured by Ward distance, **decoded at the
  segment midpoint** -- the same choice we made independently.
- Predictor initialised from **layers 8-16 of Llama-3.2-1B** (490M); Y-Encoder is
  EmbeddingGemma-300M. Both now stated in Related Work.
- The paper itself stabilises the stream "with simple smoothing" before detection
  and reports average pooling helps both schedules. That is worth knowing: our
  smoothing disclosure describes a setting the original method also uses, and our
  pooling control isolates what the paper assumes.

### Restyle (format only -- no content taken from the colleague's paper)
- Author line is now `Aman Parganiha, and Gaurav Atram`, journal-style, with
  affiliations as `\thanks` footnotes, matching the reference layout. Department,
  institute, city and the `\markboth` venue remain TODO.
- **Two TikZ figures added**: Fig. 1, the architecture (frozen components grey,
  the trained predictor tinted, the training-only branch boxed); Fig. 2, what
  uniform and adaptive do with the same budget on a stream of plateaus. Both are
  drawn in the .tex so the user can edit them, and both are wrapped in
  `\resizebox` after the first draft of Fig. 1 ran 86pt past the text width.
- Winning cells in the headline, same-takes and ceiling tables now use a tinted
  `\best{}` macro, as the reference paper highlights its best numbers.
- Still 12 pages, 0 errors, 0 overfull. All **287 numeric cells re-verified** after
  the restyle (the checker needed teaching about `\best{}`). The Overleaf zip was
  rebuilt and re-validated by compiling it from an empty directory.

Later the same day, on the user's request, the running head
("PREPRINT -- TODO: TARGET VENUE, 2026") was removed from every page:
`\markboth{}{}`, so pages carry only a page number, as the reference paper does.
The commented line above it restores a venue banner in one edit. Rebuilt: 12
pages, 0 errors, 0 overfull, 287 cells still verifying. (The word "preprint" still
appears seven times on the last page -- inside "arXiv preprint arXiv:..." in the
bibliography, which is correct.)

**Queued next (user):** fill the author placeholders; commit when happy.

---

## 2026-09-20 (Sunday)

**Theme: the thesis fix pass, on the user's "fix the thesis". Every defect from
yesterday's audit is fixed. Verifying the fixes by measurement rather than by
reading turned up four more wrong numbers, one wrong framing, and a bound whose
"provable" label needed re-proving.**

### What changed in `docs/THESIS.md` (and therefore the PDF)
- **The paper is described correctly** (§1, §2, §3, §6.1), checked against the
  arXiv HTML of 2512.10942. Its selective-decoding benchmark is EgoExo4D atomic
  descriptions (218 videos, ~143 annotations each). Its 2.85x means "selective at
  0.35 Hz matches uniform at 1 Hz". It reports no crossover anywhere in 0.01–2 Hz.
  Keysteps are no longer called the paper's benchmark, and 2.5x is no longer set
  against 2.85x. §1 also claimed the paper "glosses over" predicted streams; its
  headline is on a predicted stream, so that sentence is rewritten.
- **Significance** (abstract, §1, §6.9, §9, README, INDEX, RESULTS): the semantic
  metric is significant at 8/8 budgets and CIDEr at 7/8. At 0.011 Hz the CIDEr
  difference is null (−0.002, CI [−0.037, +0.031], 19/40 takes).
- **Complete tables:** COIN-gt now has 8 rows, keysteps 7, §6.3b 8, atomic-218 8,
  and the headline 8 (including the one uniform win). "Pareto dominance" becomes
  "mid-band dominance" wherever the data says so.
- **Pre-smoothing disclosed** in §4.3, §6.3, §6.5, §6.8, §8 and Appendix A:
  `smoothing_window = 3` applies from §6.5 on, and §6.1–6.3 are un-smoothed. It
  also explains why the same checkpoint has two adaptive curves.
- **Smaller fixes:**
  - The in-domain predictor used 627 takes, not 721.
  - The optimiser is AdamW with cosine decay and batch 32.
  - The §6.5 caption now compares like for like (0.846 vs 0.667).
  - §6.7 is no longer in future tense, and its claim to be "exact" is gone.
  - The 9.9x anchor is explained: the paper's rule would give a meaningless ~93x,
    and adaptive at 0.020 Hz (≈25x) is within noise.
  - EmbeddingGemma is named, and VL-JEPA's own decoder is described.
  - The web app is described in §6.4.
  - The session overlap is disclosed in §8 and added to future work.
- **The PDF defects:** the rejected-artifact figure no longer splits a sentence,
  and the VL-JEPA entry is now an article, so its arXiv id prints.
- **Formatting:**
  - The bibliography has 16 entries, 8 of them new; each new one was checked against
    its arXiv or publisher page. All are cited inline and there is no `\nocite{*}`.
  - The 10 tables are numbered and captioned.
  - All 21 floats are referenced from the text.
  - There is a List of Figures (with short captions) and a List of Tables.

### New measurements (scratch scripts in the job dir; no repo data touched)
- **Scaling confound:** the final run's 20k-step checkpoint scores 0.882 / 0.832 /
  0.394. At matched 20k steps, +0.099 of the +0.113 gain is data and +0.014 is the
  extra steps. The frozen-137 set saturates (0.883 → 0.882). All 9 published
  scaling cells re-derive exactly on the "956" set, which is the files in
  `data_cache_coin_full_val` that predate the 2026-07-19 late merge. The directory
  now holds 977, so `eval_predictor.py` there prints 0.844 rather than 0.846;
  Appendix A says so.
- **Headline without smoothing, semantic metric:** recomputing with w=3 reproduces
  the published numbers exactly. With w=1, adaptive still wins 8/8, by +0.013 at
  1 Hz rising to +0.102.
- **Headline without smoothing, CIDEr:** the harness first reproduced the published
  0.05 Hz cell exactly (0.33781). With w=1, adaptive wins the **same 7/8 budgets**
  and loses 0.011 Hz as before. The key 9.9x cell is unchanged (0.3379 vs 0.3378).
  Only the two highest rates narrow: 1 Hz 0.3065 vs 0.2956, and 0.5 Hz 0.3196 vs
  0.3098 (≈+0.010, against ≈+0.035 smoothed). The 0.2–0.1 Hz cells are slightly
  *higher* unsmoothed.
- **Ceiling with smoothing:** the raw ceiling does not strictly bound smoothed
  adaptive. The smoothed-stream ceiling is 0.7661, and the per-annotation union
  is 0.7721 against 0.7720, so the "provable" claim holds and every percentage
  is unchanged.
- **Action100M, C3 and vocabulary tables:** all re-derive exactly, except C3's
  COIN-956, which is 0.824 (the published 0.823 was measured on the 977-file dir).
- **The GT stream on exactly the 40 headline takes**, rebuilt as `run_eval` does and
  looked up in the atomic-218 run's decode cache:
  - **§6.7 used smoothing 3.** All 15,843 w=3 adaptive keys are in the cache. Only
    12,693/15,843 w=1 keys are, and the missing ones are the blended means an
    un-smoothed run would have decoded.
  - **Same takes, the stream is the only difference.** The GT stream favours
    uniform at 7/8 budgets (adaptive only at 0.20 Hz, 2.381 vs 2.352), while the
    predicted stream favours adaptive at 7/8. §6.8, §7, the Figure 7 caption and
    the INDEX viva note now say so. The earlier text had said "differing only in
    the stream" across 218 vs 40 takes.

### Four more wrong numbers, caught by checking at printed precision
Yesterday's audit said "every printed value matches". It was eyeballing values at
4 decimals, and that was not good enough. The machine check (118 cells) found:
1. COIN-gt 0.35 Hz adaptive is 8.67 (source 8.674699), not 8.68.
2. Atomic-218 0.10 Hz adaptive is 1.60 (1.604963), not 1.61.
3. C3's COIN-956 is 0.824 on the fixed set. Also, "no better than COIN alone on
   A100M" was false against C1-final (0.390 vs 0.386).
4. TABLES.md had its own errors:
   - It listed C1-final as trained on 26,863 clips; the real figure is 26,360.
   - The 25.3x caveat pointed at the wrong row.
   - "Curated labels beat noisy ones" contradicted the entropy account.
   - The out-of-domain effect was 59% denoising, not 58%.

### Tooling
- `md_to_latex.py`: a `Table: caption {#tab:x}` line now makes a numbered table
  float, and a `~` before `\ref`/`\cite` is kept as a tie. Regression-checked:
  unchanged markdown gives byte-identical output.
- `check_thesis_tex.py` now fails on:
  - unreferenced floats;
  - cite keys missing from the .bib;
  - .bib entries that are never cited;
  - any at-sign in the .bib outside an entry header.
- `thesis.tex`:
  - gains the List of Figures and List of Tables;
  - sets table captions to sit above their tables;
  - uses `hypertexnames=false`, which removes the duplicate-anchor warnings;
  - loses a stale "SECTIONLEVEL" pointer.
- **Two of my own mistakes, caught before they shipped.** An at-sign in my new .bib
  header comment made BibTeX skip "entries" (BibTeX has no comment syntax, so this
  is now a check). And I had written "nine" new entries where there are eight.

### Build
Tectonic 0.17.0 was re-downloaded to the job scratch dir (nothing installed). The
final build is clean:
- exit 0, with **0 errors, 0 overfull boxes, 0 undefined refs or cites**, and
  BibTeX silent;
- **30 pages**: 4 unnumbered front matter plus 26 numbered;
- all 114 auto-checked table cells, and the GT-boundary row, match their sources
  at the printed precision;
- the mechanical PDF-text checks pass.

`livejepa_thesis_overleaf.zip` (0.86 MB) was validated by compiling it from an
empty directory, and its text matches the main build. 13/13 tests pass. Nothing
is committed: the diff (12 files) is left for the user's review.

### Operational gotcha
The first background eval crawled at 12 decodes/min. `run_eval` in predictor mode
loads V-JEPA 2 even when every stream is cached, and SONAR loads encoder and
decoder in fp32 (≈3 + 5.5 GB), which overflows the 8 GB T1000 into shared memory.
A decode-only script that releases the encoder runs at ~190/min.

### Later the same day: related work, abstract, and an IEEE paper
On the user's "fix all the mistakes and make paper in IEEE format":
- **Related work is now a real section.** Twelve references added (dense and
  streaming captioning, the JEPA lineage, event boundaries, action segmentation,
  change-point detection, token merging, BERTScore, CLIPScore), each verified
  against its arXiv page the same day. The bibliography is 28 entries, all cited.
  LeCun's position paper was dropped: OpenReview served a bot check, and an
  unverified entry is not worth the line.
- **The abstract is 427 words, down from 548.** Every claim survives, including
  the crossover caveat and the COIN mid-band.
- **`thesis_materials/paper_ieee.tex`**: an IEEEtran two-column paper distilled
  from the thesis, sharing `figures/` and `references.bib`. Written first as a
  6-page conference paper, then extended on request to **12 pages in journal
  format**: 16 tables, 13 figures, 27 references. The extension is all material
  the 6-page version compressed into single sentences — the method ablation and
  the naive trigger's (W, tau) grid, the tuning sweep, the qualitative caption
  table, the same-takes control, the smoothing on/off table, and the per-budget
  significance table — plus pseudocode for the trigger and formal definitions of
  both metrics. Clean build: 0 errors, 0 overfull, no undefined citations.
  It is hand-maintained; the author block and `\markboth` carry TODO placeholders.
- **All 287 numeric cells in the paper were machine-checked** against their source
  files at the printed precision. That caught four of my own double-rounding
  errors in the significance table (e.g. +.068 where the source rounds to +.067),
  now fixed. The checker itself needed two fixes first: it could not read
  IEEE-style leading-dot decimals or nested braces in `\textbf{26{,}360}`.
- `make_overleaf_zip.py` grew a `--paper` flag; the resulting 0.72 MB zip was
  validated by compiling it from an empty directory.
- The thesis is now 32 pages and still passes every check.

**Queued next (user):**
1. Review the diff and the new PDFs, then commit and push.
2. Institute template, date, declaration, and an own-voice re-read.
3. Optionally, the participant-disjoint retrain (~1 day, ₹0).
4. The viva deck.
5. Disable the autopilot task, and clean up credentials.

---

## 2026-09-19 (Saturday)

**Theme: full completeness audit after a month idle. Code, data, archive and the
build pipeline are sound. The thesis *document* is not yet submission-ready: it has
factual and consistency defects, two typesetting defects visible in the PDF, and
structural gaps. A scheduled task has also been wasting 5.2 GB a day for two months.**

### Verified sound (re-run today rather than taken from the docs)
- `pytest tests/ -q`: **13/13** in 6 s. `py_compile` passes over livejepa/, scripts/, webapp/.
- Git clean, `main` == `origin/main` (682c5db), 137 tracked files.
- `md_to_latex.py` regenerated to a temp file: **byte-identical** to the committed
  `thesis_body.tex`. `check_thesis_tex.py` PASS. All 19 files in the Overleaf zip are
  byte-identical to the working tree.
- The tables below were checked cell by cell against their source JSON: 6.1 COIN-gt
  and keystep, 6.3b, the 6.5 Pareto panels, 6.7 atomic-218, 6.8 in-domain, the 6.9
  significance and ceiling results, and the C2 A100M gate (0.348). **Every printed
  value matches.** I did not re-derive four sets of numbers: the 6.5 cos-scaling
  values, the 6.6 C1/C3 cos values, the 6.2 ablation, and the 6.8 control deltas.
  No raw gate output for the first two is left on disk (`logs/` has none), though
  HANDOFF, WORKLOG and THESIS all agree on them. The problems below are about what
  is left out and how things are described, not about wrong numbers.
  **Correction (2026-09-20): not quite.** This check compared values by eye at 4
  decimals. A machine check at the printed precision found two rounding errors:
  COIN-gt 0.35 Hz adaptive is 8.67, not 8.68, and atomic-218 0.10 Hz adaptive is
  1.60, not 1.61. Re-deriving the skipped numbers also found C3's COIN-956 printed
  as 0.823 where the fixed 956-file set gives 0.824. All are fixed; see 2026-09-20.
- Drive archive `G:\My Drive\livejepa_archive` is present.

### Found: `LiveJEPA_KaggleAutopilot` was never switched off
It still fires daily at 12:00. Since 2026-07-21 it has downloaded the same 5.2 GB
`coin_cache_p7.tar` **42 times (~220 GB)**, overwriting `backups/coin_cache_p7.tar`
each time. This does no harm to the data, but it keeps the Kaggle token in daily
use. The six other LiveJEPA tasks are one-shot and dormant. I did **not** disable it;
that is the user's call. Fix: `Disable-ScheduledTask -TaskName LiveJEPA_KaggleAutopilot`.

### Thesis content defects (none of these is caught by the build checks)
1. **Sections 3 and 6.1 misdescribe the paper.** Checked today against the arXiv
   2512.10942 HTML: VL-JEPA's selective-decoding benchmark is EgoExo4D **atomic**
   descriptions on 218 val videos (~143 annotations each), and its 2.85x means
   "selective at 0.35 Hz matches uniform at 1 Hz". Our section 3 says keysteps are
   "the regime the paper's headline benchmark uses" and that atomic is deliberately
   not used. Section 6.1 calls keysteps "the paper's own benchmark" and sets 2.5x
   against 2.85x. Both passages were written before D.1/D.4, and they contradict
   6.7, 6.8 and the abstract.
2. **Significance is overclaimed** in the abstract and section 9 ("significant at every
   decode budget"). `results_egoexo_rigor.json` shows the semantic metric significant
   at 8/8 budgets but CIDEr at only 7/8. At 0.011 Hz the per-take CIDEr difference is
   **-0.0017** (19/40 takes), so 6.9's "agrees in direction at every budget" is also false.
3. **Some tables leave out rows.** The 6.1 COIN-gt table stops at 0.10 Hz. In the JSON,
   0.05/0.02/0.01 Hz are all uniform wins (3.77 vs 3.53, 3.54 vs 2.29, 3.46 vs 2.04),
   yet the heading says "Pareto dominance holds". The paper claims *no* crossover
   anywhere in 0.01-2 Hz, so our crossover is a finding that should be reported, not
   trimmed. The 6.8 table shows 4 of 8 budgets and leaves out the one uniform win
   (0.011 Hz: 0.305 vs 0.302).
4. **Undisclosed smoothing.** `configs/default.yaml` sets `smoothing_window: 3`.
   Every adaptive number that goes through `select_points` used it: the headline,
   rigor, ceiling, and the 6.5 COIN runs. Section 4 never mentions smoothing. This also
   explains why the thesis shows **two different adaptive curves for the same
   checkpoint on the same 7 videos**: 6.3b used smooth=1 (2.814 at 1 Hz) and the 6.5
   c1old panel used smooth=3 (2.658). The smooth3_ward row of
   `results_adaptive_tuning.json` reproduces c1old exactly. With smooth=3, adaptive
   *loses* at 0.5 Hz, which contradicts 6.3b's "wins at >=0.5 Hz" for that panel.
5. **Smaller items.** Only **627** takes actually contributed pairs, not the "721" the
   thesis states (721 was the candidate pool; extraction hit its cap at 11,556 pairs).
   4.2 says Adam but the code uses AdamW. The 6.5 caption compares 0.846 (956-val) with
   0.772 (137-val). 6.7 still ends in future tense about "our next rung". The 9.9x is
   called "the paper's reporting form", but the paper anchors on uniform at 1 Hz, and
   by that rule adaptive at 76 decodes (0.302) already beats uniform at 1 Hz (0.296).
   Anchoring on the best uniform point is the conservative choice, and the text should
   say so. Adaptive at 0.02 Hz (0.312, 140 decodes) also beats the best uniform
   (0.310), so the text should explain why it quotes 9.9x rather than about 25x.
   EmbeddingGemma is never named. Action100M is used but never cited. Section 9 lists
   the web UI as future work, but it is deployed.

### Typesetting defects, confirmed in the compiled PDF (pdftotext)
- In 6.8, the rejected-artifact figure fence sits in the middle of a sentence. The PDF
  reads "...our negative and positive results", then Figure 9, then a new indented
  paragraph starting "together isolate."
- Bibliography entry [3] (VL-JEPA itself) prints with **no arXiv id and no venue**. It
  is an `@inproceedings` entry with a `journal` field, and that entry type ignores
  `journal`. Fix: make it `@article`.

### Structural gaps for a Master's thesis
The body is about 6,400 words over 24 pages (21 numbered). Related work is four short
paragraphs. There are 8 bib entries and no inline `\cite`: the prose writes author-year
by hand while the bibliography is numeric via `\nocite{*}`. The 10 tables are bare
`tabular` with no caption or number. The body text never refers to a figure (all 3
`\ref`s are inside captions). The abstract is 504 words. The institute's requirements
are unknown, so the user must check them. Most of the material needed to expand
already exists in RESULTS.md (602 lines), SYSTEM_DESIGN.md (528), TABLES.md and the
data-engine story.

### Viva risk: session-level overlap behind the headline
The eval takes are disjoint from training **by take uid only**. From takes.json:
**40/40** eval takes share a participant and a physical setting with training takes,
and **39/40 share the recording session** (`capture_uid`). The thesis does not say
this. Both methods consume the same stream, so the adaptive-vs-uniform comparison is
not directly biased, but the absolute quality (the "25x from correcting the domain")
includes some familiarity with the same session. A participant-disjoint control needs
no new extraction: filtering the existing cache keeps **483 takes / 8,822 pairs (76%)**.
It would cost about 6.5 h to retrain, about 15 h to re-encode the 40 takes (23 min
each), and about 3 h for rigor. That is roughly one day of unattended T1000 time, at
no cost.

### Housekeeping
- Credentials are still on this college machine: `~/.kaggle/access_token`,
  `~/.kaggle/kaggle.json`, `~/.aws/credentials` (expired Aug 1),
  `~/.cache/huggingface/token`, and GitHub in Windows Credential Manager. Google Drive
  is also still signed in (G:).
- HANDOFF.md has 3 stale lines: the server is "currently RUNNING" (it is not), the
  thesis "needs a midweek update", and "finish the week plan".
- No viva slide deck exists.

**Queued next (the user decides):** disable the autopilot task. Choose the scope of a
thesis fix pass: items 1-5 plus the typesetting fixes are about a day of editing,
while the structural expansion depends on the institute's rules. Optionally run the
participant-disjoint control (about a day of machine time). Build the viva deck. Clean
up credentials before the machine is handed back.

---

## 2026-08-18 (Tuesday)

**Theme: the thesis COMPILES. 24-page PDF, zero errors, 14 figures placed - and
two silent defects caught by reading the PDF that no build log mentioned.**

### It had never been compiled; now it has
No TeX toolchain on this box was the reason. Fixed by downloading **Tectonic
0.17.0** (a single 51 MB self-contained binary that fetches packages on demand)
into the scratch dir - no install, nothing added to the repo. Result:
**exit 0, zero errors, zero overfull boxes**, BibTeX resolving all 8 entries,
**24 pages** (3 unnumbered front matter + 21 numbered). Sections come out 1-9
with 6.1-6.9 nested and appendices A-B, so the ~54 "6.8"-style cross-references
still land correctly.

### Figures: the body had none at all
`\includegraphics` appeared **nowhere** - BUILD.md's checklist had "insert
figures" open. Now **14 images in 11 figure environments**, captioned and
cross-referenced, placed per **Appendix B of THESIS.md** (which is the accurate
map; I wrongly called INDEX.md stale mid-session - `c1final`/`c1old` at 6.5 is
right, since that pair *is* the data-scaling contrast). One figure is genuinely
new to both maps: `results_coin_predictor.png` at 6.3, confirmed by matching its
JSON to the section's table (ckpt `checkpoints_kaggle/predictor_20000.pt`, 7
videos, CIDEr 2.611 at 1.0 Hz). Recorded in Appendix B and INDEX.md.

**Why this needed a converter change.** Figures belong in `docs/THESIS.md`, since
`thesis_body.tex` is generated and hand edits are lost. But a figure environment
could not survive `inline()`: the raw-LaTeX regex requires braces, so bare
`\centering` was escaped to `\textbackslash{}centering`, and `\caption{...}`
containing `\emph{...}` broke on the nested braces. Added a **```latex fence =
byte-for-byte passthrough** to `scripts/md_to_latex.py`, plus **HTML comments are
now skipped entirely**.

### Two defects the logs did not catch, found by reading the PDF
1. **A broken cross-reference, caused by my own fix.** Repairing "Section~\ref"
   to "Figure~\ref" with `re.sub`, the *replacement* template was interpreted by
   `re` - `\r` became a carriage return - so the markdown held CR + "ef{...}".
   LaTeX compiled it silently and the PDF read *"the negative that Figure
   effig:egoexo-indomain resolves"*. Also a violation of the repo's LF-only rule.
2. **An editorial note was being typeset as the thesis's first sentence**:
   *"This document is written in Markdown for easy conversion to LaTeX/Word;
   figures referenced are the PNGs in the repo root"* - meaningless in a PDF and
   by then factually wrong. Now inside an HTML comment.

Both are the reason `scripts/check_thesis_tex.py` now exists: it verifies figure
paths resolve, every `\ref` has a `\label`, environments balance, the body is
pure ASCII, and **no stray control characters** are in the markdown. Exit 0/1 so
it can gate a commit. It strips TeX comments before counting, or `thesis.tex`'s
own header prose ("everything above \begin{document}") reads as an unclosed
environment.

### Margins: 48 overfull warnings -> 0
Appendix B tabulates long file names in `\texttt{}`, which TeX will not break;
the worst row ran **133.20pt (~4.6 cm)** past the right margin. Fixed with
`\usepackage[htt]{hyphenat}` + `\setlength{\emergencystretch}{3em}`. Measured
properly, compiling with and without: **48 -> 0**. (First attempt at that
measurement was invalid - a heredoc mangled the edit so both arms compiled the
*same* file and both read 0. Redone with sed.)

### Deliverable
`scripts/make_overleaf_zip.py` -> **`livejepa_thesis_overleaf.zip`, 0.85 MB**:
`thesis.tex` + `thesis_body.tex` + `references.bib` flat at the archive root
(nested folders are why Overleaf's "Main document" comes up empty) + all 16 PNGs,
14 placed and 2 spare. The `.json` plot sources and demo `.mp4`s are excluded.
**Validated by extracting the zip into an empty directory and compiling that** -
exit 0 - rather than trusting the file list.

Also: `titlepage` class option (contents no longer start halfway down page 1),
and `thesis_materials/*.log` added to `.gitignore` - `build.log` was untracked
and would have been committed.

**Standing gotcha, reconfirmed hard today:** Git Bash here **halves backslashes**
in heredocs *and* in `python -c` strings. It burned me three times - a `\t` that
became a real tab inside a source comment, a self-test whose assertions passed
only because input and expectation were mangled identically, and the invalid
margin measurement above. **Write backslash-heavy content to a file with the
editor tool, then run the file.** Never through the shell.

**Left for the user:** upload the zip to Overleaf (pdfLaTeX), swap the institute
template, replace `\date{\today}` with the real submission date, add the
declaration/certificate, and re-read 7-9 plus the abstract in their own voice.

---

## 2026-08-13 (Thursday)

**Theme: the 94 GB Google Drive archive landed and was VERIFIED - not just
"the copy finished". Migration off this machine is now complete on both legs.**

### Archive verified against MANIFEST.txt, folder by folder
The user reported the upload done. Verified rather than accepted, four ways:

1. **Free space delta.** `G:` went 520.63 -> 425.33 GB free = **95.3 GB
   written**, against 94.45 GB expected. Right order, right magnitude.
2. **Per-folder file counts and byte sizes.** All 14 top-level folders match
   the manifest **exactly** - not approximately. 101,101 files, 94.24 GB.
   `eval_data`'s 11 manifest sub-entries sum to exactly 7,295 files /
   62,365.7 MB, which is what is on disk.
3. **SHA256 on the files that matter.** Byte-identical, source vs Drive:
   `checkpoints_c1_final/predictor_30000.pt` (the deployed ckpt),
   `checkpoints_egoexo/predictor_20000.pt` (the 9.9x headline),
   `data_cache_coin_full/pipeline_state.json`, all three `*/VAL_UIDS.txt`,
   `frozen_val_uids.txt`, `egoexo_takes_pred40.txt`. Robocopy compares size
   and timestamp, **not content** - so size parity alone would not have caught
   a truncated or corrupted checkpoint.
4. **Proof the bytes reached Google, not just `G:`.** DriveFS local cache is
   **0.51 GB** while `G:` presents **94.24 GB**. Drive is in stream mode, so
   the content cannot be sitting in a local upload queue - it is server-side
   and being streamed back on demand. The 228 MB of checkpoint hashing above
   was served through that path.

**94.46 vs 94.24 GB is not a shortfall.** The manifest lists the two hero `.pt`
files twice - once individually in P1 (so an interrupted transfer would still
have moved them), then again inside their parent folder in P4. 228.4 MB of
deliberate double-counting. 94.46 - 0.22 = 94.24, exactly what is on Drive.

Two file paths I guessed at while spot-checking were wrong and are recorded so
the next session does not repeat them: there is **no `eval_data/streams/.keep`**,
and **`VAL_UIDS.txt` does not live in `data_cache_coin_full`** - it lives in the
three `*_val` dirs (`a100m_val` 527 B, `coin_full_val` 4,470 B, `egoexo_val`
924 B), which is what CLAUDE.md's `*/VAL_UIDS.txt` glob has always said.
`data_cache_coin2_val` has no such file; its uid list is elsewhere.

### Migration status: both legs done
- **Code/docs/thesis** -> private `github.com/amanparganiha/livejepa`, 135 files,
  2.41 MB, 5 commits, clean tree, verified private (unauthenticated fetch 404s).
- **Data/weights/video** -> Drive `livejepa_archive`, 94.24 GB, verified above.
- `data_cache_coin_full` (12.34 GB, 53,727 files) is the least replaceable thing
  in the project - COIN's YouTube links keep dying (1,650 were already dead
  during extraction), so it cannot be rebuilt to this coverage. It is now on
  Drive with matching counts and a hash-verified `pipeline_state.json`.

**Queued next:** Overleaf compile + institute template swap
(`thesis_materials/BUILD.md`); user review of the rewritten THESIS.md
sections 7/8/9 and the `/about` copy. Still PARKED at the user's request: the
live-webcam GPU demo, pending possible access to the institute's machine.

---

## 2026-08-10 (Monday)

**Theme: references VERIFIED (two were wrong), repo prepared for GitHub, and a
migration plan - user has an internship and is losing access to this machine.**

### References verified against arxiv.org / CVF Open Access
Not from memory this time. Two entries in my own references.bib were WRONG:
1. **I had INVENTED the VL-JEPA title** ("Selective Decoding for Streaming Video
   Captioning"). Real: *"VL-JEPA: Joint Embedding Predictive Architecture for
   Vision-language"*, Delong Chen, Mustafa Shukor, Theo Moutakanni, Willy Chung,
   Jade Yu, Tejaswi Kasarla, Yejin Bang, Allen Bolourchi, Yann LeCun, Pascale
   Fung. arXiv:2512.10942, submitted 2025-12-11, revised 2026-02-02.
   **Checked for propagation: none.** The prose only ever cites it by arXiv ID
   and "Chen, Shukor et al." (which is correct). THESIS.md:1 is LiveJEPA's OWN
   title, not VL-JEPA's - not a conflict.
2. LiveCC had a placeholder venue. Real: CVPR 2025, pp. 29083-29095,
   arXiv:2504.16030, Joya Chen, Ziyun Zeng, Yiqi Lin, Wei Li, Zejun Ma, Mike
   Zheng Shou.
Confirmed correct as written: V-JEPA 2 (2506.09985, Assran/Bardes/Fan/Garrido/
Howes), SONAR (2308.11466, Duquenne/Schwenk/Sagot), CIDEr (1411.5726, Vedantam/
Zitnick/Parikh, CVPR 2015), COIN (1903.02874, Tang et al., CVPR 2019),
Ego-Exo4D (2311.18259 submitted 2023, proceedings CVPR 2024 - both noted).

### Git repo prepared (NOT pushed - awaiting the user's remote)
- `git init`, `.gitignore`, one commit `e4e0a14`: **169 files, 4.05 MB**.
- **.gitignore bug caught by verification, not by reading.** First draft used
  inline comments (`*.zip   # 286 MB`). **git has NO inline comments in
  .gitignore** - the trailing text becomes part of the pattern and silently
  matches nothing. Result: `*.zip`, `webapp/cloudflared.exe` and
  `.claude/settings.local.json` were all still staged - **342 MB**, including a
  286 MB zip and a 52 MB binary. Rules with no comment (`eval_data/`,
  `checkpoints*/`) worked, which is why it looked fine at a glance.
  Comments now on their own lines; re-verified 342 MB -> 4.05 MB, zero leaks.
  (`git check-ignore` reports nothing for files already in the index - that
  masked it the first time. Reset the index before trusting it.)
- Secret scan clean: the only hits are env-var NAMES and doc references to
  `~/.kaggle/access_token`. `scripts/download_egoexo_subset.ps1` explicitly tells
  the reader not to hard-code AWS keys. Repo will be **PRIVATE** (user's call),
  so the demo token in 8 files is not a concern; parameterise it before ever
  flipping to public.
- No `gh` CLI on this box, so the user creates the repo and authenticates; I
  wire the remote and push.

### PUSHED to github.com/amanparganiha/livejepa (PRIVATE)
4 commits, branch `main`, local and remote in sync. Verified privacy rather than
assuming it: an unauthenticated fetch of the repo URL returns **404**, which is
what a private repo does for anyone not signed in as the owner.
- Credentials were already cached by Git Credential Manager - the push printed a
  "Cannot prompt because user interactivity has been disabled" line and then
  succeeded with exit 0. Noise, not failure; check the exit code, not the stderr.
- `git init` defaulted to `master` on git 2.53 here; renamed to `main`.

### Repo pruned to what matters (user: "only push those files which are important")
**171 -> 135 files, 4.05 -> 2.41 MB. 38% of tracked bytes were EXACT duplicates.**
Found by hashing every tracked file, not by eyeballing: the eval commands write
`results_*.{json,png}` to the repo ROOT, and `thesis_materials/figures/` holds
the curated thesis-cited copies of the same files - both were committed. Same
for the two demo mp4s.
- Root copies now gitignored with a **leading slash** (`/results_*.json`) so
  `thesis_materials/figures/` is untouched; figures/ is the single committed home.
- **Rescued 4 root files that had NO twin in figures/ before untracking**: the
  superseded buggy oracle run (provenance for the 5b post-mortem), the atomic
  pilot json/png, and the C2 gate output.
- Verified mechanically that every `results_*` filename referenced in RESULTS.md,
  THESIS.md or INDEX.md resolves to a committed copy. Zero duplicate bytes left.
- Also dropped `deploy/kaggle_autopilot/autopilot.log` (run log) and
  `notebook3308534b33.ipynb` (byte-identical to notebooks/kaggle_c1_full_coin).
- All `git rm --cached` - nothing deleted from disk.
- Added a RESULTS.md note explaining the root-vs-figures split, since the
  reproduce commands still say `--out results_egoexo_rigor`.

### Migration: user is leaving the college machine
Measured what is actually irreplaceable rather than copying 120 GB:
- **`data_cache_coin_full` (12.6 GB) is the single least-replaceable artifact** -
  more so than the checkpoints, which can be retrained FROM it. 1,650 COIN
  YouTube links were already dead during extraction and more die monthly, so a
  re-run would now yield strictly less.
- New **`scripts/export_project.ps1`** (pure ASCII, parses clean): copies ~19.4 GB
  of caches + the 2 result-producing checkpoints + streams + GT annotations,
  checks free space BEFORE writing anything, robocopy with retries, writes
  MANIFEST.txt, optional `-Verify` for SHA-256. Deliberately skips the 63 GB
  EgoExo video (re-downloadable), 21 GB backups/ (redundant tars), intermediate
  checkpoints, and a100m (both its experiments are closed negatives).
- User will keep it on their laptop. Told them plainly: one copy is not a backup.

## 2026-08-02 (Sunday)

**Theme: headroom analysis closes the experimental programme. The corrected
boundary oracle landed, it is still ~= adaptive, and that turns out to be the
finding: the trigger is nearly exhausted, the remaining gap is the predictor.**

### Corrected oracle (results_egoexo_rigor_oracle_fixed.json)
  | Hz | uniform | adaptive | GT-boundary (was "oracle") |
  |---|---|---|---|
  | 0.50 | 0.6054 | **0.6473** | 0.6250 |
  | 0.20 | 0.6034 | **0.6558** | 0.6509 |
  | 0.05 | 0.5949 | **0.6725** | 0.6684 |
- The two bugs (index-vs-time mapping, exact-vs-pooled embeddings) were real: the
  0.05 Hz cell went 0.5879 -> 0.6684. But it is STILL at/below adaptive.
- Second look says this is not a third bug. Annotation boundaries are homogeneous
  in CAPTION space; adaptive's are homogeneous in PREDICTOR space, so adaptive's
  pooled mean is the sharper representative of what the encoder saw. Renamed it a
  **reference condition**, not an upper bound - the "oracle" label was the error.

### New: scripts/eval_ceiling.py - bounds that really are bounds
Pure numpy over cached streams, no SONAR decode (the semantic metric is a cosine),
so ~2 min instead of ~3 h. Prefix sums give all O(T^2) contiguous-range means from
two matmuls.
  | reference | score (95% CI) | % of ceiling |
  |---|---|---|
  | uniform @0.05Hz | 0.5949 [0.5740,0.6167] | 77.1% |
  | **dense = decode EVERY timestep** | 0.6037 [0.5854,0.6243] | 78.2% |
  | GT-boundary | 0.6684 [0.6522,0.6851] | 86.6% |
  | **adaptive @0.05Hz** | **0.6725** [0.6560,0.6898] | **87.1%** |
  | best-frame ceiling | 0.7541 [0.7396,0.7692] | 97.7% |
  | **best-window ceiling** (bound) | **0.7720** [0.7577,0.7867] | 100% |

### Three findings, and the first is the best one in the thesis
1. **Decoding more does not help at all.** Uniform is flat in decode rate:
   0.5949 (0.05Hz) -> 0.6054 (0.5Hz) -> 0.6037 (dense 2Hz). 40x the compute buys
   nothing. **Adaptive @0.05Hz (0.6725) BEATS decode-everything (0.6037)** at ~40x
   fewer decoder calls -> on this benchmark selective decoding is not a
   quality/compute trade-off, it is a strict improvement. Pooling denoises:
   best-window sits +0.018 above best-frame, i.e. a span carries signal no single
   timestep does.
2. **Perfect boundary knowledge is not the missing piece** (see table above).
   Trigger timing has essentially nothing left to give.
3. **The residue is representational.** 87.1% of a bound no real schedule can
   reach (it lets each annotation pick its own window under no budget). So the
   remaining 13% belongs to the PREDICTOR, not the trigger - which retro-explains
   why the 3c trigger-tuning sweep came back negative, and points the lever at
   predictor capacity + in-domain data, the axis where 6.5's scaling curve was
   still climbing.

### Docs
- RESULTS.md 5b: new "How much headroom is left?" subsection + method note on the
  oracle bug (kept, not hidden).
- THESIS.md: new **6.9** covering BOTH significance (paired bootstrap, which the
  thesis was missing entirely) and headroom.
- Rule carried forward: **an upper bound that loses to the method it bounds is a
  bug, not a result** - and its corollary, when the bug is fixed and it still
  loses, the label was wrong, so re-derive what the condition actually bounds.

### Packaging - DONE the same day (user gave the go-ahead)
- **New** `scripts/make_thesis_figures.py` -> `results_egoexo_rigor.png` (paired
  deltas + 95% CIs, the one ns cell circled) and `results_egoexo_ceiling.png`
  (headroom bars). House style matched to run_eval.plot_pareto.
- `thesis_materials/figures/` refreshed: **32 files** copied (was stale since
  2026-07-09 - it was missing EVERYTHING from 07-17 onward, incl. the headline).
- `thesis_materials/INDEX.md` rewritten: figure->section map in 4 groups (core /
  negative+resolution / rigor / rejected-artifact), new one-line story, regen
  commands, 2 viva notes.
- `thesis_materials/TABLES.md` rewritten: **14 tables** (was 6). New: data
  scaling, atomic-218 negative, in-domain headline, controls matrix, paired
  bootstrap, ceiling, C2/C3 matrix, vocabulary entropy. Architecture facts updated.

### Thesis defects found and fixed while packaging (these mattered)
1. **Section order was broken**: 6.5 -> 6.8 -> 6.9 -> 6.6 -> 6.7, and 6.8 opened
   with "6.7 evaluated..." - a forward reference to a section 80 lines LATER.
   Reordered by moving blocks (byte-length asserted equal before writing).
2. **Discussion/Conclusion contradicted the Results chapter.** 7/8/9 were written
   before D.4 and still concluded "regime-dependent"; the conclusion never
   mentioned the 9.9x headline at all. Rewrote all three. 7 now reconciles COIN
   (uniform holds mid-band) with EgoExo (adaptive dominates) under the single
   redundancy law, and adds a methodological paragraph on the three times a
   positive died to its own controls.
3. **Contributions list stopped at the old story** (4 items, ended at the 2.5x
   retrain). Now 7, incl. the negative/resolution pairing and the ceiling.
4. **Abstract** gained the significance + headroom sentence.
5. **Appendix A** still pointed at `checkpoints_kaggle/predictor_20000.pt` for
   everything; now section-tagged commands for all of 6.1-6.9 + which of the two
   checkpoints each result used. **Appendix B** is now a table, all names full
   (a `..._semantic.png` shorthand was caught by the checker).
6. RESULTS.md 7 claimed 3 things were "not done" that ARE done (final-ckpt
   Pareto, predictor-mode 40-take eval, ceiling). Rewritten as honest residue:
   N=7 on COIN, 40-vs-218 takes, and why neither is worth fixing.

### Verification (scripted, not eyeballed)
6.x headings sorted 6.1-6.9; all 20 INDEX artifacts + all 14 Appendix-B artifacts
exist in figures/; 87.1% re-derived from the raw jsons and matched in all three
docs; ceiling >= every reported row (invariant holds); THESIS.md pure LF.

### Webapp claim audit (user asked "is the frontend and backend also ready?")
Backend was already UP and healthy on :8000 serving the CORRECT ckpt
(`checkpoints_c1_final/predictor_30000.pt`) - no action needed there. But the
static pages had not been touched since 07-19 and carried **three defects**:
1. `index.html` chip read "up to 2.5x **time-aligned caption accuracy** vs uniform"
   - that is a wrong claim, not just a stale one. It is 2.5x fewer DECODES at
   equal accuracy, not 2.5x the accuracy. Rewritten to "up to 9.9x fewer decoder
   calls at equal-or-better caption quality" + an accurate footnote that still
   credits the 2.5x/1.6x gt-stream numbers separately.
2. `about.html` said COIN extraction hit "97% / 8,776 videos" - actual final is
   **99.6% / 8,984**.
3. `about.html` said atomic streams carry an event "every half-second" - actual
   is **~1 event / 2 s** (4x off), and the whole D.4 resolution was missing, so
   the page still ended on the regime-dependent negative.
Rewrote the findings section: kept the negative, added the predicted-stream
resolution (9.9x), the "better AND cheaper than decode-everything" result with the
87% ceiling, and the C2/C3 entropy negative. Verified live over HTTP - FastAPI
StaticFiles reads from disk, so no restart was needed.

### UI pass on /about (user: "change the UI as whatever you want")
- Headline KPI strip under the title: 9.9x / 87% / 7-of-8 / 1.2% trained.
- Findings now carry explicit verdict badges (RESULT / BOUNDARY / THE HEADLINE /
  NEGATIVE) instead of colour-only left borders - the negative is labelled as
  such rather than blending in.
- Data-scaling table: inline gradient bars behind the 956-val cos column so the
  0.667 -> 0.846 climb is visible, not just readable.
- **New inline-SVG chart** (no external assets, CSP-safe) showing fixed-interval
  0.595 / decode-every-window 0.604 / LiveJEPA 0.673 / upper bound 0.772, with
  the ceiling as a dashed marker. This is the strongest single visual we have:
  it shows the method beating decode-everything at ~40x less compute.
- Verified over HTTP: 200, 16,054 bytes, all div/section/svg/table/figure tags
  balanced.

### Live-webcam-on-RunPod analysis (user question)
`/ws_cam` ALREADY EXISTS in backend.py and is a drop-oldest design (browser
streams JPEGs into a deque(maxlen=K=16); the server encodes the newest window
whenever the GPU frees up). So it never builds a backlog - **a faster GPU buys
temporal RESOLUTION, not catch-up.**
- T1000 at ~11 s/window + trigger `window: 8`, `min_gap: 4` => ~88 s of warm-up
  before the trigger has context and a floor of ~44 s between captions. Live,
  but too coarse to demo well.
- 4090 estimate ~0.5-1.5 s/window => ~6 s warm-up, ~3 s caption floor. NOT
  measured; the estimate leans on the T1000's TU117 having **no tensor cores**,
  so its `dtype: float16` config buys it almost nothing while the 4090's fp16 is
  its fast path.
- **Gotcha that will eat an evening:** `getUserMedia` needs a SECURE CONTEXT.
  RunPod's `https://<podid>-8000.proxy.runpod.net` is fine; a raw pod IP over
  http:// will silently fail to get camera permission.
- Bandwidth is a non-issue (256x256 JPEG @2fps ~= 30-60 KB/s). `PIPE._infer_lock`
  is single-session, so a viva panel opening it at once gets "server busy".

### Live-demo latency MEASURED (new `scripts/bench_live.py`) - two corrections
Ran on the local T1000 alongside the live server (5.9 GB headroom, --no-decode):
**median 4.65 s/window** (8 iters, sd ~20 ms) for V-JEPA encode + predictor.
1. **I had told the user ~11 s/window**, quoting HANDOFF. The encode+predict step
   is **4.65 s**. NOTE: not necessarily a contradiction - the documented ~11 s is
   an end-to-end figure (frame IO + resize + SONAR decode on fire); I measured the
   per-window path that actually sets demo cadence, with frames already in RAM.
   **Have NOT re-measured end-to-end, so THESIS.md's 11 s is left alone** until a
   like-for-like run exists. Do not "fix" it without measuring the same thing.
2. **I had said `min_gap` sets the gap between captions. Wrong - `window` does.**
   `SegmentTrigger.step` CLEARS the buffer on every fire (online.py:114-116) and
   must re-fill to `window` before it can fire again. With window=8 > min_gap=4,
   min_gap never binds. Gap between captions = window x sec/window.

What that means on the T1000: window=8 -> ~37 s of silence; window=4 -> ~19 s;
window=3 -> ~14 s. So the local box is demo-usable at window=3, not hopeless.

`/ws_cam` now accepts per-session `window` / `min_gap` / `smooth` overrides
(clamped; config defaults unchanged so measurement runs are untouched). Server
was NOT restarted - uvicorn has no --reload, so the change lands on next start.

### LaTeX conversion DONE (user: "complete all the remaining part except this",
### GPU/webcam track parked - institute system may become available)
No pandoc and no TeX toolchain on this box, so:
- **New `scripts/md_to_latex.py`** - converts docs/THESIS.md -> thesis_body.tex.
  Written as a SCRIPT, not a hand conversion, because the markdown is still the
  working copy and a manual .tex would rot on the first number change.
  Handles the subset the doc actually uses (verified by inventory first: 68 table
  rows, 2 fenced blocks, 49 inline-code spans, 17 distinct non-ASCII chars).
  - **Section numbering is stripped and re-derived by LaTeX.** Safe because the
    markdown is sequential+gapless, and Abstract/Appendices are special-cased so
    they don't eat section numbers. This is what keeps the ~54 "6.8"-style
    cross-references pointing at the right places.
  - Raw LaTeX (`\cite{}`, `\ref{}`) passes through untouched, so citations can be
    added to the MARKDOWN and survive regeneration. (I had written that claim in
    BUILD.md before it was true, then made it true rather than softening it.)
  - Wide table columns auto-become `p{}` so the explanation tables wrap.
  - ASCII-art diagram's box-drawing chars mapped to ASCII for verbatim safety.
- `thesis_materials/thesis.tex` (preamble/title/bib, institute-swappable),
  `references.bib` (**with a VERIFY header - author lists and arXiv IDs came from
  project notes + memory and MUST be checked**), `BUILD.md` (Overleaf path first,
  since there's no local TeX).
- Output verified structurally: 11 sections (9 + 2 appendices), 13 subsections,
  10 tables, abstract balanced, `\appendix` present, braces 480/480, zero
  leftover non-ASCII, all environments balanced.
- **NOT COMPILED** - no TeX here. BUILD.md says so plainly and lists the 5 most
  likely first-build errors with fixes. Fixed one ordering bug by inspection:
  `\lstset` used `\color` before `xcolor` was loaded.

### Loose ends closed in the same pass
- Tests: **13/13 green**. Docs said "9/9" in THESIS.md (x2) and RESULTS.md -> fixed.
- README: pointed readers at PROJECT_CONTEXT/Master_Plan first (CLAUDE.md says
  HANDOFF.md first) -> fixed; added a Headline Result block; build-order table
  said "Final-ckpt full-system Pareto pending" (it is done) -> rewritten with
  Phase 5; layout section now lists the scripts added since July.
- Superseded banners added to `STATUS_AND_NEXT_STEPS.md`,
  `COMPLETION_PLAN.md` (upgraded to FULLY superseded) and the 2026-06-10
  `LiveJEPA_Master_Project_Plan.md`, each pointing at HANDOFF/RESULTS/BUILD.
  Kept, not deleted - the Master Plan is worth reading against what actually
  happened, since measurement overturned several of its assumptions.

### Status
**PROJECT COMPLETE.** Experiments, packaging, LaTeX conversion, webapp, docs.
Remaining: (a) compile on Overleaf + swap the institute template, (b) verify
`references.bib`, (c) the GPU/live-webcam demo IF the institute system comes
through (parked at user's request - `scripts/bench_live.py` prints the
per-window latency and expected caption cadence on whatever hardware they get).
Backend running on :8000; nothing else is running.

---

## 2026-08-01 (Saturday)

**Theme: D.4 COMPLETE - the headline result of the thesis. Adaptive dominates on
the paper's own benchmark once the predictor is in-domain: ~9.9x fewer decodes,
7/8 budgets, all three controls passed.**

### The result (40 held-out takes, in-domain predictor, CIDEr, 360s cap)

  | avg Hz | decodes | uniform | adaptive | delta |
  |---|---|---|---|---|
  | 0.998 | 7072 | 0.296 | **0.330** | +0.035 |
  | 0.499 | 3537 | 0.310 | **0.348** | +0.038 |
  | 0.333 | 2357 | 0.299 | **0.340** | +0.041 |
  | 0.199 | 1412 | 0.287 | **0.333** | +0.046 |
  | 0.100 | 706  | 0.282 | **0.331** | +0.049 |
  | 0.050 | 357  | 0.278 | **0.338** | +0.059 |
  | 0.020 | 140  | 0.249 | **0.312** | +0.063 |
  | 0.011 | 76   | **0.305** | 0.302 | -0.003 |

- **CIDEr rose 25x (0.012 -> ~0.33) purely from fixing the domain**; adaptive
  wins 7/8. Headline in the paper's form: best uniform anywhere = 0.310 @0.499Hz
  (3537 decodes); adaptive reaches 0.338 @0.050Hz (357 decodes) ->
  **~9.9x fewer decodes at equal-or-better quality** (paper: 2.85x).

### Controls - the reason this is trusted and D.3's version was not
  | control | D.3 (out-of-domain, REJECTED) | D.4 (in-domain) |
  |---|---|---|
  | metric responds to timing | +0.0012 (blind) | **+0.0225..+0.0284** |
  | survives pooling removal | +0.0051 (58% denoising) | **+0.0345** (53% survives) |
  | vs random placement | - | **8/8 wins** |
- Without pooling adaptive's lead is a FLAT +0.031..+0.040 at every frequency
  (pure temporal selection). **uniform ~= random placement (0.605 vs 0.606)** ->
  the gain is from WHERE decodes land, not from even spreading.

### Honest caveats recorded in the docs (not buried)
- The 0.011 Hz row (~2 decodes/take) is degenerate and uniform is non-monotonic
  there; a **25.3x** figure is computable from it - we quote the well-sampled
  **9.9x** instead.
- Absolute CIDEr is low (~0.33): free-form egocentric narration is hard and the
  predictor saw only 11.5k samples.
- **Why we exceed 2.85x:** our predictor is IN-domain (EgoExo-trained, eval takes
  disjoint) vs VL-JEPA's cross-domain one; and EgoExo takes are internally
  repetitive (within-take caption cos 0.669), which favours sparse adaptive
  decoding. Direction and shape replicate; magnitude is not comparable.

### Why this matters scientifically
**It resolves the D.1 paradox.** Raw atomic annotations (~1 event/2s) are
saturated -> nothing to segment -> uniform wins. The PREDICTOR smooths that into
segmentable semantic plateaus -> adaptive dominates. So selective decoding is a
property of **predicted representations**, not of dense supervision - a
distinction the paper never draws explicitly, which our negative (D.1) and
positive (D.4) results together isolate.

### Docs updated
- RESULTS.md: new **Sec 5b** (full tables, controls, caveats, repro commands);
  headline claim at the top rewritten around the predicted-vs-raw distinction.
- THESIS.md: abstract rewritten; new **6.8** with the controls narrative.
- Demo restored on the COIN champion (EgoExo ckpt is evaluation-only).

### Rigor pass - PAIRED BOOTSTRAP (user asked "is it good or needs improvement?")
- Named the honest weakness: N=40 takes, point estimates, no error bars ->
  an examiner asks "is +0.038 significant or noise?" and we could not answer.
- `scripts/eval_rigor.py`: per-take scoring + **paired** bootstrap (both methods
  see the identical take, so take-difficulty variance cancels), 5,000 resamples,
  plus an ORACLE upper bound (segment the GT stream = perfect boundaries, decode
  the PREDICTED stream there).

  | Hz | semantic delta (95% CI) | takes | CIDEr delta (95% CI) | takes |
  |---|---|---|---|---|
  | 1.00 | **+0.0397** [+0.0350,+0.0443] | **40/40** | +0.0193 [+0.0073,+0.0325] | 26/40 |
  | 0.50 | **+0.0419** [+0.0361,+0.0478] | **40/40** | +0.0212 [+0.0095,+0.0330] | 26/40 |
  | 0.35 | **+0.0484** [+0.0423,+0.0542] | **40/40** | +0.0255 [+0.0111,+0.0410] | 28/40 |
  | 0.20 | **+0.0523** [+0.0458,+0.0593] | **40/40** | +0.0263 [+0.0056,+0.0491] | 23/40 |
  | 0.10 | **+0.0675** [+0.0584,+0.0765] | **40/40** | +0.0300 [+0.0110,+0.0499] | 28/40 |
  | 0.05 | **+0.0776** [+0.0666,+0.0886] | 39/40 | +0.0279 [+0.0074,+0.0500] | 27/40 |
  | 0.02 | **+0.1057** [+0.0904,+0.1212] | **40/40** | +0.0365 [+0.0086,+0.0683] | 27/40 |
  | 0.01 | **+0.1057** [+0.0861,+0.1260] | **40/40** | -0.0017 [-0.0366,+0.0311] **ns** | 19/40 |

- **Significant at ALL 8 budgets on the semantic metric with 40/40 takes
  favouring adaptive; 7/8 on CIDEr.** The single ns cell is the degenerate
  0.011 Hz point (~2 decodes/take) already flagged as unreliable.
- Power note: semantic detects 40/40 vs CIDEr's 23-28/40 - per-take n-gram
  overlap over ~100 events is high-variance, cosine is smooth. Directions agree
  at every budget. (Per-take CIDEr ~0.15-0.20 vs corpus ~0.28-0.35 differs only
  by TF-IDF scope; only paired differences are interpreted.)
- RESULTS.md Sec 5b gained a full significance subsection + repro command.
- Ops lesson: the ORACLE picks decode points no cache has seen, so it pays full
  SONAR decode cost (~50 min/frequency) - split it out and ran uniform/adaptive
  first (cached, minutes) to secure the defensible claim before the slow part.
- Oracle launched separately at 0.5/0.2/0.05 Hz (~2-3 h) for the headroom bound.

### ORACLE BUG caught by its own sanity property (2026-08-02)
- First oracle run returned an IMPOSSIBLE result: with perfect boundary
  knowledge it scored **0.604 - identical to uniform and WORSE than our adaptive
  trigger (0.647)**. An upper bound cannot lose to the method it bounds, so it
  was treated as a code fault, not a finding.
- Two bugs in my `points()` oracle branch:
  1. **Time-base mismatch.** `build_gt_stream` timestamps from t=0 at 1/fps
     steps; the PREDICTED stream carries **window-centre** times starting
     ~K/(2*fps) = ~3.75 s in. I used gstream INDICES directly as predicted-stream
     indices -> every oracle decode misaligned by ~4 s -> degraded to
     uniform-like placement.
  2. **Unfair pooling.** Oracle used exact midpoint embeddings while adaptive
     decodes segment MEANS - handicapping the bound against the method.
- Fix: segments now map by **TIME** (`np.argmin(|times - t|)` over the predicted
  stream's own time axis) and the oracle **pools predicted embeddings over each
  GT segment**, exactly as adaptive does. Re-running at 0.5/0.2/0.05 Hz.
- **Rule for future work: an upper bound that loses to the method it bounds is a
  bug, not a result.** Sanity-check invariants before interpreting controls.

**Queued next:** corrected oracle -> thesis_materials refresh (figures/tables
incl. new Pareto PNGs) -> final packaging. All planned experiments COMPLETE.

---

## 2026-07-29 / 30 (Wed / Thu)

**Theme: D.4 stages 1-3 COMPLETE - the in-domain EgoExo predictor WORKS
(cos 0.599). Stage 4 interrupted at 12/40 takes, resumed.**

### Stages 1-3 done (unattended, free)
- **Extraction: 11,556 train + 446 val pairs** (Jul 28 19:36 -> Jul 29 11:38,
  ~16 h). Leakage-controlled: the 40 eval takes never cached, 25 takes held out.
- **Training: 20k steps** (11:38 -> 18:10, ~6.5 h) -> `checkpoints_egoexo/`
  (20 checkpoints, every 1000 steps).
- **GATE: cos 0.599, pred-pred 0.325 on held-out EgoExo takes.** This is the
  key validation: the COIN-trained predictor was semantically unusable on this
  domain (CIDEr floored at 0.012, wrong caption register entirely), whereas an
  in-domain predictor reaches 0.599 on open-vocabulary descriptive captions -
  and is not collapsed. **D.3's blocker is removed.**
  (Not comparable to COIN's 0.846: that is a 747-label closed set, this is
  open-vocabulary - see the entropy caveat in RESULTS Sec 6.)

### Stage 4 interrupted -> resumed
- Predictor-mode encoding must redo all 40 takes because the stream cache is
  keyed by checkpoint; measured **~23 min/take** (slower than the 3.3 s/window
  estimate: EgoExo takes are long). Got 12/40 before the process died with the
  session (Task Scheduler job had already exited).
- `scripts/run_d4_stage45.ps1` + task `LiveJEPA_D4Stage45` relaunched - resumes
  from take 13 (streams cache per take), then runs stage 5 (semantic metric +
  shuffled-alignment control) and **stage 5b (pooling ablation)** so the D.3
  false-positive trap cannot recur. ~11 h remaining.

**Queued next:** the decisive comparison - CIDEr + semantic + pooling ablation on
the 40 held-out takes with an in-domain predictor. If adaptive dominates, it
explains the gap to the paper's 2.85x (selective decoding needs a domain-matched
predictor); if not, the redundancy thesis is confirmed end-to-end on the paper's
own benchmark with every alternative ruled out.

---

## 2026-07-28 (Tuesday)

**Theme: D.3 finished but was UNINTERPRETABLE; ran it down to root cause, built a
style-robust metric, killed my own false positive with controls, and launched
D.4 (an in-domain EgoExo predictor) to answer the question properly.**

### D.3 completed -> CIDEr ~0.012 at every budget (apparent total failure)
- 40 takes, 360s cap, champion ckpt. uniform 0.010-0.013, adaptive 0.012-0.016.
- **Not a model failure.** Decoding cached streams showed the predictor works: on
  a bike-repair take it emits 'remove the chain', 'load the inner tube',
  'loading the tyre' - correct activity, correct actions.
- **Cause: caption-STYLE mismatch.** EgoExo annotates descriptively ("the camera
  wearer takes a tire lever from the table with his right hand"); a COIN-trained
  predictor speaks imperatives. Near-zero n-gram overlap despite correct
  semantics -> CIDEr reads 0 for both methods -> comparison impossible.
- **Methodological finding worth keeping:** n-gram metrics silently fail under
  style mismatch even when the model is semantically right. The paper never hit
  this because their predictor was trained on data matching their eval's style.

### Built `scripts/eval_semantic_pareto.py` (style-robust metric)
- Same time-alignment protocol (each GT event -> nearest decoded point) but
  scores **SONAR-space cosine** instead of n-gram overlap. Reuses cached streams
  (minutes, not hours). GT embeddings cached to eval_data/gt_emb_cache.npz.
- First result looked like a win: **adaptive beat uniform 8/8**, margin growing
  with sparsity (+0.0065 @1Hz -> +0.0199 @0.01Hz) - the paper's Pareto shape.

### CONTROLS KILLED IT (why I ran them before reporting)
- **Shuffled-alignment floor** (match each GT event to a RANDOM decoded point
  instead of the nearest): lift is only **+0.0012** for every method. The metric
  is NOT measuring temporal precision, so placement cannot be what differs.
- **Pooling ablation** (`--pool none`, exact midpoint instead of segment mean):
  mean adaptive advantage collapses **+0.0123 -> +0.0051**, and the growth with
  sparsity disappears entirely (+0.0011 at the sparsest). **~58% of the apparent
  win was mean-pooling denoising, not selective decoding.**
- Verdict: D.3 CANNOT answer adaptive-vs-uniform. Reported as such, not as a win.

### Diagnosis (measured; my first hypothesis was WRONG)
- Hypothesised "the out-of-domain stream is flat". **Refuted:** EgoExo predicted
  streams move MORE than COIN's (consecutive-cos 0.932 vs 0.972; spread 0.100 vs
  0.108).
- Real cause is on the GT side: **EgoExo within-take captions are highly
  self-similar (mean pairwise cos 0.669)** - "the camera wearer <verb>s the
  <object> with <hand>" repeated - so a prediction scores nearly the same
  against any of them, leaving alignment nothing to discriminate.
- Root cause of BOTH failures: **no in-domain predictor.**

### D.4 LAUNCHED - build an in-domain EgoExo predictor, then redo D.3
- Key realisation making it affordable: training needs only ONE 16-frame window
  per annotation (not dense streams).
- `scripts/build_egoexo_cache.py` - windowing IDENTICAL to inference (K=16 @2fps,
  centered on the annotation timestamp), resumable, leakage-controlled: the 40
  D.3 eval takes NEVER cached; 25 further takes held out for gating.
  Smoke-tested (shapes (256,1024)/(1024,), native-norm targets, correct captions).
- `scripts/run_d4_egoexo_predictor.ps1` + Task Scheduler `LiveJEPA_D4EgoExoTrain`:
  extract 12k pairs -> train 20k steps -> gate -> re-run D.3 with BOTH metrics
  (CIDEr + semantic w/ controls) -> restore demo.
- Verified start: 746 usable takes -> **721 train / 25 val / 40 excluded**,
  ~5.3 s/sample => **~17 h extraction** (resumable across nights), then ~6 h
  train + ~3 h eval.

**Queued next:** D.4 stage 1 (extraction) -> train -> the decisive re-run. If the
in-domain predictor shows adaptive dominance on EgoExo atomic content, it
reconciles our D.1 negative with the paper's 2.85x; if not, the redundancy thesis
is confirmed end-to-end on the paper's own benchmark. Either way it is publishable
and costs nothing.

**Theme: combined COIN+A100M result - a second clean negative that CLOSES the
Action100M question. C1-final stays champion.**

### C3 combined (33,573 clips) - completed 09:20, auto-gated, demo restored

  | model | training data | COIN-137 | COIN-956 | A100M-160 |
  |---|---|---|---|---|
  | C1-final | 26,863 COIN | **0.897** | **0.846** | 0.386 |
  | C1-mid | 5,529 COIN | 0.883 | 0.733 | **0.401** |
  | C2 | 6,710 A100M | 0.359 | 0.392 | 0.348 |
  | **C3 combined** | 33,573 (both) | 0.875 | 0.823 | 0.390 |

- **Adding 25% more clips made it slightly WORSE** (-0.022 / -0.023 on the COIN
  benchmarks) with no meaningful A100M gain (0.390 < C1-mid's 0.401).
- Mechanism visible in the captions - A100M's open vocabulary contaminates
  previously exact COIN outputs: 'squat and hold the barbell' -> 'sitbar and
  hold the barbell'; 'stand up with straight legs' -> 'stand up barrel with
  straight legs over head'. Exact matches 7/10 (C1) -> 5/10 (C3).
- **Verdict across C2+C3: A100M-preview helps neither as replacement nor as
  augmentation at this scale.** Predicted by the entropy analysis; the fix is
  ~10-100x more A100M data (free via Kaggle), not a different mixing strategy.
  Question CLOSED - no more paid compute needed for it.
- **C1-final remains the deployed checkpoint** (demo verified healthy on it).
- Docs updated: RESULTS **Sec 6b** (full 4-model table + mechanism), THESIS 6.6
  augmentation paragraph.
- Ops note: the run's PowerShell log is UTF-16 with NULs - decode with
  `open(...,'rb').read().replace(b'\x00',b'')` before grepping (plain grep/
  Select-String silently mangles it).

### D.3 EgoExo predictor-mode eval LAUNCHED (the last open experiment)
- **The question:** D.1 showed uniform beats adaptive at every budget on a CLEAN
  gt stream of atomic descriptions (no redundancy at ~1 event / 2 s). But the
  paper's 2.85x came from their PREDICTED stream, which the predictor smooths.
  Does the full system (V-JEPA 2 -> predictor -> SONAR) recover an adaptive
  advantage where the clean stream could not?
- `scripts/run_d3_egoexo_predictor.ps1` + Task Scheduler `LiveJEPA_D3EgoExoPred`
  (detached). 40 density-matched takes across 8 scenarios, champion ckpt
  (c1_final), `--max-seconds 360`.
- **Sizing measured before launch** (not guessed): 180s vs 360s cap costs only
  +29% windows (11.3k -> 14.5k) but lifts annotation coverage 87% -> **99%** and
  full-take coverage 21/40 -> 37/40, AND matches D.1's cap exactly -> chose 360.
  All 40/40 takes verified to resolve to playable video first.
- ETA ~13 h encode + ~3 h sweep = **~16 h**. Resumable: encoded streams cache
  per-checkpoint in eval_data/streams/, SONAR decodes persist to JSONL, partial
  curves flush per (method, hz). Demo down during the run, auto-restored after.
- Verified healthy start: "take filter: 40 uids", GPU 80%, python alive.
  (`NativeCommandError` in the log is the known PS 5.1 stderr-wrapping quirk on
  native commands - cosmetic, not a failure.)

**Queued next:** D.3 results (~tomorrow midday) -> final RESULTS/THESIS section
-> thesis_materials refresh -> final packaging. No paid compute needed for any
of it.

---

## 2026-07-25 (Saturday)

**Theme: C2 LAUNCHED - Action100M training live on a rented RTX 4090.**

### Pod deployed and running
- RunPod pod `wooden_harlequin_partridge` (id 7t8oxotussuegv), **1x RTX 4090
  24 GB, On-Demand $0.69/hr** (+$0.009 storage = **$0.70/hr** all-in),
  RunPod PyTorch 2.8 template, **80 GB disk** (30 GB container + 50 GB network
  volume auto-created at /workspace).
- User did the deploy click-by-click; bundle uploaded via Jupyter, unzipped to
  /workspace/livejepa, launched detached:
  `SHARDS=2 MAXVID=1500 nohup bash deploy/run_c2.sh > /workspace/c2_run.log 2>&1 &`
- **Verified healthy start:** 4090 detected, deps installed, configs/c2.yaml
  written, both shards fetched, **pipeline target 1,500 videos / 38,580
  segments** (bigger than C1's 26k clips), deterministic val = 44 videos,
  encoders loaded (587/587 + 387/387 weights), chunk 1 underway.
- Scale deliberately trimmed (SHARDS=2 MAXVID=1500) to keep the run inside the
  $15 credit: projected ~8-13 h => **~$6-9**. Burn tracking at 30 min: $0.34
  spent / $14.66 left = exactly the expected rate (~21 h runway).
- Harmless `HF_TOKEN` warning (unauthenticated HF downloads) - ignored.

### Notes / reminders recorded for the wrap-up
- **Billing does NOT stop when the run finishes** - the pod bills until
  **Terminate**, and the 50 GB network volume bills separately, so BOTH must be
  removed at the end. User opted to check back manually rather than install an
  auto-stop watcher (would have needed a RunPod API key).
- Wrap-up sequence when `=== C2 DONE. DOWNLOAD c2_out.tar.gz ===` appears:
  download c2_out.tar.gz -> Terminate pod + delete network volume -> unpack to
  checkpoints_c2/ -> **gate at home** on the frozen COIN vals (data_cache_coin2_val
  + data_cache_coin_full_val) -> EgoExo predictor-mode atomic eval on the T1000
  (61 GB of takes already local; deliberately NOT on the rented pod, keeps AWS
  creds off it) -> new C2 scaling row in RESULTS.md / THESIS.md.
- Partial-run safety: ckpts save every 1000 steps, so an early stop is still a
  valid, smaller scaling point.

### Housekeeping
- Local demo server dropped (its launcher process ended with the previous
  session; unrelated to the pod) -> restarted, verified healthy on
  checkpoints_c1_final/predictor_30000.pt. Local GPU is free the whole weekend
  since C2 runs remotely.

### Extraction throttled early -> C2 becomes a data-SOURCE comparison
- Chunk 1 finished (178 videos, 10 dead, **6,870 clips**); chunk 2 hit 15
  consecutive transient failures -> breaker fired, clean stop, progress saved.
  Final: **train=6,710 / val=160 clips** vs the 38,580-segment target (~17%).
- Consequence for the thesis: C2 is no longer a scale-UP. At 6,710 clips it is
  scale-MATCHED to the 5,529-clip COIN mid rung, so it answers a different (still
  valuable) question: **same scale, different data source** - does the paper's
  own data (Action100M) beat COIN step labels? Frame honestly; do NOT present as
  a scaling row.
- Lesson: pods are the wrong tool for YouTube extraction (single IP, throttles
  after ~200 videos). **Kaggle is the right tool** (free, fresh IP per session -
  exactly how COIN was beaten). Pods = training only.

### BUG OF THE DAY: training was I/O-starved on the network volume (35x fix)
- Symptom: `predictor_1000.pt` 11:41 -> `predictor_2000.pt` 14:01 = **2h20m per
  1,000 steps** (30k steps would be ~70 h ~= $49, far past the $8.43 left), with
  **nvidia-smi showing 0% GPU**.
- Root cause: the feature cache lived on `/workspace` = RunPod **network volume**.
  Each step reads 64 small .npz over network storage; per-file latency dominates
  and the 4090 idles. Not compute-bound at all.
- Fix: untar the cache to the pod's **local container disk** (`/root/cache`) and
  retrain from there -> **98% GPU, ~250 steps/min = ~35x faster**; 20k steps now
  ~80 min ~= $1.
- **RULE (carry to any future rental): never train off a network volume - stage
  the cache on local disk first.** Added to the gotchas list.
- Retargeted 30k -> **20k steps** deliberately: matches the mid-rung recipe for
  the scale-matched comparison above.
- Note: killing the slow trainer also killed its parent run_c2.sh (`set -e`), so
  gate+package were relaunched manually as a watcher that writes
  `C2_FINISHED.txt` when done.
- **`a100m_cache.tar` (3.2 GB) created** - the extracted features are the real
  GPU-bought asset; bringing them home makes the rental permanently valuable
  (future A100M/COIN-combined training runs cost nothing).

### C2 COMPLETE - trained, brought home, pod terminated
- **20,000 steps finished** in ~80 min after the local-disk fix; losses converged
  hard (info_nce 3.99 -> 0.014, cosine 0.735 -> 0.035). Sanity check: the rerun
  reproduced the killed run's trajectory almost exactly at matched steps
  (step 2500: 0.0559/0.1678 vs 0.0555/0.1676) -> deterministic, uncorrupted.
- **In-domain gate (A100M val, 160 samples): cos 0.348, pred-pred 0.328.**
  Much lower than COIN's 0.846 but **NOT comparable** - different val set, far
  harder target space: A100M captions are free-form YouTube narration (e.g.
  "It is time to get the real talk of the day") vs COIN's closed-vocabulary step
  labels. pred-pred 0.328 (< COIN's 0.408) shows the model is MORE diverse, not
  collapsed - it learned real structure in a harder space.
- Pod hiccup: `--decode` crashed on the pod (`ModuleNotFoundError: tiktoken`,
  needed by the SONAR decoder tokenizer). Cosine numbers were unaffected;
  captions deferred to home where tiktoken works. (If a future pod run needs
  decode, add `tiktoken` to the pip line in deploy/run_c2.sh.)
- My wrapup watcher never fired: `pgrep -f "livejepa.train"` matched the
  watcher's OWN command line -> infinite loop. Harmless (ran the steps by hand).
  **Rule: never pgrep for a pattern your own wrapper command contains.**
- **Brought home + installed:** checkpoints_c2/predictor_20000.pt +
  data_cache_a100m{,_val} (6,710 + 160 clips, from a100m_cache.tar 3.4 GB).
  The extracted features are the GPU-bought asset -> future A100M/combined
  training is now FREE forever on the T1000.
- **Pod terminated + network volume deleted. Total C2 spend ~$8.08**
  ($15 -> $6.92 remaining), inside the approved 800-1500 INR estimate.

### Cross-domain matrix launched (the result that makes C2 meaningful)
- Since both models AND both val sets are now local, running the full 2x2:
  each model scored on the other's benchmark. Answers "does training on the
  paper's own data help, and where?" far better than one in-domain number.
  (C1 on A100M-val, C2 on A100M-val w/ captions, C2 on COIN-956, C2 on the
  frozen COIN-137 w/ captions; C1's COIN numbers already documented: .897/.846.)

### C2 RESULT: a clean, controlled NEGATIVE (and a better finding than a win)

  | model (training data) | COIN-137 | COIN-956 | **A100M-160** |
  |---|---|---|---|
  | C1-final (26,360 COIN, 30k) | **0.897** | **0.846** | 0.386 |
  | C1-mid (5,529 COIN, 20k) | 0.883 | 0.733 | **0.401** |
  | C2 (6,710 A100M, 20k) | 0.359 | 0.392 | 0.348 |

- **Both COIN models beat the A100M model on A100M's OWN val.** The
  scale-matched control is decisive: C1-mid used FEWER clips (5,529 vs 6,710)
  at the same 20k steps and still won 0.401 vs 0.348 -> **not** a data-volume
  artifact. Training on the paper's own data did not help.
- **Diagnosis - supervision quality, not domain.** A100M-preview captions are
  model-generated over YouTube (noisy; the parser meets non-actions like "It is
  time to get the real talk of the day"), vs COIN's curated closed-vocabulary
  step labels. C2 learned the REGISTER but not the semantics
  ('Get a needle' -> 'Push the squeeze of the treats.') and answers COIN clips
  in that register regardless ('squat and hold the barbell' -> 'Monitoring and
  clean-up'). COIN models, though out of domain, land in the right activity
  neighbourhood on A100M clips.
- Scope kept narrow and honest: this is the 10% PREVIEW at ~6.7k clips; VL-JEPA
  used the full 1.2M-video corpus where noise averages out. Claim = *at small
  scale, curated supervision beats noisy auto-generated supervision even on the
  noisy corpus's own benchmark* - practically useful (prefer clean+small over
  large+noisy on a budget).
- Weak secondary observation (N=160, flag as hypothesis): C1-mid > C1-final on
  A100M (0.401 vs 0.386) despite being far weaker in-domain -> possible mild
  over-specialisation to COIN vocabulary from extra training.
- **Docs updated:** RESULTS.md new **Sec 6** (full matrix, diagnosis, scope) +
  limitations refreshed; THESIS.md new **6.6** + abstract now carries the
  supervision-quality finding; EgoExo boundary section renumbered 6.7.

### DIAGNOSIS CORRECTED (measured, my first read was wrong)
- User asked "did we miss something / can we improve?" -> measured the caches
  instead of guessing:

  | corpus | clips | unique captions | repeats/caption |
  |---|---|---|---|
  | COIN | 26,863 | **747 (3%)** | **36.0** |
  | A100M | 6,710 | **6,096 (91%)** | **1.1** |

- **It is NOT label noise** (inspection: A100M captions are mostly sensible
  actions - "puree the mixture in a blender"; only 1% contain pronouns).
  **It is target-vocabulary ENTROPY.** COIN is effectively closed-set (747
  labels x36 examples); A100M is open-vocabulary (~1 example per caption).
  6.7k one-shot targets cannot teach an open-vocab mapping.
- **This qualifies our OWN headline:** the §4 scaling curve (0.667->0.846) is
  measured on a 747-label closed set, so part of the gain is closed-set
  discrimination, not open-ended captioning. **0.846 and 0.348 are NOT
  commensurable** - different tasks sharing a metric. Recorded as an explicit
  caveat in RESULTS §6 and THESIS 6.6 rather than buried.
- Corrected both docs (earlier "noisy labels" wording replaced).
- Implication for what would help: **more data, not cleaner data** -> Kaggle
  (free, fresh IP/session), not another rental.

### Post-mortem: what we should have done on the pod
1. **Retried extraction after cooldown.** We stopped at 6,710 clips with ~15 h
   of unused runway; 2-3 retries could have multiplied the A100M set - the one
   thing that would actually have moved the result.
2. **Used the 4090 for the EgoExo predictor-mode eval** (the most compute-heavy
   remaining task; T1000 ~13 h vs 4090 ~2-3 h for 40 takes). Blocked because the
   61 GB of takes are local - but only the 40 needed takes (~3.4 GB) were
   required and could have been pulled on-pod. Kept AWS creds off the rented pod
   deliberately; defensible, but it cost the speed win.
3. Right calls: brought the feature cache home (permanent asset), and terminated
   promptly. Total $8.08 for a decisive controlled result is good value.

### Combined COIN+A100M training LAUNCHED (free, overnight, T1000)
- `scripts/run_c3_combined.ps1` + Task Scheduler `LiveJEPA_C3Combined` (detached,
  survives the session). **33,573 clips** (COIN 26,863 + A100M 6,710) - the
  largest training set of the project; `CachedDataset` comma-separated multi-dir
  verified before launch.
- Recipe held IDENTICAL to the C1-final row (30k steps, batch 32) so the result
  drops straight into the scaling table; only the data mix changes.
- Hypothesis (from the entropy finding): A100M helps as **augmentation** even
  though it lost as a **replacement** - COIN's 747-label closed set supplies
  anchor structure, A100M's 6,096 unique captions supply vocabulary breadth.
- Auto-gates on all three benchmarks when done (frozen COIN-137 vs 0.897,
  COIN-956 vs 0.846, A100M-160 vs best-so-far 0.401) and restarts the demo on
  the C1 ckpt (swap only if C3 gates better). Verified stepping: 100% GPU,
  step 200, info_nce 2.13 / cosine 0.61. ETA ~9-10 h.
- Advice to user on "should we rent again?": **no** - everything remaining is
  free (Kaggle for extraction w/ fresh IPs, T1000 for training + the EgoExo
  predictor-mode eval since all 786 takes are already local, so the Aug 1 cred
  expiry blocks nothing). Keep the $6.92 as insurance.

**Queued next:** morning - read C3 gates, update scaling table + docs, swap demo
if better -> EgoExo predictor-mode atomic eval on the 40-take subset (the open
question from D.1) -> thesis_materials refresh.

---

## 2026-07-24 (Friday)

**Theme: C2 kit COMPLETE and verified - ready for the Saturday 4090 deploy.**

- **`deploy/run_c2.sh`** written (valid bash, LF): one-command pod pipeline -
  deps -> GPU config -> `action100m_pipeline.py` (chunked extract) -> train
  (30k/batch 64) -> gate in-domain on the A100M val -> tar `c2_out.tar.gz` for
  download. Env-tunable (SHARDS/MAXVID/STEPS/BS); resumable + partial-run safe
  (ckpts every 1000 steps; training proceeds on whatever extraction landed).
- **`deploy/README_C2.md`** written: beginner runbook - deploy 4090 (NOT the
  $2-6/hr cards), 80 GB disk, upload bundle, one launch command, monitor credit,
  download result, **TERMINATE**, then home-gate. Troubleshooting + cost math.
- **Design locked: "pod trains, home gates"** - pod does the heavy Action100M
  train + in-domain A100M-val gate; the frozen COIN-val gate and the predictor-
  mode EgoExo atomic eval run at HOME on the T1000 (videos already local; keeps
  AWS creds off the rented pod).
- **`livejepa_cloud.zip` rebuilt (`--c2`, 300 MB, 77 files)** - verified to
  contain run_c2.sh, README_C2.md, action100m_pipeline.py, both checkpoints, all
  core training modules, COIN.json, uid lists, configs. 13/13 tests green; demo
  healthy on the final ckpt.
- **Everything verified end-to-end** (driver smoke Thu; bundle + bash + tests
  today). Kit is deploy-ready; only my final go + click-by-click remain.

**Queued next (Sat Jul 25):** user deploys the 4090 with click-by-click; I
confirm expected cost before Deploy; launch run_c2.sh; monitor; bring home
c2_out.tar.gz; terminate; then home-gate + EgoExo predictor-mode eval + update
RESULTS/THESIS with the C2 scaling row.

---

## 2026-07-23 (Thursday)

**Theme: D.2 full-system Pareto (final vs old ckpt) done - data scaling ~2x'd
absolute quality but the regime-dependent pattern is robust to predictor quality.**

### D.2 result (7 leakage-clean held-out COIN videos, both ckpts, same protocol)
- Ran overnight under Task Scheduler; both JSONs written, demo auto-restored on
  the final ckpt (verified /health).

  | Hz | old u | old a | final u | final a |
  |----|-------|-------|---------|---------|
  | 1.0 | 2.611 | 2.658 | 5.046 | **5.359** |
  | 0.5 | 2.644 | 2.561 | **5.388** | 5.009 |
  | 0.35| 2.856 | 2.492 | **5.072** | 5.043 |
  | 0.2 | 2.960 | 2.388 | **5.129** | 4.909 |
  | 0.1 | 2.124 | 2.348 | 4.057 | **4.486** |

- **Finding 1: data scaling ~2x'd absolute full-system CIDEr** (5.0-5.4 vs
  2.6-2.9) - end-to-end payoff of cos 0.667->0.846.
- **Finding 2: the regime-dependent PATTERN is robust to predictor quality** -
  a 2x-better predictor keeps the SAME shape (adaptive wins 1.0 + 0.1 Hz,
  uniform owns 0.2-0.5 mid-band). So the mid-band uniform-advantage is NOT an
  artifact of a weak/noisy predictor; it tracks COIN's ~0.2 Hz step cadence.
  Nearest adaptive gets is a tie at 0.35 Hz (5.07 vs 5.04). Honest: this is a
  partial NEGATIVE for plan Phase D.3 (better data did not flip the mid-band).
- Caveats: N=7 (only 7 held-out COIN videos left on disk - rest deleted as
  transient); run used config smoothing_window=3 (canonical best is 1, marginally
  favours adaptive). **Definitive full-system Pareto (best config, 30-50 videos)
  bundled into C2.** RESULTS.md Sec 3b rewritten with the comparison.

### C2 prep started (user has RunPod account + $15 credit ready)
- Design decided: **pod TRAINS, home GATES** - the pod produces the checkpoint,
  we bring it home (115 MB) and gate on the fixed vals locally on the T1000.
  Avoids bundling ~1 GB val caches, keeps the upload small, and keeps AWS creds
  off the rented pod.
- `make_cloud_bundle.py` updated: now ships BOTH checkpoints (added final
  predictor_30000) + a `--c2` flag that bundles the small training assets
  (COIN.json, uid lists, A100M manifest). Test build: 300 MB, 74 files. Clean.
- **Gap found + CLOSED same day:** `download_action100m.py` keeps full videos
  (no chunk-delete) -> won't fit a pod disk. Built **`scripts/action100m_pipeline.py`**
  - chunked download->extract->DELETE, mirroring coin_full_pipeline verbatim
  (fatal-vs-transient classification + 15-streak breaker + resumable state +
  densest-first ranking + is_val_video split + sid `a100m_{vid}_{j:03d}`).
- **Verified end-to-end** (user asked for care - runs on paid compute):
  (1) parses OK; (2) on 1 real parquet shard = 932 videos / 19,726 segments
  (so ~4-8 shards covers the plan's 50-100k target); val split 3.3%; segment
  tuples correct; (3) live 1-video/3-segment smoke: downloaded, extracted 3
  clips (npz+txt via the proven cache_sample), deleted the video, wrote correct
  state. Demo stopped for the smoke, restored + healthy after. 13/13 tests green.
- Told user: don't deploy yet (billing starts on run); when we do, pick RTX 4090
  ~$0.40/hr Community Cloud, NOT the B200/H200/RTX PRO 6000 ($2-6/hr) shown.

### Housekeeping
- Deleted eval_data/coin_chunk (4.3 GB of leftover yt-dlp staging fragments -
  1,555 .webm/.part; extraction done + merged, so pure cruft). eval_data 66->62
  GB; C: 568 GB free. eval_data's 61 GB is the EgoExo benchmark videos (786 val
  takes) - the paper's own benchmark, needed for D.1 (done) + C2 predictor-mode.

**Queued next (Fri Jul 24):** write deploy/README_C2.md (beginner runbook) +
run_c2.sh (fetch shards -> action100m_pipeline -> train -> save); rebuild the
--c2 bundle; final dry-run. Then user deploys Sat with click-by-click. C2 =
Action100M train + gate-at-home; stretch: COIN Pareto scale-up.

---

## 2026-07-22 (Wednesday)

**Theme: D.1 paper-protocol eval COMPLETE (honest negative on atomic); doc
consolidation started (Phase E).**

### D.1 result landed (EgoExo4D atomic, 218 density-matched takes, gt-mode, 360s)
- Ran ~45 h under Task Scheduler (crash-safe design held; 157,098 decode calls,
  62% cache-reused, 59.4k unique). Exited clean 10:15, results + PNG written.
- **Uniform beats adaptive at EVERY frequency** (CIDEr): 1.0Hz 4.48/3.57,
  0.5 3.47/3.11, 0.35 2.91/2.79, 0.2 2.31/2.26, 0.1 1.78/1.61, 0.05 1.40/1.21.
- Reading: confirms the pilot at full paper scale. Atomic descriptions fire
  ~1 event / 2 s -> no temporal redundancy for selective decoding to exploit ->
  uniform's even spacing near-optimal. Consistent with the keystep result (§1,
  adaptive wins ~2.5x on coarse/redundant annotations). The honest boundary:
  selective decoding pays iff meaning is temporally redundant.
- Divergence from paper's 2.85% headline noted: our GT-mode is a clean-signal
  proxy; the paper's number was on their PREDICTED (denoised) stream. Predictor-
  mode on these takes (Phase D.2 / C2) is the real open test (plan Phase D.3).
- Re-read plan (gentle-sauteeing-glacier.md) before proceeding, per user.
- Demo server restored on final ckpt (GPU freed after eval).

### Doc consolidation (Phase E) - DONE
- **RESULTS.md**: header claim rewritten (redundancy-governed dominance);
  new **Sec 4 data-scaling study** (2,962->5,529->26,360 clips, cos
  0.667->0.733->0.846) + new **Sec 5 paper-protocol EgoExo atomic** (218 takes,
  uniform wins every rate); stale "web UI not done" fixed; doc-status banner
  flags which sections use the old vs final ckpt.
- **STATUS_AND_NEXT_STEPS.md**: phase table rows 2/3/4 updated (predictor
  scaled, D.1 done, webapp deployed); Sec 5 next-steps rewritten to the plan's
  live priorities (final-ckpt COIN Pareto -> C2 -> writeup).
- **THESIS.md**: abstract rewritten to the redundancy-monotone thesis; new
  **6.5 data-scaling** + **6.6 paper-protocol atomic boundary** subsections.
- **README.md**: build-order status refreshed to 2026-07-22 / final ckpt.
- **COMPLETION_PLAN.md**: marked SUPERSEDED with a pointer banner.
- No code touched; 13/13 tests still green.

### Full-system COIN Pareto with the FINAL ckpt - LAUNCHED (running)
- Plan Phase D.2 / D.3. Found only 7 COIN videos on disk (extraction deleted
  videos as transient) but **verified all 7 are leakage-clean** (in neither the
  predictor train cache nor its val cache) -> valid held-out set. Rather than
  download 30-50 more (YouTube-throttle risk + 20 min/video T1000 encode), run
  the clean 7 now and bundle the 30-50-video scale-up into the C2 4090 weekend.
- Runs BOTH ckpts on the identical 7 videos for apples-to-apples: final
  (predictor_30000, cos 0.846, fresh ~2.5h) vs old (predictor_20000, cos 0.636,
  cached streams, fast). Old run (2026-07-09) used same 7 + same protocol but
  did not record ids -> re-running old guarantees the match.
- Launched via Task Scheduler `LiveJEPA_D2Pareto` (scripts/run_d2_coin_pareto.ps1,
  ASCII), detached (parent = scheduler shell), crash-safe. Demo down ~2.5h
  during the run; runner auto-restarts it on the final ckpt at the end.
- Outputs: results_coin_predictor_c1final.{json,png} + ..._c1old.{json,png}.

**Queued next:** D.2 finishes ~2.5h -> compare curves, update RESULTS Sec 3b,
worklog -> C2 4090 weekend Jul 25-26 (Action100M train + predictor-mode EgoExo
atomic on the 40-take subset + COIN Pareto scale-up to 30-50 videos).

**Queued next:** COIN full-system Pareto (final ckpt) -> update RESULTS Sec 3b
-> C2 4090 weekend (Action100M + predictor-mode EgoExo atomic).

---

## 2026-07-20 (Monday)

**Theme: model switch to Opus 4.8; recovered the lost D.1 eval and made it
crash-proof; full doc audit found the real risk is stale thesis docs.**

### Session handover (Fable 5 -> Opus 4.8)
- Handoff package worked as designed: read `HANDOFF.md` -> newest WORKLOG entry
  -> verified every claim against disk before acting. No context lost.

### Root-caused the D.1 eval loss (it was structural, not bad luck)
- The Jul 19 run was killed when the agent session's process exited. Post-mortem
  of the log: **all 218 streams built fine in ~4 min**; the process then spent
  ~9 h inside the *sweep*, which wrote nothing until the very end.
- Three separate flaws, all now fixed:
  1. `CachedDecoder` cache was **in-memory only** -> every SONAR decode lost.
     Now persists to `eval_data/decode_cache.jsonl` (JSONL, flushed per batch,
     tolerant of a torn last line). A restart resumes reusing prior decodes.
  2. Results were written **once, at the end**. Now the partial curve flushes
     after every (method, frequency), tagged `"partial": true`.
  3. Background jobs die with the agent process. Now launched via **Windows
     Task Scheduler** (`LiveJEPA_D1Eval` + `scripts/run_d1_eval.ps1`, pure
     ASCII) -> verified parent is a Task Scheduler shell, not the session.
- Bonus: duplicate embeddings inside one decode batch are now decoded once.
  Verified safe - `sonar._hf_decode` gives each embedding its own length-1
  encoder output, so beam search is per-item and batch-independent.
- **Verification before trusting it** (user asked for triple-checking): decode
  de-dup safety read out of `encoders/sonar.py:72-89`; cache-key equivalence
  (sha1 of the *same* rounded bytes Fable 5 hashed); no downstream consumer of
  the results-json schema; scoring math byte-identical. 13/13 tests green, then
  a live 2-take smoke run confirmed cache writes + partial flush + sane curve.
  **The numbers are unchanged - the edits buy resilience, not different results.**

### Protocol correction (measured, not assumed)
- Jul 19 run used `--max-seconds 180` (CLI default). Paper evaluates 218 takes
  of **~6 min**. Measured on our takes: 180 s fully covers only **136/218** and
  drops **16%** of annotations; **360 s keeps 98%**.
- Cost of the fix is small: projected **~94.7k unique decodes / 21.9 h at 360 s**
  vs 74.6k / 17.3 h at 180 s (measured rate **1.2 decodes/s** on the T1000).
  Relaunched at **360 s**. ETA ~11:00 Jul 21.
- Standing caveat for the writeup: our density-matched takes carry a **median of
  100 annotations vs the paper's ~143** - our val pool is sparser, unfixable.

### Doc audit - the real risk
- `RESULTS.md`, `docs/STATUS_AND_NEXT_STEPS.md`, `docs/THESIS.md`, `README.md`
  are all frozen at **2026-07-09**. They present the old ckpt (cos 0.636) as
  *the* model, contain **no scaling table**, list finished work as "next steps",
  and call the deployed webapp a "planned follow-up". Nothing is lost (it is all
  in WORKLOG/HANDOFF) but the submittable documents understate the project by a
  wide margin. `docs/COMPLETION_PLAN.md` is fully superseded.
- **This is now the top non-compute priority** ahead of the C2 weekend.

### Ops note
- SONAR enc+dec fills the T1000 (**7,965 / 8,192 MiB**) -> the demo server and a
  running eval **cannot coexist**. Demo left down while D.1 runs; pausing the
  eval is now cheap (cache resume), so the demo can be restored on request.

**Queued next:** D.1 finishes ~Jul 21 -> consolidate RESULTS/THESIS/STATUS with
the scaling table + D.1 -> COIN full-system Pareto with the final ckpt ->
C2 4090 weekend Jul 25-26.

---

## 2026-07-19 (Saturday)

**Theme: THE SCALING TABLE — final C1 checkpoint trained and gated; curve still
climbing steeply → strong C2 case.**

### Final C1 training (overnight)
- 30k steps / batch 32 on the 26,360-clip master; ran 19:10→04:41 (~9.5 h) on
  the T1000. Healthy losses (info_nce ~0.05–0.13, cosine ~0.03 at the end).
  → `checkpoints_c1_final/predictor_30000.pt`.

### THE SCALING TABLE (identical recipe/arch across rows; same vals per column)

  | training data | frozen 137-val cos | fresh 956-val cos | pred-pred (fresh) |
  |---|---|---|---|
  | 2,962 clips (WS1) | 0.772 | 0.667 | 0.527 |
  | 5,529 clips (mid) | 0.883 | 0.733 | 0.467 |
  | **26,360 clips (final)** | **0.897** | **0.846** | **0.408** |

- **Fresh diverse val jumped +0.113** (0.733→0.846) on 4.8× data — the curve is
  NOT flattening; prediction diversity also improved (pred-pred 0.527→0.408).
  Frozen-val gain small (+0.014) but that val is 7-video small-N near ceiling —
  the 956-sample val (240 held-out videos, hash-split) is the real signal.
- Decoded captions on frozen val: **7/10 exact matches**, misses are
  near-synonyms ('pull the barbell to the chin' → 'lift the barbell directly
  to the head').
- **Verdict: C2 (Action100M on a rented 4090) is scientifically justified —
  data is still the bottleneck.** User's call on the ~₹800–1,500 spend.

### Bug of the day: merge scripts dropped caption .txt companions
- Gates 2–4 crashed on an npz without its .txt. Root cause: my ad-hoc merge
  scripts copied `*.npz` ONLY — the 2,888 clips from the p5+p6 merges lost
  their captions (harmless for training, fatal for eval/decode).
- Recovery: quarantined orphans → realized the txt live in the cumulative tars
  → `tar --wildcards -xf p6.tar 'coin_*.txt'` (VAL_UIDS.txt explicitly
  excluded) → all 2,888 restored, **zero true orphans**, master intact at
  26,360 + 956 with every caption present.
- Permanent fix: `scripts/merge_cache_tar.py` (dup-safe, copies npz+txt,
  never touches pipeline_state.json / VAL_UIDS.txt).

### Demo
- Server restarted with the FINAL checkpoint (health verified,
  `LIVEJEPA_CKPT` → checkpoints_c1_final/predictor_30000.pt).

### C2 DECISION: GO (user, 2026-07-19 morning) — 4090 rental next weekend
- Basis: scaling curve still climbing (+0.113 fresh-val on 4.8× data).
- **Rental Jul 25–26** (~₹800–1,500): Action100M extract + train + bundled
  heavy evals (EgoExo predictor-mode 40, A100M-ckpt gates).
- Week plan: D.1 GT-218 finishes (~Mon) → WS2 COIN Pareto with C1 ckpt on
  T1000 (Mon night) → RESULTS.md/THESIS updates midweek → rebuild cloud kit
  (new ckpt + union state + A100M manifest) → rental weekend.
- D.1 GT-mode 218-take eval LAUNCHED this morning (run_eval gained
  `--uids-file`; 13/13 tests; → results_egoexo_atomic_218.{json,png}).

### Continuity package (user anticipates Fable 5 → Opus 4.8 model switch)
- **`HANDOFF.md`** (root): master handoff — full state snapshot w/ scaling
  table, file map, credential pointers, 12 gotchas, commands cookbook,
  week plan + C2 runbook, continuity mechanisms.
- **`CLAUDE.md`** (root, auto-loads every session): read-order + inviolable
  rules (sacred state files, frozen vals, ASCII ps1, LF, grep -a, generated
  notebooks, secrets-in-files-only, daily worklog).
- **`SUCCESSOR_GUIDE.md`** (root): the *behavioral* guide — operating
  principles, decision framework (free-before-paid, gate-before-scale,
  thresholds-not-vibes), how to work with the user, failure playbook
  (12 scenarios → first moves), goal restated.
- Memory: new `livejepa-handoff.md` + index updated. Any future model reads
  HANDOFF.md → newest worklog entry → continues.
- **Webapp gained an architecture page**: `/about` (webapp/static/about.html,
  matching product aesthetic — pipeline diagram w/ param counts, goal, scaling
  table, honest findings, use cases) + hero button on index. backend.py route
  added; server restarted on final ckpt; /health + /about verified.
- Ops quirk logged: stop+start chained in ONE PowerShell lets stop_server.ps1
  kill its own parent — always separate processes.
- V16 (last-247 sweep) committed by user this morning; watcher armed; merge
  via scripts/merge_cache_tar.py when it lands.

### COIN EXTRACTION OFFICIALLY CLOSED (V16 merged, afternoon)
- V16 caught **206 of the last 247** → p7.tar (5.23 GB) banked first-try with
  the size-verified loop, merged via merge_cache_tar.py (+~500 clips w/ txt).
- **FINAL: 8,984/9,023 resolved = 99.6%** — 7,334 videos extracted (81.3%),
  1,650 dead YouTube links (18.3%), 39 unreachable after multi-IP retries
  (0.4%, abandoned). Master: **26,863 train + 977 val = 27,840 clips.**
- The C1 checkpoint stays as-trained (26,360 clips) — the +503 late clips are
  +1.9%, not worth breaking scaling-table comparability; they join any C2-era
  training. No further Kaggle clicks EVER for COIN; noon task can be retired
  after this week (kept as dormant safety for now).
- eval_data/coin_union_state.json refreshed to the final union (from p7).

**Queued next:** D.1 218-take results (~Mon) → COIN Pareto Mon night → C2 prep
midweek → 4090 weekend Jul 25–26. User has NO daily duties anymore.

---

## 2026-07-18 (Friday)

**Theme: Colab lane retired; reverse lane goes beast-mode; pincer nearly closed.**

### Morning status
- **Kaggle V13 launched** (user's daily commit, GPU T4 ×2) after fixing a
  ConcurrencyViolation commit error — stale browser draft vs server sequence
  (caused by yesterday's API pushes + scheduled-run attempts). Fix: cancelled the
  useless CPU-only web schedule, closed duplicate tabs, F5, re-commit. Clean.
- **Colab lane RETIRED**: four consecutive runs since p4 (p5–p8, incl. two after
  fresh-runtime advice) all returned `done=1267 dead=265` — zero new videos.
  YouTube has Colab IP ranges throttled on arrival. Verified before deleting:
  p4/p6/p8 tar listings identical (7,622 entries; hashes differ only from re-tar
  mtimes). Kept colab_p8.tar locally + on Drive; deleted local p4/p6 (−3.7 GB).
  User's "p8 is 8 GB" reading was a Drive info-panel misread — actual 1.76 GB.
- **Reverse lane overnight surge: done=4952 dead=1333** (was 2630/696 at 23:00) —
  ~2,900 videos resolved in 11 h, accelerated by skip-on-existing through the
  merged colab region. Back ~6,285 videos of the list now resolved locally.
- **Master: 5,811 unique videos, 22,724 clips.** Union coverage ≈ 90%; unclaimed
  gap between Kaggle's front (~1,880 + V13 in flight) and the reverse frontier
  ≈ 900 videos, closing from both ends.
- Daily routine simplified to ONE click (Kaggle commit); noon task banks the tar.

### Noon ledger
- **V13 completed + auto-banked** (`coin_cache_p5.tar`, 3.98 GB, 12:09) — noon loop
  hands-free for the 2nd straight day. Merge: +888 new clips (862 train + 26 val);
  front lane now `done=1908 dead=440`. (autopilot.log still not receiving writes —
  known cosmetic bug; banked files are the source of truth.)
- **Master: 25,263 clips (24,392 train + 871 val), 6,383 unique videos.**
- **TRUE 3-lane union (exact, from all state files): 8,167/9,023 resolved (90.5%)**
  — done=6,529, dead=1,638, **remaining 856** (the fresh middle gap).
- Projection: reverse lane clears ~856 fresh videos in ~6–10 h → extraction done
  tonight; final C1 training (30k steps, ~3–5 h T1000) launches tonight/early
  tomorrow — a full day ahead of the Jul 20–21 projection.

### EgoExo4D access LANDED — D.1 data dependency sealed (creds valid to Aug 1)
- User's access approved; creds placed in `~/.aws/credentials` by user (never in
  chat). Verified with a metadata pull.
- **`scripts/select_egoexo_takes.py`** (new, deterministic): density-MATCHED 218
  val takes (closest to paper's ~143 anns/take; actual pool sparser — selection
  min=62 / median=100 / max=223, honest thesis footnote) + 40-take predictor-mode
  subset round-robined across 8 scenarios (Cooking, Bike Repair, Soccer,
  Basketball, Dance, Music, Health, Rock Climbing). Lists committed to
  `eval_data/egoexo_takes_218.txt` / `egoexo_takes_pred40.txt`.
- **All 218 takes' downscaled-448 videos downloaded: 19 GB, 1,989 files —
  verified 218/218 have a playable ego (aria) stream** via the repo's own loader.
  Grabbed the full set, not just the 40: access expires Aug 1, disk is cheap
  (630 GB free), and it future-proofs predictor-mode at any scale.
- Bug of the day #2: first bulk download "completed" in seconds having matched
  ZERO takes — the uid file had CRLF endings, so `tr '\n' ' '` left `\r` glued to
  every uid. Fix: selection script now writes LF (`newline='\n'`); relaunched and
  landed. (Same Windows line-ending family as the PS5.1 ASCII rule.)
- Note: 786 annotated val takes on disk (earlier notes said 826 — 786 is the
  loader-parsed count with non-empty descriptions; use 786 going forward).

### Afternoon reverse-lane check (15:50)
- `done=5542 dead=1498` (7,040 resolved locally; ~100 fresh videos/h in the
  step-dense middle). Union ≈ 8,400/9,023 → **~600 remaining**, ETA ~22–23:00.

### Evening: reverse lane FINISHED the list; leftover endgame armed
- **Reverse lane walked the entire 9,023-video list and exited cleanly**
  (`done=6102 dead=1629` local; final chunk was the 12-video list tail). Every
  COIN training video has now been visited by at least one lane.
- **Union after finish: 8,181/9,023 resolved (90.7%)** — done=6,543, dead=1,638,
  **remaining 842**, ALL of them transient download failures (local IP throttle),
  not unvisited videos.
- Immediate retry pass recovered only +10 (+1 dead) before the 15-streak breaker
  fired — local IP still hot. (Also: my log-filter grep flipped to binary mode
  and swallowed the breaker message — use `grep -a` on pipeline logs.)
- **Endgame armed, two prongs:**
  1. **Union-state-aware Kaggle notebook**: `make_c1_notebook.py` now bakes
     `eval_data/coin_union_state.json` (all-lane done/dead) into cell 5c as a
     99 KB zlib+base64 blob — tomorrow's session skips everything resolved and
     spends Kaggle's fresh IP ONLY on the 842 leftovers. Legacy mass-dead
     auto-repair threshold raised 1500→3000 so the legitimate union dead-list
     (~1.6k) never triggers --retry-dead. Pushed as **V14 draft** (the push's
     CPU run fails at cell 2 by design — "notebook failed" email tonight is
     EXPECTED; chain resumes from V13's p5.tar).
  2. **Overnight local retry loop**: 4 passes at 3-h intervals (~19:45, 22:45,
     01:45, 04:45), --sleep 4; breaker caps the cost of a still-throttled pass
     at ~10 min.
- Training decision: leftovers (842) > threshold (~400) → final C1 training
  moved to TOMORROW EVENING after V15's tar + overnight gains merge. Still
  inside the Jul 20–21 projection.

### Night addendum: V15 live early + EgoExo insurance complete
- User committed **V15 tonight** (after F5) instead of waiting for morning — the
  union-aware notebook is hunting the 842 leftovers on a fresh Kaggle IP right
  now; status watcher armed for immediate download+merge on finish.
- **EgoExo insurance download DONE: all 786 annotated val takes now have
  playable video on disk — 61 GB total** (`eval_data/egoexo/takes/`,
  +41.7 GiB / 5,197 files for the extra 568). Zero remaining dependency on the
  Aug 1 credential expiry; predictor-mode eval possible at ANY scale.
  (Also corrected user misconception: EgoExo is eval-only, never training —
  contamination would invalidate the benchmark.)

### LATE NIGHT: V15 vindicates the union blob — FINAL C1 TRAINING LAUNCHED
- **V15 (union-aware, fresh Kaggle IP) rescued 585 of the 842 leftovers** in one
  session: state `done=7128 dead=1648`. Download broke once at 3.83/4.97 GB
  (IncompleteRead) — retry loop landed it. Merge: **+2,001 clips** (1,916 train
  + 85 val).
- **UNION: 8,776/9,023 resolved = 97.3% — only 247 videos left.** Extraction is
  effectively COMPLETE: 7,128 videos extracted (79% of the list), 1,648 dead
  links (18.3%), 247 in-limbo (2.7%, both IPs throttled on them).
- **Master: 27,316 clips (26,360 train + 956 val), 6,979 unique videos — 9.2×
  the original training set.**
- 247 < 400 threshold → **FINAL C1 TRAINING LAUNCHED TONIGHT** (task bz3c0qf5j):
  30k steps, batch 32, `data_cache_coin_full` (26,360 clips) →
  `checkpoints_c1_final/`. Overnight retry loop stopped (GPU conflict; 2.7%
  won't move the curve). Demo webapp STOPPED for the night to free VRAM
  (~4 GB) — RESTART IN THE MORNING with whichever ckpt gates best.
- Tomorrow's draft refreshed: **V16 pushed** with the 97.3% union blob (106 KB)
  — an optional user click sweeps only the last 247 (expect another failed-push
  email tonight; harmless CPU run).

**Queued next (2026-07-19):** training finishes ~00:30–02:00 → morning: gate vs
frozen 137-val (baselines 0.772 / 0.883) + fresh val + Kaggle-1118 if available
→ scaling table → restart demo with best ckpt → EgoExo D.1 GT-mode → optional
V16 click for the last 247.

---

## 2026-07-17 (Thursday)

**Theme: full fleet autonomous; pilot delivers a scientifically important surprise.**

### EgoExo atomic-descriptions pilot — RESULT (15 densest takes, GT-mode, ~20 h T1000)
- Full budget-matched sweep completed (19,734 unique SONAR decodes, 43% cache reuse).
- **Surprise: uniform beats adaptive at EVERY budget on this subset** — e.g. CIDEr at
  0.35 Hz: uniform 2.51 vs adaptive 2.36; at 1 Hz: 3.75 vs 2.94 (opposite of the
  keystep result, where adaptive won ~2.5×).
- **Diagnosis:** densest-first selection backfired scientifically — these takes carry
  500–1,136 captions in 300 s (a semantic event every 0.3–0.6 s). When meaning changes
  every moment there are no redundant segments to skip, so *selection has nothing to
  exploit* — uniform is near-optimal under constant change. Selective decoding's
  advantage is a function of temporal redundancy; these takes have none.
- **Value for the thesis:** this maps the mechanism's *boundary* — adaptive wins on
  keysteps (sparse, redundant), loses on hyper-dense atomic streams. Together with the
  COIN mid-band finding, the story becomes "when does selective decoding pay?" —
  stronger and more publishable than a bare win.
- **Protocol fix for the full D.1 run:** density-MATCHED selection (218 takes closest
  to the paper's ~143 annotations/video), plus all-826 as robustness; densest-15 kept
  as the stress-test condition. Compute reality: the full grid on T1000 ≈ days →
  either trim the frequency grid, or bundle the big eval into the C2 4090 weekend
  (~₹300 extra, hours instead of days). Decision pending C1/C2 timing.

### Kaggle autopilot — reality check and final shape
- The 5:32 scheduled run failed → investigation revealed **Kaggle policy: scheduled
  notebooks AND API-pushed runs are CPU-only** (web dialog states it outright;
  API pushes died with "Torch not compiled with CUDA enabled" despite
  `enable_gpu:true` + `--accelerator NvidiaTeslaT4`). Full-zero-click autopilot is
  impossible on Kaggle free tier.
- **Final lane design:** user does ONE daily "Save Version → Save & Run All"
  (~30 s; web commits DO get GPU — verified: Version #12 running on T4 ×2, past the
  5-min CUDA-check window). Self-input resumes from previous version's output; PACK
  runs unattended; a local Task-Scheduler job (noon daily,
  `deploy/kaggle_autopilot/run_daily.ps1`) auto-downloads the newest tar into
  `backups\`. Web schedule deleted (CPU-only → useless). Kaggle API token installed
  (`~/.kaggle/access_token`) — CLI works for status/output/download.
- Kaggle quota: 17/30 GPU-h remaining this week — fits daily commits till reset.

### Autonomy milestones
- Pilot completion auto-triggered **mid-point training** (20k steps on 5,529 clips,
  running now); reverse-lane extraction auto-queued behind it.
- **Kaggle autopilot went live**: session 3 ran manually as verification — the
  self-input loop worked (`unpacking newest bundle` from the notebook's own output,
  resume `done=809 dead=202`), packed `coin_cache_p3.tar (1.92 GB)`; user scheduled
  **daily runs** (Frequency trigger, start 07/17). Datasets pN remain as manual
  backups only; weekly tar download to `backups\` recommended.
- **Colab lane batch 2** launched via delete-runtime → Run all (auto-resumed from
  Drive: `done=388 dead=88`, 1,174 clips restored — Drive loop proven).

### Mid-point checkpoint — FIRST SCALING-TABLE ROW (data scaling WORKS)
- Trained 20k steps on the 5,529-clip two-session cache (identical recipe/arch to
  the original — clean apples-to-apples). Gate results:

  | training data | frozen 137-val cos | fresh 168-val cos | pred-pred |
  |---|---|---|---|
  | 2,962 clips (old, Kaggle WS1) | 0.772 | 0.713 | 0.519 |
  | **5,529 clips (p1+p2)** | **0.883 (+0.111)** | **0.729 (+0.016)** | 0.503 |

- **Decoded captions are now near-exact on the demo domain**: 'lift the barbell
  directly over the head' → identical; 'stand up with straight legs' → identical;
  'put down the barbell' → identical; misses are semantically close ('pull the
  barbell to the chin' → 'lift the barbell...'). Massive visible quality jump vs
  the old fuzzy captions.
- Honest caveats logged: frozen-val is 137 clips from only 7 videos (small-N,
  class-overlap with training pool boosts it); the fresh 168-sample val gain is
  modest (+0.016) — the full-COIN checkpoint will tell whether the curve keeps
  climbing. Not collapsed on either val.
- **Demo server swapped to the new checkpoint** (`LIVEJEPA_CKPT` →
  checkpoints_c1_p1/predictor_20000.pt), health verified.
- Verdict: scaling gate PASSED — free lanes keep grinding toward full-COIN; C2
  (Action100M, paid) decision after the full-COIN checkpoint.

### End-of-day fleet ledger (first full three-lane day)
- **Kaggle V12** (daily commit, GPU): +493 videos, cumulative `done=1522 dead=358`;
  noon task auto-banked `coin_cache_p4.tar (3.0 GB)` into backups\ — full loop
  (run → pack → save → local download) verified hands-free. "Notebook finished"
  email = daily health signal (finished good / failed bad).
- **Colab**: 4 batches total banked on Drive (`colab_p4.tar`, 1.8 GB):
  `done=1267 dead=265`, 3,661 train + 148 val clips. GPU cooldown for the rest of
  the day (heavy use) — resumes tomorrow morning with one Run all.
- **T1000 reverse lane**: auto-started after training; ~930 back-of-list videos in
  the first afternoon (tail videos are step-sparse → fast turnover, fewer clips
  each).
- **Merges into the local master** (colab_p4 + kaggle_p4, dup-safe, live-lane state
  preserved): **14,886 clips** (14,390 train + 496 val) — 5× the original training
  set. Zero duplicate sample-ids across lanes (disjoint-lane design confirmed).
- **Coverage: ~4,340 / 9,023 videos ≈ 48% in two days.**
- Bug of the day: my persistent tail-monitor held a Windows file lock on
  autopilot.log, silently eating the noon driver's log lines (download itself
  unaffected). Monitor killed; backups\ is the source of truth.

### Timeline projection (agreed with user)
- Remaining ~52% is the step-dense middle → ~2–3 more days of daily clicks
  (Kaggle 17 GPU-h left this week ≈ 5 sessions; Colab daily mood permitting).
- **Final C1 training runs LOCALLY on the T1000** the night extraction completes
  (only the local master holds all lanes' clips; ~3–5 h for 30k steps) →
  full scaling table next morning → big predicted-stream Pareto the night after.
- Expected: **final C1 checkpoint ≈ Jul 20–21**, headline eval ≈ Jul 22, then the
  C2 (Action100M, rented 4090) go/no-go with the paper-protocol EgoExo eval
  bundled into the same rental.
- User's daily routine: Kaggle Save & Run All (30 s) + Colab Run all (1 min) +
  forward the EgoExo AWS creds email when it lands. Everything else automatic.

### Late-evening addendum (post-compact)
- **Colab ran twice tonight (p5 21:40, p6 21:45) but extracted ZERO new videos** —
  merge of p6 found all 3,661+148 clips already in the master; lane state frozen at
  `done=1267 dead=265` (identical to p4). Diagnosis: YouTube throttled the session
  instantly (second run reused the same runtime/IP). Advice given: between same-day
  runs do Runtime → *Disconnect and delete runtime* for a fresh IP; otherwise one
  run per day is the honest yield.
- Cumulative-tar design proved its worth: p5/p6 were harmless no-ops, dup-safe merge
  skipped everything, nothing to clean up.
- **Local master tonight: 18,060 clips (17,427 train + 633 val), 4,541 unique
  videos** — reverse lane added ~1,100 videos since the afternoon ledger
  (`done=2630 dead=696` and still running). Kaggle p4 spot-checked as fully merged.
- Rough union coverage now ≈ 5,900–6,000 / 9,023 resolved (~65%): extraction is
  ahead of the 2–3-day projection.

**Queued next:** daily clicks continue → merge each day's tars → extraction
completes → local final training → scaling table → Pareto eval → C2 decision.

---

## 2026-07-16 (Wednesday)

**Theme: C1 data-scaling launched for real — two Kaggle sessions survived YouTube's
throttling; local overnight training chain armed; EgoExo paper-protocol eval started.**

### Kaggle rung C1 (full-COIN extraction)
- **Session 1 ran and completed**: 385 videos processed, 107 dead links, **3,081 clips
  extracted at 1.4 s/clip** (~2 GPU-h) — more clips than the entire original training
  set (2,962) in one session.
- Survived three real-world failures, each now permanently fixed in code:
  1. **YouTube throttled the Kaggle IP** after ~400 downloads → pipeline now classifies
     fatal vs transient download errors, has a 15-streak circuit breaker that stops
     cleanly with progress saved, 2 s pacing between downloads, and a `--retry-dead`
     repair flag (a throttled legacy session had mass-marked ~3.3k good videos dead).
  2. **Kaggle's version-save 429'd** on 6,000+ tiny cache files → new PACK cell tars
     everything into one file (1.5 GB) before saving; notebook auto-unpacks tars (and
     Kaggle's own auto-extraction of them) on resume.
  3. **HuggingFace CDN outage** (global 504s) mid-launch → waited out; also learned
     fresh sessions must re-run cells 1→5 (pip deps vanish per session).
- Progress banked as Kaggle dataset **`livejepa-coin-cache-p1`** (verified: 6,210 files).
- **Session 2 launched and completed** with the fixed notebook: resume verified
  (`done=385 dead=107`, `remaining: 8531`), ran unattended on the institute machine's
  browser (Chrome Remote Desktop insight: the tab lives at the institute, so the
  user's laptop can disconnect freely). Result: **+424 videos, +2,616 clips at
  2.0 s/clip** before the breaker fired → cumulative `done=809 dead=202`
  (1,011/9,023 ≈ 11%), **total cache 5,697 clips (~1.9× the original training set)**.
  PACK cell auto-numbered `coin_cache_p2.tar (1.30 GB)`; saved as dataset
  `livejepa-coin-cache-p2` (cumulative — future sessions attach only the newest).
- Revised pace estimate: ~350–450 videos/session ⇒ Kaggle alone needs ~20 sessions;
  decided to add a parallel local-T1000 extraction lane (institute network showed no
  YouTube blocking) — to be set up after tonight's GPU work finishes.

### Local (institute T1000)
- `coin_cache_p1.tar` downloaded by user → unpacked and verified locally
  (3,036 train + 45 val clips, samples load, captions intact).
- **Automated overnight chain queued**: when the running EgoExo pilot finishes →
  train mid-point predictor on the 3,036 fresh clips (20k steps, batch 32 — identical
  recipe to the original for a clean scaling comparison) → three gate checks
  (new-vs-frozen-137 benchmark, new-vs-p1-val, old-ckpt-vs-p1-val baseline row).

### EgoExo4D (paper-protocol eval, D.1)
- Discovered we already hold **826 annotated val takes locally** (paper used 218) —
  the GT-mode paper-protocol eval needs no downloads at all.
- Added densest-first take ordering to `run_eval.py` (so `--max-videos 218`
  approximates the paper's ~143-annotations/video density); tests 13/13.
- **Pilot running**: 15 densest takes (500–1,136 GT events each), streams built,
  frequency sweep in progress on the T1000 (slow — thousands of SONAR decodes).
- User re-signed the EgoExo4D license (Dropbox Sign confirmed); AWS credentials email
  pending; renewal link: ego4d.dev/request/ego-exo4d.

### Housekeeping
- Repo cleanup: freed 2.6 GB (5.7 → 3.1 GB) — deleted superseded caches/checkpoints,
  dry-run artifacts, stale cloud bundle (all verified unreferenced); kept the frozen
  benchmark, EgoExo annotations (irreplaceable while creds expired), current ckpt.
- Demo server found dead (silent crash days ago) → restarted, healthy, token on.
- This worklog created (user request: maintained daily by Claude, unprompted).

### Third extraction lane (Colab + user's 5 TB Google Drive)
- User revealed a 5 TB Google Drive → built a **Colab middle-lane notebook**
  (`notebooks/colab_c1_full_coin.ipynb`, generated by `make_colab_notebook.py`):
  mounts Drive, resumes from the newest Drive tar, extracts with `--start-frac 0.5`
  (starts mid-list — Kaggle owns the front, T1000 the back), and **auto-saves the
  cumulative tar to Drive at session end — zero manual saving**. Also solves future
  Action100M cache storage (no 100 GB Kaggle cap) and offsite backup.
- p2 tar merged into the local cache: **5,697 clips locally** (5,529 train + 168
  val); tonight's mid-point training upgraded to train on the full two-session haul.

### Kaggle autopilot (user-approved upgrade)
- Rebuilt the C1 notebook as an **autopilot**: train/gate cells guarded behind
  `RUN_TRAIN=False` (safe for all-cell scheduled runs), resume unpacks only the
  numerically-newest cumulative tar, PACK always runs. With the notebook's **own
  output attached as an input**, each scheduled daily run resumes from the previous
  one — user's per-session dance drops to ~zero (verify once manually, then
  Schedule daily). Colab session 1 also launched (middle lane, running).

### Second extraction lane (local T1000)
- Added `--reverse` to `coin_full_pipeline.py`: the T1000 walks the same
  deterministic 9,023-video list **back-to-front** while Kaggle walks it
  front-to-back — the two lanes can't collide and need no state syncing.
- Queued to start automatically tonight after the training chain releases the GPU
  (pilot → mid-point training → gate checks → reverse extraction). Tests 13/13.

**Queued next:** report pilot Pareto + mid-point gate numbers (chain still running —
pilot's sweep is heavy on the dense takes) → user saves session 2 as
`livejepa-coin-cache-p2` (done: +2,616 clips) → first reverse-lane yield check in the
morning → full 218-take paper-protocol run once GPU scheduling allows → C2
(Action100M on rented 4090) once C1 gates pass.

---

## 2026-07-14 (Monday) — backfilled

**Theme: "ideal route" plan approved; Phase-A data engine built and dry-run-proven.**

- Researched the landscape: **Action100M released** (`facebook/action100m-preview` —
  the very dataset VL-JEPA trained on; annotations + YouTube IDs, tree-of-captions);
  VL-JEPA code/weights still unreleased (novelty intact); paper recipe extracted
  (490M Llama-init predictor, InfoNCE, EgoExo4D 218-video protocol, headline
  "selective @0.35 Hz ≈ uniform @1 Hz → 2.85×").
- **Hybrid compute route decided** (user choice): T1000 serves/evals, free Kaggle T4
  for heavy lifting, paid 4090 bursts (~₹1–4k total) only at gated rungs.
  Timeline ~3–4 weeks to headline results.
- Built Phase A: `livejepa/data/action100m.py` (parquet loader with caption-quality
  filters — caught a leaked video-uid caption in real data), `download_action100m.py`,
  `build_action100m_cache.py`, chunked `coin_full_pipeline.py` (download→extract→
  delete for small disks), `--exclude-uids-dir` benchmark protection, multi-dir
  `CachedDataset`.
- **Cache storage fix: 3.90 → 0.49 MB/clip** (cache-time token subsampling, identical
  to train-time rule) — 100k clips ≈ 49 GB, fits Kaggle.
- **T1000 dry-run gate passed end-to-end**: 1 shard → 5 videos → 25 clips (4.9 s/clip)
  → 1,000 training steps → decoded captions. Tests 13/13.
- C1 Kaggle bundle assembled (`kaggle_c1_full_coin.ipynb` generated by
  `make_c1_notebook.py`; `livejepa_kaggle.zip`).
- Datasets/storage budget documented in plan; GTX 1080 Ti noted as possible free lane
  (pending user confirming with friend).

---

## 2026-07-13 (Sunday) — backfilled

- Data audit for the user: training had used 2,962/1,118 train/val step-clips from
  ~3 videos/class × 180 COIN classes (~4–5% of COIN); eval = 26 COIN gt / 7 COIN
  predictor / 10 EgoExo keystep takes. Recommendation: scale COIN first, then
  caption-style diversity; keep val sets frozen.
- Parameter story measured from weights on disk: V-JEPA 2 = 326.0M, SONAR decoder =
  1,370.6M, SONAR encoder = 766.1M, trained predictor = **29.9M (1.2% of ~2.5B
  total)** — the "decode selectively" argument in one number (the 1.37B decoder
  sleeps through ~90% of windows).
- A4000 lab found full → drafted GPU-access request mail (short + long versions);
  advised asking for remote/off-peak access instead of a seat.
- Paid-GPU options surveyed: Azure-for-Students credits, Colab Pro, RunPod/Vast
  (~₹25–60/hr for 3090/4090); "rent a 4090 for defense day" plan; cloud kit built
  (`make_cloud_bundle.py`, `deploy/cloud_setup.sh`, `deploy/README_CLOUD.md`,
  `livejepa_cloud.zip`).

---

## 2026-07-10 (Friday) — backfilled

**Theme: full deployment + product-grade frontend; system design doc.**

- Verified project health (9/9 tests, all artifacts) → hardened `webapp/` for
  deployment: env-var config, validated chunked uploads (type whitelist, 413 cap,
  traversal-safe), CORS, `/config`, timing-safe optional token auth, job logging,
  busy events; frontend busy/reconnect UX + `?token=` passthrough.
- Ops scripts: `start_server.ps1` (0.0.0.0, log tee, crash-restart, port guard),
  `stop_server.ps1` (kills launcher first — restart-loop resurrection bug found and
  fixed live), `start_tunnel.ps1` (cloudflared).
- `docs/SYSTEM_DESIGN.md` written — full 18-section production design.
- **15/15 E2E checks passed** on the deployed server (REST, uploads incl. negative
  cases, video WS on sample + uploaded file, busy refusal, webcam WS, token gates).
- **Frontend rebuilt as a product page** (user: "sell themselves"): hero with
  animated adaptive-vs-uniform decode strip, honest stat chips, Watch/Predict/Speak,
  COIN thumbnail gallery (`/thumb/{name}`), **live semantic-shift meter** exposing
  the trigger's real signal vs τ (verified: 0.007→0.160 ramp crossing τ=0.15 exactly
  at caption fire), decoder-calls-skipped stat, decode timeline, .srt download,
  use-case cards. `SegmentTrigger.last_shift` added; `delta` streamed in both modes.
- **Public HTTPS tunnel verified end-to-end** (trycloudflare URL: page, health,
  401 without token, caption over public wss) — user tested from laptop.
- Earlier context (same era): predictor_20000.pt integrated (cos 0.636 Kaggle-1118 /
  0.772 local-137, non-collapsed), WS2 predictor-mode Pareto run (regime-dependent
  result), smoothing ablation (negative, honest), demo.py fps bug fixed + demo MP4s,
  thesis draft + `thesis_materials/` assembled.

---
