# LiveJEPA — session bootstrap

Master's-thesis project: reconstruction of VL-JEPA's selective decoding
(frozen V-JEPA 2 → 29.9M trained predictor → SONAR → decode only on semantic
shift, τ=0.15).

**Read in this order before doing anything non-trivial:**
1. `HANDOFF.md` — full state, file map, gotchas, commands (master handoff).
2. `WORKLOG.md` — newest entry = where work actually stands.
3. Persistent memory index (auto-loaded) — cross-session facts.

**Inviolable rules:**
- `data_cache_coin_full/pipeline_state.json` and `*/VAL_UIDS.txt` are never
  overwritten by merges; merge lane tars ONLY with `scripts/merge_cache_tar.py`.
- Frozen benchmarks stay frozen: `data_cache_coin2_val` (137 samples) and the
  7 uids in `eval_data/frozen_val_uids.txt` are never trained on; scaling-table
  rows use identical recipe (30k steps ↔ documented) + identical vals.
- `.ps1` files: pure ASCII (PowerShell 5.1 chokes on em-dashes).
- Files consumed by POSIX tools: write LF (`newline='\n'`), never CRLF.
- `grep` on pipeline/training logs: always `-a` (NUL bytes flip it to binary
  mode and it silently swallows output).
- Kaggle notebooks are GENERATED (`scripts/make_c1_notebook.py`) — never
  hand-edit the .ipynb. API pushes update the draft but run CPU-only and fail
  at the CUDA check (expected); only the user's web commit gets GPU, and they
  must F5 first after any push.
- Secrets: user places them in files themselves (`~/.aws/credentials`,
  `~/.kaggle/access_token`) and says "creds are in" — never in chat. Public
  tunnels are launched by the user.
- `WORKLOG.md` is updated daily, unprompted (user's standing order).
- Honest-numbers culture: negative results are logged as findings, never hidden.

**Environment:** Windows 11, PowerShell 5.1, local NVIDIA T1000 8GB (serve/eval/
light training), Kaggle web-commit T4 for GPU bursts, RunPod 4090 rentals only
at approved gates. User: Kaggle beginner, IST, budget in ₹, informal/voice-typed
messages — give exact click-level instructions and confirm before spending.
