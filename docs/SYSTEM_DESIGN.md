# LiveJEPA — Production System Design

*Frontend + backend architecture for deploying the LiveJEPA selective video-captioning
pipeline. Written 2026-07-10, matching the shipped code in `webapp/`. Sections marked
**[built]** exist and are verified; sections marked **[path]** describe the upgrade
route when the stated trigger occurs.*

---

## 1. Product understanding

**Problem.** Continuous video understanding is expensive: decoding a caption for every
window of a stream wastes compute when nothing is happening. LiveJEPA reconstructs
VL-JEPA's *selective decoding*: a frozen V-JEPA 2 encoder feeds a trained predictor
that maps vision to SONAR text-embedding space; the stream of predicted embeddings is
monitored by a change trigger (`SegmentTrigger`), and the expensive text decode runs
**only when the semantic content changes**. The product is a web service that lets a
person point a video file — or their live webcam — at this pipeline and watch captions
stream out, with the efficiency (decodes / windows) made visible.

**Primary users.**
- *Researcher/demo operator* (the thesis author): runs evaluations, records demos.
- *Committee / visitors*: open a URL, pick a sample or their webcam, see it work.
- *Downstream integrator* (future): calls the API from another system (assistive
  narration, video indexing, monitoring).

**Main goals.**
1. Make the research pipeline usable end-to-end from a browser with zero setup.
2. Be honest about performance: ~11 s/window on the T1000 → *progressive* UX, not
   real-time promises.
3. Protect the single GPU (one job at a time) and the host (upload validation, optional
   token).
4. Stay small enough that one person can maintain it, with a documented path to scale.

**Assumptions (stated).**
- One deployment target: the institute Windows 11 machine with an NVIDIA T1000 8 GB
  (possibly a T4 later). No cloud budget.
- Handful of concurrent viewers, exactly one GPU job at a time.
- No user accounts, no billing, no PII beyond the video content itself.
- Videos are short (demo-length); uploads capped at 500 MB.

---

## 2. Functional requirements

**Core (all [built]):**
- Serve a single-page UI at `/`.
- List server-side sample videos; upload a user video (validated type/size).
- Stream captions over WebSocket for a chosen video in **adaptive** or **uniform**
  mode, with per-window progress events (`n_steps`, `n_dec`, `caption`, `time`).
- Live webcam mode: browser captures frames (`getUserMedia`), streams JPEGs to the
  backend, receives captions; latest-frame buffer (no unbounded backlog); flush of the
  final open segment on stop.
- Health/readiness (`/health`) and runtime info (`/config`).
- Reject a second concurrent GPU job with a clear "busy" signal.

**Optional / advanced:**
- [built] Tunable parameters per run: uniform Hz, τ override, max windows.
- [built] Optional shared-secret token gating upload + WebSockets.
- [path] Job history + saved caption tracks (needs the SQLite layer, §8).
- [path] Multi-model selection (e.g. a pretrained-VLM captioner variant — explicitly
  deferred by the project owner).
- [path] RTSP/IP-camera ingestion for monitoring use cases.

**Roles.** Deliberately two implicit roles, no account system:
- *Viewer/operator* — everything the UI exposes; optionally gated by `LIVEJEPA_TOKEN`.
- *Admin* — whoever has shell access to the host: starts/stops via `start_server.ps1`,
  reads `webapp/server.log`, manages `webapp/uploads/`. An in-app admin panel is not
  justified at this scale; the trigger to add one is multi-tenant use.

---

## 3. Non-functional requirements

- **Performance:** first UI paint < 1 s (single HTML file, no CDN); model load ≤ ~2 min
  once at startup (background thread; UI serves immediately); inference throughput is
  hardware-bound: ~11 s/window (T1000), one window ≈ 8 s of video at 2 fps sampling
  with K=16 frames. Latency target for *caption events* is therefore "as computed",
  surfaced progressively — this is a stated product property, not a defect.
- **Scalability:** current target = 1 GPU job + ~10 idle viewers. Scale path in §10.
- **Availability:** best-effort single node. Crash → auto-restart loop in
  `start_server.ps1` (≤10 restarts, 5 s backoff). No SLA; acceptable for a research
  demo. Trigger for HA: any external consumer.
