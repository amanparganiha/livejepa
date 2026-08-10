# LiveJEPA — Web UI + Backend

A browser-testable front end for the LiveJEPA pipeline. Pick a sample video, upload
your own, or use your **laptop webcam** (captured by the browser), choose
**adaptive** (decode on semantic change) or **uniform** (fixed interval), and watch
captions stream in live with a decode-flash indicator and a decodes/steps efficiency
counter.

## Run (development)

```bash
pip install -r requirements.txt          # includes fastapi, uvicorn, python-multipart
python -m uvicorn webapp.backend:app --host 127.0.0.1 --port 8000
# then open http://127.0.0.1:8000 in a browser
```

The predictor checkpoint defaults to `checkpoints_kaggle/predictor_20000.pt`. Models
(V-JEPA 2 + SONAR) load once at startup — `GET /health` reports `model_loaded` and
any load error.

## Deploy

Three tiers, from safest to most reachable:

### 1. Local (same machine)

```powershell
powershell -ExecutionPolicy Bypass -File webapp\start_server.ps1 -BindHost 127.0.0.1
```

Open http://localhost:8000. Webcam works (localhost is a secure origin).

### 2. LAN (other machines on the institute network)

```powershell
powershell -ExecutionPolicy Bypass -File webapp\start_server.ps1     # binds 0.0.0.0
```

Open `http://<server-ip>:8000` from any machine on the network
(`ipconfig` shows the server IP; allow TCP 8000 in Windows Firewall if prompted).
Video/upload works from anywhere; **webcam will NOT work over plain LAN HTTP**
(browsers require localhost or HTTPS for camera access) — use the tunnel for that.

### 3. HTTPS tunnel (laptop webcam → this GPU server)

```powershell
# terminal 1 — the server (with an access token, since the URL is public):
$env:LIVEJEPA_TOKEN = "pick-a-secret"
powershell -ExecutionPolicy Bypass -File webapp\start_server.ps1

# terminal 2 — the tunnel:
powershell -ExecutionPolicy Bypass -File webapp\start_tunnel.ps1
```

Copy the printed `https://xxxx.trycloudflare.com` URL and open
`https://xxxx.trycloudflare.com/?token=pick-a-secret` on your laptop. Because the
origin is HTTPS, the browser allows the camera → select **webcam** → Start.
The URL changes each time the tunnel restarts.

### Config (env vars, all optional)

| Variable | Default | Purpose |
|---|---|---|
| `LIVEJEPA_CKPT` | `checkpoints_kaggle/predictor_20000.pt` | predictor checkpoint |
| `LIVEJEPA_UPLOAD_DIR` | `webapp/uploads` | where uploads are stored |
| `LIVEJEPA_MAX_UPLOAD_MB` | `500` | upload size cap (413 beyond it) |
| `LIVEJEPA_TOKEN` | *(empty = auth off)* | shared secret required on `/upload` + both WebSockets |

`start_server.ps1` logs to `webapp/server.log` and auto-restarts on crash.

### Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `/health` shows `model_loaded: false` for minutes | first load downloads/loads V-JEPA 2 + SONAR — wait; check `error` field |
| "server busy with another job" | single GPU, one job at a time — wait for the running job |
| webcam button does nothing / camera blocked | origin is not localhost/HTTPS — use the tunnel (tier 3) |
| upload rejected 400/413 | extension not in mp4/avi/mov/mkv/webm, or over the size cap |
| "invalid token" | append `?token=<secret>` to the page URL so the UI passes it through |
| captions very slow | expected: ~11 s per window on a T1000 (a T4 would be ~3–4× faster) |

## Notes

- **Not real-time on a T1000** (~11 s/window). The UI is *progressive*: the
  decodes/steps counter advances every window and captions appear as the trigger
  fires. Keep "max windows" small (e.g. 40 ≈ 20 s of video) for a quick run.
- **Webcam** is captured by the *browser* (`getUserMedia`) and streamed to the
  backend — so it works from any laptop even though the server machine has no camera.
  Requires `http://localhost` or HTTPS (browsers block camera on plain remote HTTP).
- Single GPU → one job at a time (the backend refuses a second concurrent job with a
  "server busy" message).

## Endpoints

| Route | Purpose |
|---|---|
| `GET /` | the single-page UI |
| `GET /health` | `{status, model_loaded, ckpt, error}` |
| `GET /config` | non-secret runtime info (ckpt name, device, τ, upload limit) |
| `GET /samples` | list server-side sample videos (`eval_data/coin_videos`) |
| `POST /upload` | save an uploaded video → `{video_id}` (validated: type + size) |
| `WS /ws` | stream captions for a chosen sample/uploaded video |
| `WS /ws_cam` | stream captions from browser-pushed webcam frames |

## Files

- `backend.py` — FastAPI app + the `Pipeline` wrapper (loads models once, streams events).
- `static/index.html` — the self-contained UI (no external CDNs).
- `start_server.ps1` — deployment launcher (0.0.0.0, logging, crash restart).
- `start_tunnel.ps1` — cloudflared HTTPS tunnel (enables remote webcam).

See `docs/SYSTEM_DESIGN.md` for the full production system design (architecture,
API contracts, scaling path, security model, roadmap).
