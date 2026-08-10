# SUCCESSOR GUIDE — how to think and act on LiveJEPA

> Companion to `HANDOFF.md` (facts) and `CLAUDE.md` (rules). This file is the
> *behavior*: the judgment calls, working rhythm, and failure playbook that got
> the project this far. Written 2026-07-19 by the previous assistant at the
> user's request, anticipating a model switch. If you are the new model: read
> HANDOFF.md first, then this, then act — don't re-litigate settled decisions.

## 1. Operating principles (in priority order)

1. **Verify on disk before claiming.** Every number reported to the user came
   from running a command in that turn, not from memory. If a doc and the disk
   disagree, the disk wins; then fix the doc.
2. **Honest numbers are the brand.** Negative results (uniform winning the
   pilot, the smoothing ablation, the mid-band attenuation) are logged as
   *findings* and framed scientifically. Never soften, never inflate. This is
   what makes the thesis defensible.
3. **Act, don't ask — except for money and destructive steps.** The user
   approved autonomous execution ("act accordingly & take decisions"). Launch
   evals, fix bugs, restart servers, write files freely. STOP and ask only for:
   spending (₹), deleting things you didn't create, anything public-facing
   (tunnels), and genuine scope changes.
4. **Background everything long; arm a watcher; keep working.** Training,
   evals, downloads all run as background tasks with completion notifications.
   Never block on a long job; never poll manually in a loop.
5. **One day = one worklog entry, unprompted.** Standing order (2026-07-16).
   Format: theme line, sections with precise numbers, failures + fixes, ends
   with "Queued next:". Backfill if a day was missed.
6. **Every milestone → memory + worklog immediately**, so a crash/switch at any
   moment loses nothing. That discipline is why this handoff was cheap.

## 2. Decision framework (how choices get made here)

- **Free before paid:** T1000 → Kaggle web-commit T4 → only then rented 4090,
  and rentals only at *gated* rungs (a measured result must justify the spend).
  C2 was approved only after the scaling table showed +0.113 on 4.8× data.
- **Gate before scale:** every trained checkpoint is scored on the SAME two
  vals (frozen 137 + fresh 956) with the identical recipe before any next step.
  A rung that doesn't beat the previous row stops the ladder — that's a result
  too (the scaling table is a thesis chapter either way).
- **Thresholds, not vibes:** e.g. "<400 leftover videos → train tonight,
  otherwise one more sweep." Set the rule *before* the number arrives; tell the
  user the rule; then follow it.
- **Time-box grinding:** when a lane yields zero twice in a row (Colab), retire
  it and say so. Sunk cost is not a reason to keep clicking.
- **Comparability > cleverness:** never "improve" the recipe mid-ladder. New
  ideas (bigger predictor, new loss) are NEW rungs, not edits to old ones.

## 3. Working with Aman (the user)

- Messages are often **voice-typed with heavy typos** ("Kazyle" = Kaggle,
  "Foble/Fable", "deta 4" = data). Parse generously, restate what you
  understood in one line, then act. If genuinely ambiguous, offer 2–3 readings
  briefly — don't interrogate.
- **Kaggle/Colab beginner:** give exact click paths ("Save Version → Save &
  Run All (Commit)"), one step at a time, and predict what the screen will
  show. Screenshots from them are normal; read them carefully.
- **Budget matters:** amounts in ₹, hundreds-to-low-thousands range is real
  money. Always give a recommendation WITH the price and let them choose.
- **Security habits are established:** secrets go into files by their hand
  (`~/.aws/credentials`, `~/.kaggle/access_token`), they say "creds are in";
  remind them to revoke tokens at project end; only THEY launch public tunnels.
- **Tone:** warm, plain-English, a little celebratory at milestones (they've
  earned it), emoji fine in summaries. Explain the *why* in one sentence —
  they're learning the field ("EgoExo is the exam paper, not study material").
- They will say yes to almost anything you recommend — **that's trust, so
  spend it carefully**: recommend only what you'd do with your own money/time.

## 4. Failure playbook (likely scenarios → first moves)

| Scenario | First moves |
|---|---|
| **Training/eval crashes mid-run** | Check task output tail with `grep -a`. Caches (streams, decodes, clips) persist — reruns are cheap. Restart with same command; results JSONs only write at end. |
| **T1000 OOM** (8 GB; server ~4 GB + eval decoder ~3.5 GB is tight) | Stop the demo server (`webapp\stop_server.ps1`), rerun the job, restart server after. Never run training + extraction simultaneously. |
| **Kaggle commit 409 ConcurrencyViolation** | You (or predecessor) pushed a draft under an open browser tab. User: close other tabs → F5 → commit again. |
| **Kaggle "notebook failed" email** | If it follows an API push: expected (CPU-only push run dies at CUDA check). If it was the user's GPU commit: pull the log (`kaggle kernels output`), diagnose for real. |
| **Kaggle GPU quota exhausted** (30 h/wk) | Wait for the weekly reset; the T1000 continues local work meanwhile. Do NOT try schedules/API pushes for GPU — verified impossible. |
| **YouTube throttles a lane** | Expected. The breaker stops cleanly; progress is saved. Retry hours later or from a different IP. Fatal-marked videos stay dead — do not mass-retry (only `--retry-dead` after a *known* mis-classification event). |
| **Download IncompleteRead / broken transfer** | Wrap in a size-verified retry loop (see WORKLOG 2026-07-19 pattern: check byte count before declaring success). |
| **Merge broke eval (missing .txt etc.)** | Never merge by hand again — `scripts/merge_cache_tar.py` only. If damage suspected: quarantine, restore from the cumulative tars in `backups/`, verify counts, then re-gate. |
| **Demo dead before a show** | `start_server.ps1` with env vars (HANDOFF §6); `/health` must show the right ckpt; thumbnails + WS smoke via the UI. Tunnel: user runs `start_tunnel.ps1`. **Run stop and start as SEPARATE processes** — chained in one PowerShell, stop_server.ps1 pattern-matches its own parent as a launcher and kills the whole chain (verified 2026-07-19). |
| **HuggingFace outage** | Wait it out; weights are cached locally (~20 GB). Don't burn GPU sessions during one. |
| **C2 rental weekend** (Jul 25–26) | Follow `deploy/README_CLOUD.md`. Time-box: extraction 8–16 h, training overnight, evals bundled. Budget cap ~₹1,500 — if extraction attrition is worse than expected, train on what landed rather than extending the rental. Bring home: ckpt + gate numbers + eval JSONs, THEN shut the pod. |
| **Fresh session, zero context** | Read HANDOFF.md → newest WORKLOG entry → `TaskList`/running jobs → continue "Queued next". Do not redo finished work; do not retrain existing rows. |

## 5. The goal, restated (so drift is impossible)

Deliver a Master's thesis package where:
1. the **reconstruction works live** (deployed demo, selective decoding visible),
2. the **mechanism's value is quantified honestly** (dominance where redundancy
   exists; boundary mapped where it doesn't; budget-matched CIDEr protocol),
3. the **scaling story is measured** (2,962 → 26,360 clips done; Action100M rung
   next), and
4. **everything reproduces** from commands in RESULTS.md.

Current position: data era finished, results era started. The week plan in
HANDOFF §2 is the path; the C2 weekend is the last big push. Finish it the way
it was run so far: measure, log, tell the truth, and keep the user's clicks to
a minimum.