- **Security/privacy:** localhost by default; LAN/tunnel exposure is opt-in; token
  auth when tunneled; uploaded videos stay on the host disk and are never sent to
  third parties (all models run locally). No PII processing beyond video frames.
- **Maintainability:** one backend file, one frontend file, zero build step, pinned
  `requirements.txt`; 9 unit tests (`pytest tests/`) plus scripted E2E WS harnesses.
- **Observability:** structured log lines for job start/end (video, mode, windows,
  decodes, wall time), uploads, and exceptions → `webapp/server.log`.

---

## 4. User journeys and UX flows

**First-time viewer (video path).** Open URL → header explains the idea in two lines →
sample dropdown is pre-populated → press Start → status "connected — processing…" →
windows counter ticks up every ~11 s → red flash + caption appears when the trigger
fires → "done — N captions over M windows (X% decode rate)".

**Webcam flow.** Toggle *webcam* → browser permission prompt → live preview appears →
frames stream at ~2 fps → captions arrive when the pipeline frees up and the trigger
fires → press Stop → final open segment is flushed as a last caption.

**Error flows [built]:** camera denied → inline message; GPU busy → "⏳ GPU busy — one
job runs at a time"; server restart mid-job → "connection lost — press Start to retry";
bad upload → "upload failed: unsupported file type …"; invalid token → explicit error.

**Empty/loading states [built]:** "(waiting to start…)" caption box; `/health`-backed
"loading models…" status on first job; sample list silently empty if no videos.

**Responsive/mobile [built]:** CSS grid collapses to one column below 820 px; controls
are full-width touch targets; works on a phone over the tunnel (phone camera included,
since the tunnel is HTTPS).

**Accessibility:** semantic HTML, high-contrast dark palette, no color-only signals
(the decode flash is paired with the caption text and counters). Gap (accepted): no
ARIA live-region on the caption box yet — one attribute (`aria-live="polite"`) when
polishing.

---

## 5. Frontend architecture

**Choice: vanilla HTML/CSS/JS single file (`webapp/static/index.html`), no framework.**
Why: the UI has one screen, ~10 interactive elements, and WebSocket-driven state that
maps cleanly to a handful of DOM updates. React/Vite would add a build step, node
toolchain on a Windows GPU box, and CSP/CDN concerns — for zero user-visible benefit
at this size. **Trigger to adopt React + Vite:** a second page (job history), a
component reused ≥3 times, or a second developer.

- **Organization within the file:** styles (design tokens as CSS variables) → markup
  (control panel / results panel / footer) → script in functional sections: state,
  mode/source toggles, data fetch (`/samples`, `/config`), `handleMsg` (single reducer
  for all WS events), `startVideo` / `startWebcam` (transport), `finish` (teardown).
- **State management:** module-level variables (`mode, src, ws, camStream, camTimer,
  running, done`) — a deliberate state machine: `idle → running → done|error|lost`.
  All server events funnel through `handleMsg`, so rendering is single-sourced.
- **Data fetching:** REST for one-shot data (`fetch` on load), WebSocket for the
  streaming session. No client cache needed — `/samples` and `/config` are trivially
  cheap and fetched once per page load.
- **Routing:** none (single view). Query string carries the only deep-link parameter:
  `?token=`.
- **Forms/validation:** file input validated server-side (type + size) and surfaced
  inline; numeric inputs have `min`/`step` constraints; the Start handler guards
  against double-clicks via the `running` flag and a disabled button.
- **Auth on the frontend:** token read from the URL once, attached as `X-Token` header
  on upload and as a `token` field in the first WS message. Nothing stored; the URL
  *is* the credential (appropriate for a shared-secret demo; see §11).
- **Error/retry/offline:** every failure path lands in the status line with a specific
  message; `done` flag distinguishes clean completion from connection loss; retry is
  explicit (press Start) rather than automatic — correct here because a retried GPU
  job is expensive and the user should decide.
- **Real-time UI:** counters + progress bar update on every window event; decode flash
  (600 ms) + prepend-to-log on each caption — the newest caption is always visible
  without scrolling.
- **Performance:** one HTML document (<15 kB), zero external requests (no CDN — also
  makes it work on an air-gapped LAN), JPEG frames downscaled to 224×168 q0.6 before
  upload (~8 kB/frame at 2 fps ≈ 16 kB/s upstream).
