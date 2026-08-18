"""Static checks on the thesis sources, before handing them to a TeX engine.

Run after scripts/md_to_latex.py and before uploading to Overleaf:

    python scripts/md_to_latex.py
    python scripts/check_thesis_tex.py

Why this exists. The build loop for this thesis is markdown -> generated .tex ->
Overleaf, and the failure modes are mostly silent: a figure path that does not
resolve, a \\ref with no \\label, an unbalanced environment. A TeX log will find
them eventually, but it is a long way from the markdown you actually edit.

The control-character check earns its place from a real bug. Repairing a caption
with re.sub, the replacement template "\\ref{...}" was interpreted by re itself
-- \\r became a carriage return -- so the markdown ended up holding CR + "ef{...}".
LaTeX compiled it without error and the PDF read "the negative that Figure
effig:egoexo-indomain resolves". Nothing in the build log mentioned it. Stray
control characters also violate the repo's LF-only rule for POSIX-consumed files.

Exit status is 0 when every check passes, 1 otherwise, so it can gate a commit.
"""
import io
import os
import re
import sys

B = chr(92)          # backslash, never written as a literal escape
MD = "docs/THESIS.md"
TEX_DIR = "thesis_materials"
BODY = "thesis_body.tex"
MAIN = "thesis.tex"


def strip_comments(s):
    """Drop TeX comments before counting anything.

    thesis.tex documents the template swap in its own header, and that prose
    says "everything above \\begin{document}" -- which a naive count reads as a
    second, unclosed document environment. Comments are commentary, not markup.
    An escaped \\% is not a comment and must survive.
    """
    out = []
    for line in s.split("\n"):
        cut = None
        for m in re.finditer("%", line):
            j = m.start()
            if j == 0 or line[j - 1] != B:
                cut = j
                break
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


def check_markdown(problems):
    """The source of truth. Anything wrong here is regenerated into the .tex."""
    if not os.path.exists(MD):
        problems.append("missing %s" % MD)
        return
    s = io.open(MD, encoding="utf-8", newline="").read()
    ctrl = [(i, repr(c)) for i, c in enumerate(s) if ord(c) < 32 and c != "\n"]
    if ctrl:
        for i, c in ctrl[:5]:
            problems.append("control char %s at offset %d in %s: ...%s..."
                            % (c, i, MD, s[max(0, i - 40):i + 25]))
    else:
        print("markdown: no stray control characters (LF-only)   OK")

    # A ```latex fence must close, or the rest of the document is swallowed raw.
    fences = re.findall(r"^```(\w*)", s, re.M)
    if len(fences) % 2:
        problems.append("odd number of ``` fences in %s (%d)" % (MD, len(fences)))
    else:
        print("markdown: %d code fences, balanced                OK" % len(fences))


def check_tex(problems):
    body_p = os.path.join(TEX_DIR, BODY)
    main_p = os.path.join(TEX_DIR, MAIN)
    for p in (body_p, main_p):
        if not os.path.exists(p):
            problems.append("missing %s" % p)
            return
    body = io.open(body_p, encoding="utf-8").read()
    s = strip_comments(body + "\n" + io.open(main_p, encoding="utf-8").read())

    paths = re.findall(B + B + r"includegraphics\[[^\]]*\]\{([^}]+)\}", s)
    missing = [p for p in paths
               if not os.path.exists(os.path.join(TEX_DIR, p))]
    print("figures referenced: %d, missing: %d" % (len(paths), len(missing)))
    for p in missing:
        problems.append("figure not found: %s/%s" % (TEX_DIR, p))

    labels = re.findall(B + B + r"label\{([^}]+)\}", s)
    refs = re.findall(B + B + r"ref\{([^}]+)\}", s)
    for r in refs:
        if r not in labels:
            problems.append("dangling ref: %s" % r)
    for l in sorted({x for x in labels if labels.count(x) > 1}):
        problems.append("duplicate label: %s" % l)
    print("labels: %d, refs: %d, dangling: %d"
          % (len(labels), len(refs), len([r for r in refs if r not in labels])))

    for env in ("figure", "tabular", "center", "abstract", "itemize",
                "enumerate", "lstlisting", "document"):
        o = len(re.findall(B + B + r"begin\{" + env + r"\}", s))
        c = len(re.findall(B + B + r"end\{" + env + r"\}", s))
        if o != c:
            problems.append("unbalanced %s: %d begin vs %d end" % (env, o, c))
    print("environments balanced                            OK"
          if not any("unbalanced" in p for p in problems) else "environments UNBALANCED")

    left = sorted({c for c in body if ord(c) > 127})
    if left:
        problems.append("non-ASCII in generated body: %s" % left)
    else:
        print("generated body is pure ASCII                     OK")


def main():
    problems = []
    check_markdown(problems)
    check_tex(problems)
    print()
    if problems:
        print("FAIL (%d problem(s)):" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
