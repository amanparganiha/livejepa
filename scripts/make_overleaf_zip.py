"""Build the zip to hand to Overleaf's "New Project -> Upload Project".

    python scripts/md_to_latex.py
    python scripts/check_thesis_tex.py
    python scripts/make_overleaf_zip.py

Overleaf wants the main .tex at the ROOT of the archive, so the zip mirrors
thesis_materials/ rather than containing it -- a nested folder is the usual
reason "Main document" comes up empty on upload.

What is deliberately left out: the .json files each figure was plotted from, the
two demo .mp4s, and the markdown notes. LaTeX reads none of them, and Overleaf's
free tier counts files. Every .png ships, not just the 14 currently placed, so
figures can be added in Overleaf without a re-upload.
"""
import argparse
import io
import os
import re
import sys
import zipfile

SRC = "thesis_materials"
OUT = "livejepa_thesis_overleaf.zip"
PAPER_OUT = "livejepa_paper_ieee_overleaf.zip"
TEXT = (".tex", ".bib")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", action="store_true",
                    help="package the IEEE conference paper (paper_ieee.tex) "
                         "instead of the thesis; ships only the figures it uses")
    args = ap.parse_args()

    if not os.path.isdir(SRC):
        print("run from the repo root: %s not found" % SRC)
        return 1

    if args.paper:
        return build(["paper_ieee.tex", "references.bib"], PAPER_OUT,
                     scan="paper_ieee.tex", only_used=True)
    return build(["thesis.tex", "thesis_body.tex", "references.bib"], OUT,
                 scan="thesis_body.tex", only_used=False)


def build(members, out, scan, only_used):
    used = set()
    scan_p = os.path.join(SRC, scan)
    if os.path.exists(scan_p):
        s = io.open(scan_p, encoding="utf-8").read()
        used = set(re.findall(chr(92) + chr(92) + r"includegraphics\[[^\]]*\]\{figures/([^}]+)\}", s))

    figs = sorted(f for f in os.listdir(os.path.join(SRC, "figures"))
                  if f.lower().endswith(".png") and (not only_used or f in used))
    return write_zip(members, figs, used, out)


def write_zip(members, figs, used, OUT):
    missing = [m for m in members if not os.path.exists(os.path.join(SRC, m))]
    if missing:
        print("missing required file(s): %s" % missing)
        return 1

    if os.path.exists(OUT):
        os.remove(OUT)

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for m in members:
            p = os.path.join(SRC, m)
            # Text files go in with LF endings; a CR reaching a POSIX toolchain
            # is the repo's standing gotcha.
            data = io.open(p, encoding="utf-8", newline="").read()
            data = data.replace(chr(13) + chr(10), chr(10)).replace(chr(13), chr(10))
            z.writestr(m, data.encode("utf-8"))
        for f in figs:
            z.write(os.path.join(SRC, "figures", f), "figures/" + f)

    size = os.path.getsize(OUT)
    print("wrote %s" % OUT)
    print("  %d text files + %d png (%d placed in the body, %d spare)"
          % (len(members), len(figs), len(used), len(figs) - len(used)))
    print("  %.2f MB" % (size / 1048576.0))
    unresolved = sorted(u for u in used if u not in set(figs))
    if unresolved:
        print("  WARNING: body references figures not packaged: %s" % unresolved)
        return 1
    print("  every referenced figure is present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