- **Frontend security:** no `innerHTML` with server strings except the caption log —
  captions are model-generated (not attacker-controlled) but switch to `textContent`
  composition is the hardening step if uploads from untrusted users are enabled;
  same-origin WS; HTTPS via tunnel gives wss:// automatically (`wsProto()`).

---

## 6. Backend architecture

**Choice: FastAPI + uvicorn, modular monolith in one process. [built]**
Why: native WebSocket support, async event loop for many idle connections around a
blocking GPU worker, pydantic-free simplicity at this size, and the Python ML stack
(torch, transformers, cv2) lives in-process — no serialization boundary around
115 MB checkpoints and 3 GB of model weights. Microservices are strictly worse with
one GPU: they add a network hop and solve a scaling problem that doesn't exist yet.

**Module map (all in `webapp/backend.py`, ~400 lines):**
- `Pipeline` — model lifecycle + inference. Loads V-JEPA 2, SONAR, predictor exactly
  once (`_load_lock`, double-checked); `stream()` generator yields one event per
  window; `_infer_lock` is the **GPU bulkhead**: one job at a time, acquired
  non-blocking so a second client gets an immediate `busy` instead of queueing.
- Transport — REST endpoints + two WS handlers. The blocking generator is advanced via
  `run_in_executor` so the event loop keeps serving health checks and other viewers
  while the GPU crunches.
- Storage — filesystem: `eval_data/coin_videos/` (samples, read-only),
  `webapp/uploads/` (uuid-prefixed uploads), `webapp/server.log`.
- Config — env vars read at import (`LIVEJEPA_CKPT`, `LIVEJEPA_UPLOAD_DIR`,
  `LIVEJEPA_MAX_UPLOAD_MB`, `LIVEJEPA_TOKEN`); YAML (`configs/default.yaml`) for
  model/trigger parameters shared with the research code — single source of truth.

**Request flow.** Browser → uvicorn (single process) → route handler → (`_token_ok`)
→ (`_infer_lock`) → `Pipeline.stream()` in a thread-pool worker → events awaited and
pushed over the socket. No gateway/LB on one box; the tunnel (cloudflared) terminates
TLS in front when exposed.

**Validation/sanitization [built]:** upload extension whitelist + chunked write with
hard size cap (413) + `os.path.basename` on every client-supplied name (`_resolve`
also basenames, killing path traversal); WS numeric params coerced with defaults;
frame decode failures return `None` and are skipped.

**Rate limiting/idempotency:** the `_infer_lock` *is* the rate limiter for the
expensive resource; uploads are bounded by size cap and disk. [path] per-IP request
limits (slowapi) when public. Uploads are idempotent-safe: every upload gets a fresh
uuid name; re-clicking Start is guarded client-side and server-side (busy).

**Background work:** model load runs in a daemon thread at startup (`_safe_load`),
errors surfaced via `/health` rather than crashing the server. No queue/cron needed
yet. [path] job queue = Redis + one worker per GPU (§10).

**API versioning:** none until there is an external consumer; then `/v1/` prefix with
the current contract frozen as v1.

---

## 7. API design

Hybrid REST (control plane) + WebSocket (data plane) — correct because caption events
are a server-push stream with progress, which polling REST or SSE (no upstream frames)
handle worse. All responses JSON. Auth: optional shared secret — `X-Token` header or
`?token=` on REST, `token` field in the first WS message (or query param).

| Endpoint | Contract |
|---|---|
| `GET /health` | `{status:"ok", model_loaded:bool, ckpt:str, error:str\|null}` — readiness probe |
| `GET /config` | `{ckpt, device, tau, default_hz, max_upload_mb, token_required}` |
| `GET /samples` | `{samples:[filename,…]}` |
| `POST /upload` (multipart `file`) | 200 `{video_id}` · 400 bad type · 401 token · 413 too large |
| `WS /ws` | client sends `{video, mode:"adaptive"\|"uniform", hz?, tau?, max_windows?, token?}` once; server streams `{status}` then `{n_steps, n_dec, caption:str\|null, time:float\|null}` per window, ends `{done:true, n_steps, n_dec}`. Errors: `{error}` / `{busy:true, error}` then close. |
| `WS /ws_cam` | client sends config `{mode, hz?, tau?, token?}` then `{frame:"data:image/jpeg;base64,…"}` at ~2 fps and finally `{stop:true}`; server streams the same window events; on stop, adaptive mode flushes the final segment as a last caption. |

