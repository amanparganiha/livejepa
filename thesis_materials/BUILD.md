# Building the thesis PDF

## Status — read this first

**The document compiles.** Built 2026-08-18 with Tectonic 0.17.0 (a self-contained
TeX engine): exit 0, **zero errors, zero overfull boxes**, BibTeX resolved all 8
bibliography entries, and all 14 figures placed and rendering. **24 pages** — 3
unnumbered front matter (title, contents, abstract) plus 21 numbered, ending with
the references. The PDF was read page by page, not just declared clean by a log.

That does not make an Overleaf build automatic — Overleaf runs pdfLaTeX rather
than Tectonic — but every error class that a first build usually surfaces
(missing figure, unbalanced environment, dangling `\ref`, unescaped character,
missing package) has already been found and fixed here.

## Fastest route: Overleaf

A ready archive is built for you:

```bash
python scripts/make_overleaf_zip.py     # -> livejepa_thesis_overleaf.zip (0.85 MB)
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

Two escape hatches survive conversion:

- **Inline** — `\cite{vljepa2025}`, `\ref{fig:x}`, `\label{...}` written in the
  prose pass through untouched.
- **Block** — anything inside a ```` ```latex ```` fence is emitted byte-for-byte.
  This is how the figures are placed. A bare `\centering` has no braces for the
  inline rule to catch, so figures *must* use the fence, not loose commands.

HTML comments (`<!-- ... -->`) in the markdown are skipped entirely — that is
where build notes belong, so they never reach the typeset page.

## Swapping in the institute's template

Everything above `\begin{document}` in `thesis.tex` is scaffolding meant to be
replaced. Five things to check:

- **Sectioning level.** The body uses `\section` / `\subsection`. If the class
  expects `\chapter` at top level, edit the two emitters in the `heading()`
  function of `scripts/md_to_latex.py` and regenerate.
- **Packages the body needs:** `booktabs`, `graphicx`, `listings`, `xcolor`
  (must load *before* `\lstset`, which uses `\color`), `amsmath`/`amssymb`, and
  `hyphenat` with `\emergencystretch` — see the next point.
- **Margins.** Appendix B tabulates long file names in `\texttt{}`, which TeX
  will not break. Without `\usepackage[htt]{hyphenat}` and
  `\setlength{\emergencystretch}{3em}` the build throws 48 overfull warnings, the
  worst running 133pt (~4.6 cm) past the right margin. Measured with and without.
- **Front matter.** The `titlepage` class option gives the title its own page;
  contents and abstract then follow unnumbered and the body starts at printed
  page 1. If the institute mandates roman front matter, add `\pagenumbering`
  around the front matter block.
- **Bibliography style.** `plain` at present. The body carries no `\cite`
  commands, so `\nocite{*}` is what puts entries on the page; if inline citations
  are required, add `\cite{...}` to `docs/THESIS.md` (it survives conversion) and
  drop the `\nocite{*}` line.

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
| Bibliography prints nothing | BibTeX not run, or `\nocite{*}` removed | run `bibtex thesis`, then `pdflatex` twice |
| A table runs into the margin | `hyphenat` / `\emergencystretch` dropped in the template swap | restore both; see "Margins" above |
| `Missing $ inserted` | a stray `_`, `^` or `%` reached the output | a converter bug, not a content one — report it |
