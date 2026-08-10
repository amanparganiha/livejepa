# Building the thesis PDF

## Status — read this first

`thesis.tex`, `thesis_body.tex` and `references.bib` were written and
structurally verified (balanced braces and environments, no stray non-ASCII, all
10 tables well-formed), **but they have never been compiled** — there is no TeX
toolchain on this machine. Expect the first build to surface one or two small
errors. The likely ones and their fixes are listed at the bottom.

## Fastest route: Overleaf (free, no install)

1. Go to overleaf.com, **New Project → Upload Project**.
2. Upload these four things from `thesis_materials/`:
   - `thesis.tex` (main file)
   - `thesis_body.tex` (generated body)
   - `references.bib`
   - the `figures/` folder
3. Set **Menu → Main document → `thesis.tex`**, and **Compiler → pdfLaTeX**.
4. Press Recompile. Overleaf runs BibTeX automatically.

## Local build (if you install MiKTeX or TeX Live)

```bash
cd thesis_materials
pdflatex thesis
bibtex   thesis
pdflatex thesis
pdflatex thesis      # twice more so the ToC and references settle
```

## The one rule about editing

`thesis_body.tex` is **generated**. Do not edit it — your changes vanish on the
next regeneration. Edit `docs/THESIS.md` and re-run:

```bash
python scripts/md_to_latex.py
```

The converter deliberately passes raw LaTeX through untouched, so you can put
`\cite{vljepa2025}`, `\ref{...}` or `\label{...}` straight into the markdown and
they survive conversion. Everything else in `thesis.tex` — preamble, title page,
front matter — is hand-written and safe to edit.

## Swapping in the institute's template

Everything above `\begin{document}` in `thesis.tex` is scaffolding meant to be
replaced. Three things to check when you swap:

- **Sectioning level.** The body uses `\section` / `\subsection`. If the
  institute's class expects `\chapter` for top-level, either change the class or
  edit the two `\section{` / `\subsection{` emitters in `scripts/md_to_latex.py`
  (function `heading`) and regenerate.
- **Packages.** The body needs `booktabs` (tables), `listings` (the pipeline
  diagram and the command appendix), and `amsmath`/`amssymb` (inline
  `$\approx$`, `$\times$`, `$\Delta$`, `$\tau$`). Keep those loaded.
- **Bibliography style.** `thesis.tex` uses `plain`. Change
  `\bibliographystyle{}` to whatever is mandated. If you switch to a
  natbib/biblatex style, load the matching package too.

## Numbering — why it already matches

The markdown carries manual numbers (`## 6. Results`, `### 6.9 ...`). The
converter **strips** them and lets LaTeX number the sections. That reproduces
the identical numbers, because the markdown is sequential and gapless, and the
Abstract and Appendices are handled separately so they don't consume section
numbers. This matters: the prose is full of cross-references like "see §6.8",
and after conversion they still point at 6.8. **If you add or reorder a section
in the markdown, re-check those references** — the converter cannot.

## Before you submit

- [x] ~~Verify every bibliography entry.~~ **DONE 2026-08-10** — all seven
      entries checked against arxiv.org / CVF Open Access. Two were wrong and are
      fixed: the VL-JEPA title had been invented (it is *"Joint Embedding
      Predictive Architecture for Vision-language"*, Chen, Shukor, Moutakanni,
      Chung, Yu, Kasarla, Bang, Bolourchi, LeCun, Fung), and LiveCC's venue was a
      placeholder (CVPR 2025, arXiv:2504.16030). Nothing in the thesis prose
      quoted a wrong title — the docs cite VL-JEPA by arXiv ID only.
- [ ] Fill in the author name and submission date in `thesis.tex`.
- [ ] Add the declaration / certificate / acknowledgements the institute
      mandates (a commented placeholder is in `thesis.tex`).
- [ ] Insert figures where you want them. The body does **not** place any
      `\includegraphics` — `INDEX.md` maps every figure to its section, so add
      them as you format. The two that carry the headline are
      `results_egoexo_predictor_40_indomain.png` (§6.8) and
      `results_egoexo_ceiling.png` (§6.9).
- [ ] Re-read §7–§9. Those were rewritten late and are the sections most worth
      putting in your own voice.

## Likely first-build errors

| Symptom | Cause | Fix |
|---|---|---|
| `Undefined control sequence \toprule` | `booktabs` not loaded | keep `\usepackage{booktabs}` |
| `LaTeX Error: File 'thesis_body.tex' not found` | wrong main file or missing upload | set main document to `thesis.tex`; upload both files |
| Bibliography prints nothing | BibTeX not run, or `\nocite{*}` removed | run `bibtex thesis` then `pdflatex` twice |
| A wide table runs into the margin | a cell longer than the converter's 30-char threshold | widen the `p{}` share in `emit_table`, or shorten the cell in the markdown |
| `Missing $ inserted` | a stray `_`, `^` or `%` reached the output | report it — the escaper should have caught it; it is a converter bug, not a content one |