Pagination/filtering/sorting: not applicable (sample list is tens of items). [path]
`GET /jobs?limit=&before=` cursor pagination once job history exists.

---

## 8. Database design

**Now [built]: no database — deliberately.** The system is stateless per session; the
filesystem is the source of truth (samples, uploads, logs, results JSONs produced by
the research scripts). Adding Postgres to a single-user demo is pure liability
(backup, migration, another process on the GPU box).

**v1 [path], trigger = "we want job history / saved caption tracks":** SQLite (WAL
mode), zero-ops, single file next to the app.

```sql
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,            -- uuid
  video TEXT NOT NULL,            -- sample name or upload id
  source TEXT CHECK(source IN ('sample','upload','webcam')),
  mode TEXT CHECK(mode IN ('adaptive','uniform')),
  params_json TEXT,               -- hz, tau, max_windows
  started_at TEXT, finished_at TEXT,
  n_windows INTEGER, n_decodes INTEGER,
  status TEXT CHECK(status IN ('running','done','error','cancelled'))
);
CREATE TABLE captions (
  job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
  t REAL NOT NULL,                -- seconds since job start
  text TEXT NOT NULL,
  PRIMARY KEY (job_id, t)
);
CREATE INDEX idx_jobs_started ON jobs(started_at DESC);
```

Transactions: one per job-finish (insert captions batch + update job row) — the only
multi-row write. Consistency: single writer (the app), WAL readers.

**Scale [path], trigger = multi-tenant/many nodes:** Postgres for metadata, S3-style
object storage for videos (uploads move off local disk), Redis for the job queue.
Retention: uploads auto-deleted after N days (a 10-line cron/scheduled task —
currently manual, documented in README); logs rotated by restart stamps. Migrations:
none needed for SQLite v1 beyond `CREATE IF NOT EXISTS`; adopt Alembic with Postgres.

---

## 9. System workflows

- **Startup:** uvicorn starts → UI served immediately → daemon thread loads V-JEPA 2 +
  SONAR + predictor (~1–2 min) → `/health.model_loaded` flips true. Load failure →
  server stays up, `/health.error` carries the repr, UI still explains itself.
- **Upload → caption (CRUD analog):** validate token → validate extension → stream
  chunks to disk under uuid name, abort + delete at cap → client opens `/ws` with the
  returned id → `_resolve` maps id → path (basename-only, uploads/samples dirs only) →
  busy-check → generator streams events → done event logs the job summary.
- **Webcam session:** config message → receiver task fills a `deque(maxlen=K)` (frames
  that arrive during an 11 s inference simply replace older ones — freshest context,
  no backlog) → main loop processes a window whenever the GPU is free → stop → adaptive
  flush emits the final segment.
- **Failure behavior:** client disconnect mid-job → `WebSocketDisconnect` caught, lock
  released in `finally` (no GPU leak); exception mid-inference → error event sent,
  logged with traceback, lock released; process crash → `start_server.ps1` restarts,
  clients see "connection lost — press Start to retry"; second job while busy →
  immediate `busy` event, no queue growth.
- **Notifications/email/payments:** not applicable.

---

## 10. Scalability and performance

**The bottleneck is singular and known:** V-JEPA 2 forward ≈ 11 s/window on the T1000.
Everything else (SONAR decode ~0.5 s, trigger math ~µs, WS transport ~ms) is noise.

- **Frontend delivery:** a single static file served by the same process — a CDN is
  irrelevant until there are thousands of viewers; if needed, `static/` goes behind
  Cloudflare as-is.
- **Vertical (10×): [first step]** swap T1000 → T4/RTX (≈3–4×), fp16/`torch.compile`
  on the encoder (≈1.5–2×), batch the 16-frame clip preprocessing. Gets near
  1 window/s ≈ real-time at 2 fps sampling.
- **Horizontal (100×):** split transport from compute — FastAPI node + Redis queue +
  N GPU workers each holding one pipeline copy; WS events relayed via Redis pub/sub.
  The `Pipeline`/transport separation in the current file is already along this seam.
- **1000×:** encoder behind Triton/TorchServe with dynamic batching across streams;
  serverless GPU (Modal/RunPod) for burst; uploads to object storage with presigned
  URLs; per-stream trigger state in Redis. Adaptive decoding itself is the *product's*
  scaling feature: it cuts decoder cost per stream by ~10–20× (5–10% decode rate).
