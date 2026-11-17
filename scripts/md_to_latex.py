"""Convert docs/THESIS.md into a LaTeX body for the institute's template.

Written as a SCRIPT rather than a one-off hand conversion because the markdown
is still the working copy -- a manual .tex would rot the first time a number
changes. Re-run this after any edit to THESIS.md.

It targets the markdown subset that document actually uses (verified by
inventory): ATX headings, pipe tables (with an optional pandoc-style
"Table: caption {#tab:label}" line above them), fenced code, bullet/numbered
lists, inline code, bold, italic, horizontal rules, and a fixed set of
non-ASCII symbols. A ```latex fence is passed through raw, which is how figure
environments are carried from the markdown into the generated body. It
deliberately does NOT try to be a general markdown engine.

Section numbering: the markdown carries manual numbers ("## 6. Results",
"### 6.9 ..."). Those are STRIPPED and LaTeX numbers the sections itself --
which reproduces the identical numbers, because the markdown is sequential and
gapless. Abstract and appendices are handled specially so they do not consume
section numbers. This matters: the prose is full of cross-references like
"see 6.8", and they must still point at 6.8 after conversion.

    python scripts/md_to_latex.py
    python scripts/md_to_latex.py --in docs/THESIS.md --out thesis_materials/thesis_body.tex
"""
import argparse
import os
import re
import sys

# --------------------------------------------------------------------------- #
# character handling
# --------------------------------------------------------------------------- #
SPECIALS = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$",
            "&": r"\&", "#": r"\#", "^": r"\textasciicircum{}", "_": r"\_",
            "~": r"\textasciitilde{}", "%": r"\%"}

UNICODE = {"—": "---", "–": "--", "≈": r"$\approx$", "×": r"$\times$",
           "→": r"$\rightarrow$", "←": r"$\leftarrow$", "§": r"\S",
           "≤": r"$\leq$", "≥": r"$\geq$", "∈": r"$\in$", "Δ": r"$\Delta$",
           "τ": r"$\tau$", "−": "$-$", "±": r"$\pm$", "…": r"\dots{}",
           "“": "``", "”": "''", "‘": "`", "’": "'", "\u00a0": "~"}

# verbatim can't carry these; the diagram is ASCII-art anyway
VERBATIM_ASCII = {"─": "-", "│": "|", "▼": "v", "▶": ">", "←": "<-", "→": "->",
                  "—": "--", "–": "-", "≈": "~", "×": "x", "τ": "tau"}


def esc(s):
    """Escape LaTeX specials, then map known non-ASCII to LaTeX commands."""
    out = "".join(SPECIALS.get(c, c) for c in s)
    for k, v in UNICODE.items():
        out = out.replace(k, v)
    return out


def inline(s):
    """Inline markdown -> LaTeX. Code spans are protected from escaping, and so
    are raw LaTeX commands such as \\cite{key} or \\ref{fig:x} — so citations
    can be added to the MARKDOWN and survive conversion, rather than having to
    be patched into the generated .tex on every regeneration.

    A tie written directly before such a command ("Figure~\\ref{fig:x}",
    "SONAR~\\cite{key}") is kept as a non-breaking space. Everywhere else ~
    means "approximately" in this document and is still escaped."""
    spans, raw = [], []

    def stash(m):
        spans.append(m.group(1))
        return f"\x00{len(spans) - 1}\x00"

    def stash_tex(m):
        raw.append(m.group(0))
        return f"\x01{len(raw) - 1}\x01"

    s = re.sub(r"`([^`\n]+)`", stash, s)
    s = re.sub(r"~?\\[a-zA-Z]+(?:\[[^\]]*\])?\{[^{}]*\}", stash_tex, s)
    s = esc(s)
    if raw:
        s = re.sub(r"\x01(\d+)\x01", lambda m: raw[int(m.group(1))], s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])", r"\\emph{\1}", s)
    s = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", r"\1", s)      # links -> text
    return re.sub(r"\x00(\d+)\x00",
                  lambda m: r"\texttt{" + esc(spans[int(m.group(1))]) + "}", s)


