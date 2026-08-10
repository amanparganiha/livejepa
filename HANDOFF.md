# LiveJEPA — MASTER HANDOFF (written 2026-07-19)

> **Purpose of this file:** complete continuity for ANY future assistant/model
> session (written when the user anticipated switching from Claude Fable 5 to
> Opus 4.8). Read this first, then the newest entry of `WORKLOG.md`, then the
> persistent memory index (auto-loaded). Everything here is verified as of
> 2026-07-19 morning.

---

## 1. What this project is

**LiveJEPA** (Master's thesis, user: Aman) reconstructs the *selective decoding*
mechanism of VL-JEPA (arXiv:2512.10942 — paper code/weights UNRELEASED, which is
the novelty) from released components:

```
video frames (16 @ 2fps)
   → frozen V-JEPA 2 encoder (326.0M params)          [watch]
   → trained predictor (29.9M — the ONLY trained part) [predict]
   → SONAR text-embedding space (enc 766.1M / dec 1,370.6M)
   → SegmentTrigger: decode ONLY when semantic shift 1−cos > τ=0.15  [speak]
```

Total ~2.5B params, 1.2% trained. The 1.37B SONAR decoder sleeps through ~90%
of windows — that's the whole "selective decoding" argument in one number.

**Thesis claim (honest, nuanced):** adaptive selective decoding Pareto-dominates
uniform decoding on *temporally-redundant* streams (COIN ~1.6×, EgoExo keysteps
~2.5× fewer decodes at equal CIDEr) but the advantage is regime-dependent: it
ATTENUATES on noisy predicted streams and INVERTS on hyper-dense streams
(densest-15 EgoExo atomic pilot: uniform won every budget). The boundary-mapping
("when does selective decoding pay?") is a deliberate, publishable contribution.
SONAR (invertible) replaces the paper's EmbeddingGemma (encode-only) by design —
absolute parity with the paper is NOT the claim.

## 2. State snapshot (2026-07-19)

**DONE:**
- Core mechanism + online trigger (`livejepa/selective/online.py`, SegmentTrigger
  with `last_shift`), 13/13 tests green.
- Product webapp deployed (FastAPI backend + product UI, token
  `livejepa-demo-2026`, tunnel-verified, 15/15 E2E). Server currently RUNNING,
  serving `checkpoints_c1_final/predictor_30000.pt`.
- **Full-COIN data engine CLOSED (2026-07-19 afternoon): 8,984/9,023 resolved =
  99.6%** (7,334 extracted / 1,650 dead links / 39 unreachable, abandoned).
  Local master: `data_cache_coin_full{,_val}` = 26,863 train + 977 val clips.
  (C1 ckpt was trained on 26,360 — the +503 late clips join C2-era training;
  do NOT retrain the C1 row, it breaks scaling-table comparability.)
- **FINAL C1 checkpoint trained (2026-07-18 night, T1000, 30k steps, batch 32).**

  | training clips | frozen 137-val cos | fresh 956-val cos | pred-pred |
  |---|---|---|---|
  | 2,962 (`checkpoints_kaggle/predictor_20000.pt`) | 0.772 | 0.667 | 0.527 |
  | 5,529 (`checkpoints_c1_p1/predictor_20000.pt`) | 0.883 | 0.733 | 0.467 |
  | **26,360 (`checkpoints_c1_final/predictor_30000.pt`)** | **0.897** | **0.846** | **0.408** |

  Curve still climbing → **C2 APPROVED by user (Action100M on rented 4090,
  Jul 25–26, ~₹800–1,500)**.
- **EgoExo4D benchmark data 100% on disk** (creds expire Aug 1 but nothing more
  is needed): 786/786 annotated val takes with video, 61 GB,
  `eval_data/egoexo/takes/`. Selection lists: `eval_data/egoexo_takes_218.txt`
  (density-matched paper protocol) + `egoexo_takes_pred40.txt` (8-scenario
  predictor-mode subset).

---

### UPDATE 2026-08-02 — EXPERIMENTS AND PACKAGING BOTH COMPLETE

Everything in the July week-plan below this line is **done**. Nothing is running.
Read `WORKLOG.md` 2026-08-01 and 2026-08-02 for the detail.

**The thesis headline (§5b RESULTS / §6.8 THESIS):** an *in-domain* EgoExo
predictor (`checkpoints_egoexo/predictor_20000.pt`, gate cos 0.599) makes adaptive
win **7/8 budgets at ≈9.9× fewer decodes** on the paper's own atomic-description
benchmark — reconciling the §5 negative (uniform wins 8/8 on the *raw annotation*
stream). **Selective decoding needs a PREDICTED stream, not dense labels.**
Significant at every budget (paired bootstrap, 40 takes), and at **87.1% of a
provable ceiling** — so the residual headroom is the predictor, not the trigger.

**Results since the snapshot above:**
- D.1 (218-take gt-mode): uniform wins 8/8 — the redundancy limit, RESULTS §5.
- C2 (Action100M, 4090 rental ~$8): clean negative; COIN-trained models beat it on
  A100M's *own* val at matched scale. Cause = target-vocabulary **entropy**
  (COIN 747 captions / 36× repeats vs A100M 6,096 / 1.1×), not label noise.
- C3 (combined 33,573 clips): also negative, −0.022 on COIN. **C1-final stays
  deployed.**
- D.4 (in-domain EgoExo predictor): the headline above.
- Rigor: `scripts/eval_rigor.py` (paired bootstrap + GT-boundary reference),
  `scripts/eval_ceiling.py` (dense / best-frame / best-window bounds, ~2 min,
  needs no SONAR decode), `scripts/make_thesis_figures.py`.

**Packaging state:** `thesis_materials/` fully refreshed 2026-08-02 — 32 artifacts
in `figures/`, `INDEX.md` (figure→section map + viva notes), `TABLES.md` (14
tables). `docs/THESIS.md` sections reordered to 6.1–6.9 and §7/8/9 rewritten (they
had contradicted the Results chapter). **The only work left is format conversion
into the institute's LaTeX/Word template + reference styling.**

**Gotcha added:** an upper bound that loses to the method it bounds is a bug —
but if it still loses after the bug is fixed, the *label* was wrong; re-derive
what the condition actually bounds. (Cost ~3 h of re-runs to learn.)

---

**REMAINING (the July week plan — ALL COMPLETE, kept for provenance):**
1. ~~Mon: D.1 218-take results → analysis (compare vs pilot's inversion).~~
2. ~~Mon night: WS2 full-system COIN Pareto with the final ckpt.~~
3. ~~Midweek: RESULTS.md + docs/THESIS.md updated with scaling table + D.1.~~
4. ~~Jul 25–26: C2 rental (RunPod 4090, kit in `deploy/`).~~
5. ~~Package: final RESULTS/THESIS/thesis_materials update.~~
   Still deliberately deferred: pretrained-VLM variant, institute thesis template,
   LiveCC qualitative baseline, scaling the headline 40→218 takes (~84 h, judged
   not worth it — significance is already established).

## 3. File map

| Path | What |
|---|---|
| `livejepa/` | core package (train.py, run_eval.py, selective/, data/, encoders/) |
| `scripts/` | all pipelines: `coin_full_pipeline.py` (chunked extract), `eval_predictor.py`, `merge_cache_tar.py` (ALWAYS use for tar merges), `select_egoexo_takes.py`, `make_c1_notebook.py` + `make_colab_notebook.py` (NEVER hand-edit ipynbs — regenerate), `make_cloud_bundle.py`, `download_action100m.py`, `build_action100m_cache.py` |
| `configs/default.yaml` | local GPU config (cuda, no stubs, transformers SONAR) |
| `data_cache_coin_full{,_val}` | THE MASTER training cache (26,360+956 clips). `pipeline_state.json` + `VAL_UIDS.txt` are SACRED — merges must never overwrite |
| `data_cache_coin2_val` | frozen 137-sample benchmark val (never train on its 7 videos; uids in `eval_data/frozen_val_uids.txt`) |
| `checkpoints_c1_final/` | the champion (predictor_30000.pt, cos 0.846) |
| `checkpoints_c1_p1/`, `checkpoints_kaggle/` | mid + old ckpts (scaling rows) |
| `eval_data/egoexo/` | annotations + 786 take videos (61 GB) |
| `eval_data/coin_union_state.json` | all-lane done/dead union (embedded into the Kaggle notebook by make_c1_notebook.py) |
| `backups/` | banked lane tars (kaggle p1–p6 chain cumulative, colab p8) |
| `webapp/` | backend.py + static/index.html (product UI) + start/stop ps1 |
| `deploy/kaggle_autopilot/` | kernel-metadata.json + run_daily.ps1 (noon Windows task `LiveJEPA_KaggleAutopilot` downloads newest tar to backups\) |
| `deploy/` + `docs/SYSTEM_DESIGN.md` | RunPod cloud kit + 18-section design |
| `WORKLOG.md` | daily log — UPDATE DAILY UNPROMPTED (user's standing order) |
| `RESULTS.md`, `docs/THESIS.md`, `thesis_materials/` | results + thesis draft (pre-scaling-table numbers — need midweek update) |
| `results_egoexo_atomic_pilot.{json,png}` | densest-15 pilot (uniform wins — boundary condition) |

## 4. Credentials & security (POINTERS ONLY — never paste secrets in chat)

- **EgoExo4D AWS creds**: `~/.aws/credentials` [default] — valid to **Aug 1**.
  All needed data already downloaded; only re-download would need them.
- **Kaggle**: CLI authed via `~/.kaggle/access_token` (KGAT). Kernel:
  `amanparganiha/notebook3308534b33`. Advise user to revoke tokens post-project.
- **Webapp token**: `livejepa-demo-2026` (env `LIVEJEPA_TOKEN`).
- **RULE:** user places secrets in files themselves and says "creds are in";
  never ask them to paste keys into the conversation. Public tunnels are
  launched by the user, not the assistant.

## 5. Hard-won gotchas (violate these and you WILL lose a day)

1. **PS 5.1 + .ps1 files: pure ASCII only** (em-dashes = parse errors).
2. **Windows CRLF**: files feeding POSIX tools must be written LF
   (`open(..., newline='\n')`); a CRLF uid list once made a 218-take download
   match ZERO takes.
3. **`grep` on pipeline logs needs `-a`** — progress bars contain NULs; without
   -a grep flips to binary mode and silently swallows everything after.
4. **Kaggle free tier:** scheduled notebooks AND API-pushed runs are CPU-ONLY.
   Only the user's web "Save Version → Save & Run All" gets GPU. An API push
   updates the DRAFT (next user commit runs the new code) but its own run dies
   at the cell-2 CUDA check — harmless, expect a "failed" email. After any API
   push the user MUST F5 the notebook tab or commits 409
   (ConcurrencyViolation).
5. **Kaggle 429s on saving thousands of small files** → PACK cell tars
   everything; Kaggle AUTO-EXTRACTS tars uploaded as datasets (but NOT
   notebook-output tars mounted via kernel_sources self-input).
6. **YouTube throttling**: ~400–500 downloads/IP/day; pipeline has
   fatal-vs-transient classification + 15-streak breaker + `--retry-dead`.
   Colab IPs are permanently blackholed (lane retired). Institute IP recovers
   after hours of cooldown.
7. **Merges**: ONLY via `scripts/merge_cache_tar.py` (copies npz+txt, skips
   dups, never touches pipeline_state.json/VAL_UIDS.txt). An npz-only merge
   once orphaned 2,888 clips.
8. **Frozen benchmarks are sacred**: `data_cache_coin2_val` (137), the 7 uids in
   `eval_data/frozen_val_uids.txt`, and identical eval recipes are what make
   the scaling table valid.
9. **SONAR needs native-scale embeddings** (norm ~0.196); unit-norm decodes to
   empty strings (predictor rescales internally — see memory
   `sonar-native-scale`).
10. **Stray `inspect.py`** occasionally shadows stdlib in tmp dirs — delete it.
10b. **Rented pods: NEVER train off a network volume.** RunPod's `/workspace` is
    network-attached; each step reads 64 small .npz and per-file latency starves
    the GPU (measured 2026-07-25: **0% GPU, 2h20m per 1,000 steps**). Untar the
    cache to local container disk (`/root/cache`) first → **98% GPU, ~35× faster**.
    Also: pods are the wrong tool for YouTube extraction (one IP → throttled after
    ~200 videos); use Kaggle for extraction (fresh IP per session), pods for
    training only.
11. Notebook self-input resumes from the LATEST SUCCESSFUL version's output;
    failed runs don't break the chain.
12. Trigger τ=0.15; demo shift-meter verified crossing exactly at caption fire.

## 6. Commands cookbook

```powershell
# demo server (from repo root)
$env:LIVEJEPA_CKPT="<abs path to .pt>"; $env:LIVEJEPA_TOKEN="livejepa-demo-2026"
powershell -ExecutionPolicy Bypass -File webapp\start_server.ps1   # background it
powershell -ExecutionPolicy Bypass -File webapp\stop_server.ps1
```
```bash
# gate a checkpoint (ALWAYS these two vals for the scaling table)
python scripts/eval_predictor.py --ckpt <ckpt> --val data_cache_coin2_val --decode
python scripts/eval_predictor.py --ckpt <ckpt> --val data_cache_coin_full_val

# train (identical recipe = table-comparable)
python -m livejepa.train --config configs/default.yaml --data-root data_cache_coin_full \
  --ckpt-dir <dir> --max-steps 30000 --batch-size 32

# paper-protocol EgoExo eval (gt-mode needs no ckpt/video)
python -m livejepa.run_eval --dataset egoexo --mode gt --gt-source atomic \
  --uids-file eval_data/egoexo_takes_218.txt --out results_egoexo_atomic_218

# full-system Pareto on held-out COIN
python -m livejepa.run_eval --dataset coin --mode predictor \
  --ckpt checkpoints_c1_final/predictor_30000.pt --coin-split val --out results_coin_predictor_c1

# merge a lane tar into the master
python scripts/merge_cache_tar.py backups/coin_cache_pN.tar

# regenerate + push the Kaggle notebook (draft only; user commits for GPU)
python scripts/make_c1_notebook.py
cp notebooks/kaggle_c1_full_coin.ipynb deploy/kaggle_autopilot/notebook3308534b33.ipynb
kaggle kernels push -p deploy/kaggle_autopilot

# fleet status
kaggle kernels status amanparganiha/notebook3308534b33
python -c "import json;st=json.load(open('data_cache_coin_full/pipeline_state.json'));print(len(st['done']),len(st['dead']))"
```

## 7. Continuity mechanisms (how the next model picks this up)

1. **Persistent memory** (`~/.claude/projects/<this-project>/memory/`) —
   auto-loaded index every session, model-agnostic. Key files:
   livejepa-progress, livejepa-plan, livejepa-data-engine, livejepa-demo-state,
   livejepa-environment, sonar-native-scale, livejepa-worklog-habit.
2. **`CLAUDE.md`** (repo root) — auto-loaded when working in this repo; points
   here and lists the inviolable rules.
3. **`WORKLOG.md`** — the daily narrative. STANDING ORDER: update it every
   working day without being asked (user request 2026-07-16, format approved).
4. **Plan file** `~/.claude/plans/gentle-sauteeing-glacier.md` — the approved
   ideal-route plan (Hybrid compute).
5. The user communicates informally (often voice-typed with typos), is a Kaggle
   beginner, budget-conscious (₹), timezone IST. Guide them with exact clicks,
   confirm before spending money, and keep the "honest numbers" culture — never
   inflate results, log negative findings as findings.

**The single most important sentence for a fresh model:** everything is
verified-on-disk and reproducible; trust WORKLOG.md + this file over any stale
doc, keep the frozen vals frozen, and finish the week plan in §2.