- **Latency wins in order of cheapness:** GPU upgrade > fp16 > smaller K > frame-skip
  under load (already implicit in the latest-frame webcam buffer).

---

## 11. Security design

**Threat model by exposure tier (the deploy script makes tiers explicit):**
- *localhost:* trusted operator; token off; risk ≈ 0.
- *LAN:* institute network; enable token if untrusted peers share the LAN.
- *Tunnel (public URL):* unguessable subdomain ≠ security. **Token required** — the
  README instructs setting `LIVEJEPA_TOKEN` before tunneling.

- **AuthN/Z [built]:** single shared secret compared with `hmac.compare_digest`
  (timing-safe), enforced on the three state-touching surfaces (upload, `/ws`,
  `/ws_cam`); read-only endpoints (`/`, `/health`, `/config`, `/samples`) stay open —
  they leak nothing sensitive (`/config` is explicitly non-secret). No passwords
  stored anywhere. [path] real accounts → OIDC in front (Cloudflare Access does this
  without code changes).
- **Transport encryption:** TLS terminated by cloudflared on the tunnel; plain HTTP on
  localhost/LAN is an accepted, documented trade-off. At rest: local disk, no cloud.
- **Injection surface:** no SQL (no DB); no shell-outs with user input; path traversal
  neutralized by `os.path.basename` at both write (`upload`) and read (`_resolve`);
  uploads never executed, only read by cv2; SSRF impossible (server fetches no
  client-supplied URLs).
- **XSS/CSRF/CORS:** captions are model output, not user input (see §5 hardening note);
  no cookies/sessions → CSRF not applicable; CORS is permissive because auth is
  token-per-request, not ambient.
