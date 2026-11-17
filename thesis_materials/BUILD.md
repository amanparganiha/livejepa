# Building the thesis PDF

## Status — read this first

**The document compiles.** Last built **2026-11-17**, after the reframe for the
pooling-matched baseline (see WORKLOG 2026-11-17), with Tectonic 0.17.0 (a
self-contained TeX engine). The build is clean:
- exit 0, with **zero errors and zero overfull boxes** (the first build of the
  new text overran by 170pt in the new paired table; it now uses a two-level
  header in a raw-LaTeX block and fits);
- all **28 bibliography entries are cited in the text**;
- no reference or citation is undefined, and the extracted PDF text has no
  `??`, no leaked LaTeX and no control characters.

The content is 14 images in 11 figure environments and 11 numbered, captioned
tables, with a List of Figures and a List of Tables: **34 pages**, unnumbered
front matter (title, contents, the two lists, abstract) plus the numbered body,
ending with the references. The remaining warnings are underfull boxes, mostly
the long file names in Appendix B's table — cosmetic.

The Overleaf zip was validated by extracting it into an empty directory and
compiling that; its text matches the main build exactly. (Earlier builds:
2026-08-18, 24 pages; 2026-09-20, 32 pages.)

The PDF was read page by page and checked mechanically from its extracted text,
not just declared clean by a log. The Overleaf zip was validated by extracting it
into an empty directory and compiling that; its text matches the main build
exactly. (The first build was 2026-08-18: 24 pages, 8 references, no inline
citations.)

That does not make an Overleaf build automatic — Overleaf runs pdfLaTeX rather
than Tectonic — but every error class that a first build usually surfaces
(missing figure, unbalanced environment, dangling `\ref`, unescaped character,
missing package) has already been found and fixed here.

## The IEEE paper

`paper_ieee.tex` is an **IEEEtran journal-format** (two-column) paper distilled
from the same results, sharing this directory's `figures/` and `references.bib`.
It is **13 pages** (built 2026-11-17: exit 0, zero overfull boxes, no undefined
references; its Overleaf zip compiles from an empty directory to identical text).
It carries 18 tables, 13 plots plus 2 figures drawn in TikZ, and 27 references. Build it the same way (`tectonic -k
paper_ieee.tex`, or pdfLaTeX + BibTeX twice), or package it for Overleaf with:

```bash
python scripts/make_overleaf_zip.py --paper   # -> livejepa_paper_ieee_overleaf.zip (0.72 MB)
```

Three things to know. It is **hand-maintained**, not generated, so a number
changed in `docs/THESIS.md` must be changed here too. Its author block is complete
(2026-11-17): A. Parganiha, Department of Computer Science and Engineering, and
K. G. Atram, Department of Data Science and Artificial Intelligence, both IIIT
Naya Raipur, with institute e-mails. The running head is deliberately empty
(`\markboth{}{}`), so pages carry only a page number; the commented line above it
shows how to print a venue banner if a journal asks for one. And for a conference rather than a journal,
switch the class option to `conference` and cut: the 6-page conference version was
this paper without the ablation grid, the tuning sweep, the qualitative examples,
the same-takes control and the per-budget significance table.

Two of its figures are **drawn in TikZ inside the .tex**, not imported: Fig. 1
(architecture) and Fig. 2 (what the two schedules do at an equal budget). Edit
them where they sit; each is wrapped in a `\resizebox` so it cannot overrun the
column or the page. Winning cells in the result tables use `\best{}`, defined in
the preamble, which tints and bolds in one step.

Every numeric cell in the paper was checked against its source file at the
printed precision (287 cells). If you edit a number, re-run that check rather
than trusting the edit.

## Fastest route: Overleaf

A ready archive is built for you:

```bash
python scripts/make_overleaf_zip.py     # -> livejepa_thesis_overleaf.zip (0.86 MB)
```

1. Go to overleaf.com → **New Project → Upload Project** → pick
   `livejepa_thesis_overleaf.zip`.