# --------------------------------------------------------------------------- #
# block handling
# --------------------------------------------------------------------------- #
def emit_table(rows, caption=None):
    """Markdown pipe table -> booktabs tabular.

    Alignment comes from the separator row. Columns whose widest cell is long
    become p{} columns sized by their share of the total text, so the wide
    'what it is' explanation tables wrap instead of running off the page.

    With a caption (pandoc's "Table: text {#tab:label}" line directly above the
    table) the tabular becomes a numbered table float, so it appears in the
    List of Tables and can be cited as Table~\\ref{tab:label}. Without one it
    stays an unnumbered centred block."""
    def cells(line):
        return [c.strip() for c in line.strip().strip("|").split("|")]

    head, sep, body = cells(rows[0]), cells(rows[1]), [cells(r) for r in rows[2:]]
    n = len(head)
    body = [(r + [""] * n)[:n] for r in body]

    align = []
    for s in sep:
        align.append("r" if s.endswith(":") and not s.startswith(":")
                     else "c" if s.startswith(":") and s.endswith(":") else "l")

    widths = [max([len(head[i])] + [len(r[i]) for r in body]) for i in range(n)]
    wide = [i for i, w in enumerate(widths) if w > 30]
    spec = list(align)
    if wide:
        share = min(0.42, 0.86 / len(wide))
        for i in wide:
            spec[i] = f"p{{{share:.2f}\\linewidth}}"

    def hcell(h):
        """Header cells are bolded by the template; markdown headers are often
        already **bold**, so don't emit \\textbf{\\textbf{...}}."""
        t = inline(h)
        return t if t.startswith(r"\textbf{") and t.endswith("}") else r"\textbf{" + t + "}"

    grid = [r"\begin{tabular}{" + "".join(spec) + "}",
            r"\toprule",
            " & ".join(hcell(h) for h in head) + r" \\",
            r"\midrule"]
    grid += [" & ".join(inline(c) for c in r) + r" \\" for r in body]
    grid += [r"\bottomrule", r"\end{tabular}"]

    if caption is None:
        return [r"\begin{center}\small"] + grid + [r"\end{center}"]
    label = None
    m = re.search(r"\s*\{#([^}\s]+)\}\s*$", caption)
    if m:
        label, caption = m.group(1), caption[:m.start()]
    head_lines = [r"\begin{table}[htbp]", r"\centering\small",
                  r"\caption{" + inline(caption.strip()) + "}"]
    if label:
        head_lines.append(r"\label{" + label + "}")
    return head_lines + grid + [r"\end{table}"]


def emit_verbatim(lines):
    body = ["".join(VERBATIM_ASCII.get(c, c) for c in l) for l in lines]
    body = [l if all(ord(c) < 128 for c in l) else
            "".join(c if ord(c) < 128 else "?" for c in l) for l in body]
    return [r"\begin{lstlisting}"] + body + [r"\end{lstlisting}"]


def heading(level, text, state, out):
    """Headings, with Abstract/Appendix/References kept out of the numbering."""
    plain = re.sub(r"^\d+(\.\d+)*\.?\s*", "", text).strip()
    low = text.lower()

    if level == 1:
        return                                    # the title lives on the title page
    if level == 2 and low.startswith("abstract"):
        state["abstract"] = True
        out.append(r"\begin{abstract}")
        return
    if level == 2 and low.startswith("appendix"):
        if not state["appendix"]:
            out.append(r"\appendix")
            state["appendix"] = True
        out.append(r"\section{" + inline(re.sub(r"^Appendix\s+\w+\s*[—-]\s*", "", text)) + "}")
        return
    if level == 2 and low.startswith("references"):
        state["stop"] = True                      # bibliography replaces this section
        return
    out.append((r"\section{" if level == 2 else r"\subsection{") + inline(plain) + "}")