- **Uploads [built]:** extension whitelist, hard size cap enforced *during* streaming
  (a spoofed Content-Length can't blow the disk), uuid names (no overwrite/guessing),
  dedicated directory. Downloads: clients never fetch upload files directly — no
  download endpoint exists.
- **Abuse prevention:** GPU lock bounds compute abuse to one job; upload cap bounds
  disk; [path] slowapi per-IP limits + fail2ban on the tunnel if abused.
- **Secrets:** one optional env var; never logged; not in the repo. [path] .env file
  excluded by gitignore → OS keyring/vault only if secret count grows.
- **Privacy:** webcam frames are processed in memory and never written to disk;
  uploads stay local and are manually (→[path] automatically) purged.

---

## 12. Reliability and fault tolerance

- **Graceful degradation [built]:** model-load failure ⇒ UI + health still serve with
  the error surfaced; missing checkpoint ⇒ same; camera absent ⇒ inline message; GPU
  busy ⇒ instant honest refusal rather than silent queueing.
- **Timeouts/retries:** WS jobs are client-cancellable (disconnect frees the GPU in
  `finally`); the UI retries only on explicit user action (right choice for
  minutes-long GPU jobs — automatic retry would double-spend the GPU). `max_windows`
  bounds job length; [path] a server-side wall-clock cap per job is the one missing
  guard if untrusted users can start unbounded videos.
- **Bulkheads:** `_infer_lock` isolates the GPU; the asyncio loop is never blocked by
  inference (executor threads), so health checks and other viewers survive a long job.
- **Crash recovery [built]:** `start_server.ps1` restart loop (5 s backoff, capped at
  10 — a persistent crash loop stops and points at the log instead of flapping).
- **Third-party failure:** cloudflared dies → LAN/localhost still work (the tunnel is
  additive); HuggingFace down → only matters on first-ever model download (weights are
  cached locally afterwards).
- **Backup/DR:** the repo + `checkpoints_kaggle/predictor_20000.pt` + `configs/` fully
  reconstruct the service; the checkpoint also lives in the Kaggle run output (offsite
  copy). Uploads are expendable demo data. No DB → nothing else to back up.

---

## 13. Observability and operations

- **Logs [built]:** `livejepa.web` logger → console + `webapp/server.log` via the
  launcher (`Tee-Object`): job start/end with video, mode, windows, decodes, wall
  time; uploads with size; full tracebacks on failure; uvicorn access lines. Restart
  markers timestamped by the launcher.
- **Metrics:** at this scale the job-summary log lines *are* the metrics (grep-able:
  wall-time per window trend = GPU health; decode-rate = trigger health). [path]
  `prometheus-fastapi-instrumentator` + Grafana when there's a second consumer.
  SLI candidates: window processing time (alert > 20 s sustained), model_loaded
  uptime, WS error rate. SLO: none promised (research demo); informal target =
  "up during demo hours".
- **Detection:** `/health` is the single probe (readiness + last load error); a
  scheduled task curling it every 5 min and alerting on failure is the [path]
  one-liner if unattended operation is needed.
- **Admin tooling:** PowerShell scripts + log file + `webapp/uploads/` folder — an
  operator with RDP does everything; that matches reality (remote access to the
  institute box).
- **Deploy/rollback:** git pull + restart script; rollback = git checkout previous
  tag + restart (stateless app makes this trivial). Blue-green/canary: meaningless on
  one node; noted as the pattern to adopt with the 100× split (§10).

---

## 14. Testing strategy

- **Unit [built]:** `pytest tests/` — 9 tests over the selective core (trigger
  semantics, pooling, selection math). Run before every deploy; currently 9/9.
- **Integration/E2E [built as scripts]:** WS client harnesses (used throughout
  development and re-run at deploy): `/ws` on a sample video (uniform 0.2 Hz ⇒
  deterministic caption count), `/ws_cam` with synthetic JPEG frames (proved the
  full browser-shaped path: base64 → decode → window → caption "get up the bag"),
  upload → stream round-trip. These pin the API contract from the client's side —
  the de-facto contract tests.
- **Frontend testing:** manual matrix (Chrome/Edge; localhost/LAN/tunnel; video/
  webcam; busy/error paths) — a Playwright smoke test is the [path] automation once
  the UI grows beyond one screen.
- **Load testing:** N idle WS viewers + 1 job (the only meaningful load shape); the
  busy-path test doubles as the concurrency test. GPU saturation testing is
  pointless — the lock guarantees serialization by construction.
- **Regression:** the research results (`results_*.json`) + cached streams pin the
  *model* behavior; `scripts/tune_adaptive.py` self-validates against the WS2
  baseline. Model changes rerun those, not just unit tests.
- **Test data:** COIN val videos already in `eval_data/coin_videos/` (also the UI
  samples — one artifact, two uses); synthetic gradient JPEGs for the cam harness.
- **Security testing:** the E2E suite includes negative cases (bad extension 400,
  oversize 413, wrong token 401/WS-error, traversal name resolved safely).

---

## 15. DevOps and deployment

- **Hosting:** the institute Windows 11 + T1000 machine — the only host with the GPU
  and the 3 GB of local model weights. Cloud GPU is the explicit non-choice (cost,
  and the data/models are already here).
- **Topology [built]:** one uvicorn process (started by `start_server.ps1`, bound
  0.0.0.0:8000) serving static + API + WS; optional cloudflared sidecar
  (`start_tunnel.ps1`) for HTTPS/public access. Static assets, API, and "worker" are
  one process on purpose (§6).
- **Environments:** dev = same machine on 127.0.0.1 (default uvicorn command in the
  README); "prod" = the launcher on 0.0.0.0 (+ tunnel). With one physical GPU,
  dev/staging/prod separation is by port + config, not by machine — honest and
  sufficient.
- **Config:** env vars for deployment concerns (token, caps, paths), YAML for model
  science (shared with research scripts so the demo can't drift from the evaluated
  configuration).
- **CI/CD:** [path] GitHub Actions running `pytest` + a stub-mode API smoke test
  (`use_stubs: true` runs the whole transport without GPU) on push; deploy remains
  a manual `git pull` + restart on the GPU box (a self-hosted runner is not worth
  its security surface at an institute).
- **Containers:** documented non-choice — CUDA-in-Docker on Windows adds friction and
  the target is a single known machine. The `requirements.txt` + README *is* the
  environment spec. Revisit with Linux GPU workers at the 100× split.

---

## 16. Edge cases and special scenarios

Handled [built]:
- **Double Start / repeated clicks:** `running` flag + disabled button client-side;
  `_infer_lock` server-side — the invariant holds even against a hostile client.
- **Two browsers, one GPU:** second gets `busy:true` immediately; first is unaffected.
- **Disconnect mid-job:** lock released in `finally`; generator abandoned; no leak.
- **Server restart mid-job:** UI shows "connection lost — press Start to retry".
- **Upload lies about size:** cap enforced on actual bytes written, partial file
  deleted.
- **Weird filenames (`../../x.mp4`, unicode):** basenamed + uuid-prefixed at write;
  basenamed again at resolve.
- **Corrupted/truncated video:** cv2 yields no frames → 0 windows → clean `done`
  event with zeros (empty-state, not a crash). Corrupted webcam JPEG → decode returns
  None → frame skipped.
- **Video shorter than one window (< 16 frames at 2 fps):** zero windows, clean done —
  the UI's decode-rate line makes "nothing processed" visible.
- **Webcam frames faster than GPU:** `deque(maxlen=K)` keeps freshest context,
  backlog impossible.
- **Adaptive fires rarely on a static scene:** correct behavior (that's the thesis);
  stop-flush guarantees at least the final segment is captioned; the UI hint manages
  expectation.
- **Token appears in URLs:** accepted for a demo secret (rotate by restarting with a
  new value); noted as the first thing to replace with Cloudflare Access if persistent.

Accepted-risk gaps (documented, triggers named): no per-job wall-clock cap; no upload
auto-purge; no per-IP rate limit — all become mandatory the day untrusted strangers
get the URL, all are ≤20-line changes.

---

## 17. Trade-offs and alternatives

| Decision | Alternative considered | Why the choice wins here |
|---|---|---|
| Vanilla JS single file | React + Vite | zero build step on a GPU box; one screen; trigger for React documented (§5) |
| FastAPI modular monolith | Flask+SSE / Node+Python split / microservices | native WS + async around a blocking GPU; one GPU makes distribution pure overhead |
| No database | SQLite from day 1 | nothing to persist yet; schema designed and ready (§8) so adding it is hours, not a redesign |
| Lock + instant "busy" | job queue | honest UX for minutes-long jobs; a silent queue on an 11 s/window GPU is a worse product |
| Shared-secret token | OIDC/JWT accounts | matches the actual user population (a handful of known people); Cloudflare Access is the no-code upgrade |
| cloudflared quick tunnel | port-forward / ngrok / self-managed TLS | free, no account, no firewall changes at an institute, HTTPS unlocks getUserMedia |
| Windows-native scripts | Docker | CUDA-on-Windows-Docker friction for a single known host; env spec lives in requirements.txt |

**If priorities shifted:** *speed of iteration* → keep exactly this; *scale* → do the
§10 100× split first (transport/compute seam already in the code); *cost* → nothing
to cut (it's one machine); *product polish* → React UI + SQLite history + Playwright.

---

## 18. Final summary

- **Frontend:** self-contained vanilla-JS SPA — source toggle (file/webcam), two
  selection modes, WebSocket-driven progressive captioning UI with busy/lost/error
  states, token passthrough, `/config` footer; responsive, CDN-free.
- **Backend:** FastAPI modular monolith; `Pipeline` (load-once models, generator
  streaming, GPU bulkhead lock) + REST control plane + two WS data planes; env-var
  deployment config; validated chunked uploads; timing-safe optional token; structured
  job logging.
- **Data/infra:** filesystem-as-database (SQLite schema ready when history is wanted);
  single Windows/T1000 host; PowerShell launcher with crash-restart + log; cloudflared
  HTTPS tunnel for public/webcam access.
- **Top risks & mitigations:** GPU slowness → progressive UX now, T4/fp16 next;
  public tunnel exposure → token + read-only defaults + upload caps; single-node crash
  → restart loop + stateless design; model-load failure → degraded-but-honest serving
  via /health.
- **Roadmap:**
  - **MVP [shipped]:** everything in §2 core — verified E2E.
  - **v1:** SQLite job history + saved caption tracks; upload auto-purge; per-job
    wall-clock cap; `aria-live`; Playwright smoke; GitHub Actions stub-mode CI.
  - **Scale-up:** T4/fp16/compile; Redis queue + GPU worker split; Prometheus/Grafana;
    object storage for uploads; `/v1` API freeze.
  - **Enterprise:** OIDC (Cloudflare Access), multi-GPU worker pool behind Triton with
    dynamic batching, per-tenant isolation + quotas, audit logging, RTSP ingestion.