2. **Menu → Compiler → pdfLaTeX**. (Main document should already be `thesis.tex`;
   the zip puts it at the archive root precisely so Overleaf finds it.)
3. **Recompile.** Overleaf runs BibTeX for you.

The zip carries `thesis.tex`, `thesis_body.tex`, `references.bib` and all 16
PNGs — 14 placed in the body, 2 spare so you can add figures without
re-uploading. The `.json` plot sources and the two demo `.mp4`s are deliberately
excluded: LaTeX reads none of them.

## Local build

```bash
cd thesis_materials
pdflatex thesis && bibtex thesis && pdflatex thesis && pdflatex thesis
```

Or, with no TeX installation at all, the engine used here — it downloads what it
needs on first run:

```bash
tectonic -k -o . thesis.tex
```

## The one rule about editing

`thesis_body.tex` is **generated**. Do not edit it — changes vanish on the next
regeneration. Edit `docs/THESIS.md`, then:

```bash
python scripts/md_to_latex.py        # regenerate the body
python scripts/check_thesis_tex.py   # static checks; exit 0 = safe to build
python scripts/make_overleaf_zip.py  # refresh the upload archive
```

`check_thesis_tex.py` verifies that every figure path resolves, every `\ref` has
a `\label`, environments balance, the body is pure ASCII, and no stray control
characters have crept into the markdown. That last check is not hypothetical: a
carriage return once replaced the backslash in a `\ref`, LaTeX compiled without
complaint, and the PDF read "the negative that Figure effig:egoexo-indomain
resolves". Nothing in the build log mentioned it.

## Raw LaTeX in the markdown

Three escape hatches survive conversion:

- **Inline** — `\cite{vljepa2025}`, `\ref{fig:x}`, `\label{...}` written in the
  prose pass through untouched. A tie written directly before one
  (`Figure~\ref{fig:x}`, `SONAR~\cite{sonar2023}`) is kept as a non-breaking space;
  every other `~` in the prose means "approximately" and is escaped.