def convert(md):
    lines = md.split("\n")
    out, state = [], {"abstract": False, "appendix": False, "stop": False}
    i, para = 0, []
    caption = None                  # a "Table:" line waiting for its table

    def flush_para():
        if para:
            out.append(inline(" ".join(para).strip()))
            out.append("")
            para.clear()

    while i < len(lines):
        line = lines[i]

        if state["stop"]:
            break

        if line.strip().startswith("<!--"):                       # markdown-only
            # An HTML comment is editorial scaffolding for people reading the
            # .md -- build notes, TODOs -- and must not be typeset. THESIS.md
            # opens with one ("this document is written in Markdown for easy
            # conversion..."), which was appearing as the thesis's first
            # sentence until this branch existed.
            flush_para()
            j = i
            while j < len(lines) and "-->" not in lines[j]:
                j += 1
            i = j + 1
            continue

        if line.strip().startswith("```"):                       # fenced code
            flush_para()
            info = line.strip()[3:].strip().lower()
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                j += 1
            block = lines[i + 1:j]
            # ```latex is a RAW passthrough: emitted byte-for-byte, neither
            # escaped nor wrapped in lstlisting. This is how figures reach the
            # generated body. A figure environment cannot survive inline():
            # bare commands like \centering carry no braces, so the raw-LaTeX
            # regex misses them and esc() turns the backslash into
            # \textbackslash{}. Block-level passthrough sidesteps that
            # entirely -- and keeps the figures in the markdown, which is the
            # file the author edits.
            out += (block if info == "latex" else emit_verbatim(block)) + [""]
            i = j + 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para()
            if state["abstract"] and len(m.group(1)) <= 2:
                out.append(r"\end{abstract}"); out.append("")
                state["abstract"] = False
            heading(len(m.group(1)), m.group(2).strip(), state, out)
            out.append("")
            i += 1
            continue

        m = re.match(r"^Table:\s+(.+)$", line.strip())             # table caption
        if m:
            k = i + 1
            while k < len(lines) and not lines[k].strip():
                k += 1
            if k < len(lines) and lines[k].strip().startswith("|"):
                flush_para()
                caption = m.group(1)
                i = k
                continue

        if line.strip().startswith("|"):                          # table
            flush_para()
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            rows = lines[i:j]
            out += (emit_table(rows, caption) if len(rows) >= 2 else
                    [inline(r) for r in rows]) + [""]
            caption = None
            i = j
            continue

        if re.match(r"^\s*[-*]\s+", line) or re.match(r"^\s*\d+\.\s+", line):
            flush_para()
            numbered = bool(re.match(r"^\s*\d+\.\s+", line))
            env = "enumerate" if numbered else "itemize"
            out.append(r"\begin{" + env + "}")
            pat = r"^\s*\d+\.\s+" if numbered else r"^\s*[-*]\s+"
            item = None
            while i < len(lines):
                l = lines[i]
                if re.match(pat, l):
                    if item is not None:
                        out.append(r"\item " + inline(" ".join(item)))
                    item = [re.sub(pat, "", l).strip()]
                elif l.strip() and (l.startswith("  ") or l.startswith("\t")):
                    item.append(l.strip())                        # wrapped continuation
                else:
                    break
                i += 1
            if item is not None:
                out.append(r"\item " + inline(" ".join(item)))
            out.append(r"\end{" + env + "}")
            out.append("")
            continue

        if line.strip() == "---":                                 # rule -> spacing
            flush_para()
            out.append(r"\medskip")
            out.append("")
            i += 1
            continue

        if not line.strip():
            flush_para()
            i += 1
            continue

        para.append(line.strip())
        i += 1

    flush_para()
    if state["abstract"]:
        out.append(r"\end{abstract}")
    # collapse runs of blank lines
    res, prev_blank = [], False
    for l in out:
        blank = (l == "")
        if blank and prev_blank:
            continue
        res.append(l)
        prev_blank = blank
    return "\n".join(res).strip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default="docs/THESIS.md")
    ap.add_argument("--out", dest="dst", default="thesis_materials/thesis_body.tex")
    args = ap.parse_args()

    md = open(args.src, encoding="utf-8").read()
    tex = convert(md)

    left = sorted({c for c in tex if ord(c) > 127})
    if left:
        print(f"WARNING: {len(left)} unmapped non-ASCII char(s): {left}", file=sys.stderr)

    os.makedirs(os.path.dirname(args.dst) or ".", exist_ok=True)
    with open(args.dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(tex)
    print(f"wrote {args.dst}  ({tex.count(chr(10))} lines, "
          f"{tex.count(chr(92) + 'section')} sections, "
          f"{tex.count('tabular') // 2} tables)")


if __name__ == "__main__":
    main()