- **Block** — anything inside a ```` ```latex ```` fence is emitted byte-for-byte.
  This is how the figures are placed. A bare `\centering` has no braces for the
  inline rule to catch, so figures *must* use the fence, not loose commands. Give
  each `\caption` a short form (`\caption[short]{long}`) so the List of Figures
  stays one line per entry.
- **Table captions** — a pandoc-style line `Table: caption text {#tab:label}`
  directly above a pipe table turns it into a numbered table float with that
  caption and label, listed in the List of Tables and citable as
  `Table~\ref{tab:label}`. A table without one stays an unnumbered block.

`check_thesis_tex.py` fails if a figure or table label is never referenced, if a
`\cite` key is missing from `references.bib`, if a `.bib` entry is never cited
(there is no `\nocite{*}`), or if an at-sign appears anywhere in `references.bib`
outside an entry header. BibTeX has no comment syntax: an at-sign even on a
`%` line starts a broken entry that BibTeX silently skips, which is exactly what a
comment written on 2026-09-19 did.

HTML comments (`<!-- ... -->`) in the markdown are skipped entirely — that is
where build notes belong, so they never reach the typeset page.

## Swapping in the institute's template

Everything above `\begin{document}` in `thesis.tex` is scaffolding meant to be
replaced. Five things to check:

- **Sectioning level.** The body uses `\section` / `\subsection`. If the class
  expects `\chapter` at top level, edit the two emitters in the `heading()`
  function of `scripts/md_to_latex.py` and regenerate.
- **Packages the body needs:** `booktabs`, `graphicx`, `listings`, `xcolor`
  (must load *before* `\lstset`, which uses `\color`), `amsmath`/`amssymb`,
  `caption` with `\captionsetup[table]{position=top}` (table captions are emitted
  above their tables), `hyperref` (the bibliography's `\url`s need it; the
  `hypertexnames=false` option silences duplicate-page-anchor warnings caused by
  `titlepage`), and `hyphenat` with `\emergencystretch` — see the next point.
- **Margins.** Appendix B tabulates long file names in `\texttt{}`, which TeX
  will not break. Without `\usepackage[htt]{hyphenat}` and
  `\setlength{\emergencystretch}{3em}` the build throws 48 overfull warnings, the
  worst running 133pt (~4.6 cm) past the right margin. Measured with and without.
- **Front matter.** The `titlepage` class option gives the title its own page;
  the contents, the List of Figures and List of Tables (one page), and the
  abstract then follow unnumbered, and the body starts at printed page 1. If the
  institute mandates roman front matter, add `\pagenumbering` around the front
  matter block.
- **Bibliography style.** `plain` (numeric) at present; swap in the institute's
  `.bst` on the `\bibliographystyle` line. Every entry is cited inline with
  `\cite{...}` from `docs/THESIS.md` (added 2026-09-20), so there is no
  `\nocite{*}`; an entry nobody cites simply does not appear, and the check script
  reports it.

## Numbering — why it already matches

The markdown carries manual numbers (`## 6. Results`, `### 6.9 ...`). The
converter **strips** them and lets LaTeX number the sections, which reproduces
the identical numbers because the markdown is sequential and gapless, with the
Abstract and Appendices handled separately so they consume no section number.
Verified in the built PDF: sections run 1–9 with 6.1–6.9 nested correctly, and
appendices A–B. This matters because the prose contains ~54 cross-references of
the form "see §6.8". **If you add or reorder a section, re-check them** — the
converter cannot.

## Before you submit

- [x] ~~Verify every bibliography entry.~~ **DONE 2026-08-10** — all checked
      against arxiv.org / CVF Open Access. Two were wrong and are fixed: the
      VL-JEPA title had been invented (it is *"Joint Embedding Predictive
      Architecture for Vision-language"*, Chen, Shukor, Moutakanni, Chung, Yu,
      Kasarla, Bang, Bolourchi, LeCun, Fung), and LiveCC's venue was a
      placeholder (CVPR 2025, arXiv:2504.16030).
- [x] ~~Insert the figures.~~ **DONE 2026-08-18** — 14 images in 11 figure
      environments, captioned, cross-referenced, placed per Appendix B.
- [x] ~~Compile it once.~~ **DONE 2026-08-18** — clean build, no errors.
- [x] ~~Accuracy and formatting fix pass.~~ **DONE 2026-09-20** (details in
      WORKLOG):
      - the paper's benchmark is now described correctly;
      - significance is stated per metric;
      - full tables, including the rows where uniform wins;
      - pre-smoothing is disclosed;
      - a split sentence is rejoined, and the VL-JEPA reference now prints its
        arXiv id;
      - 16 verified references, all cited inline;
      - numbered, captioned tables, and every float referenced from the text.
- [ ] **Swap in the institute's template** (section above), including its
      citation style.
- [ ] **Confirm the date.** `\date{\today}` prints the compile date. Replace it
      with the submission date before printing.
- [ ] Add the declaration / certificate / acknowledgements the institute
      mandates (a commented placeholder sits in `thesis.tex`).
- [ ] Re-read §7–§9 and the abstract. Those were rewritten late and are the
      sections most worth putting in your own voice.

## Likely first-build errors

| Symptom | Cause | Fix |
|---|---|---|
| `Undefined control sequence \toprule` | `booktabs` not loaded | keep `\usepackage{booktabs}` |
| `File 'thesis_body.tex' not found` | uploaded the folder, not its contents | the zip is flat by design; re-upload it rather than a nested folder |
| Figures missing, text fine | `figures/` not uploaded, or renamed | run `check_thesis_tex.py`; it lists every path it cannot resolve |
| Bibliography prints nothing | BibTeX not run | run `bibtex thesis`, then `pdflatex` twice |
| An entry is missing, or `[?]` in the text | a key typo, or an at-sign in a `references.bib` comment made BibTeX skip entries | run `check_thesis_tex.py`; it reports both |
| A table runs into the margin | `hyphenat` / `\emergencystretch` dropped in the template swap | restore both; see "Margins" above |
| `Missing $ inserted` | a stray `_`, `^` or `%` reached the output | a converter bug, not a content one — report it |
