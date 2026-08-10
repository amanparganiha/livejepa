"""LiveJEPA web backend — FastAPI.

Loads the pipeline once (frozen V-JEPA 2 -> trained predictor -> SONAR) and streams
captions over a WebSocket as they are computed. Because V-JEPA 2 is ~11 s/window on
a T1000 (not real-time), the design is *progressive*: the UI shows the decodes/steps
counter advancing every window and a caption appears the moment the selective trigger
(adaptive) or the fixed interval (uniform) fires.

Run:
    python -m uvicorn webapp.backend:app --host 127.0.0.1 --port 8000
    # then open http://127.0.0.1:8000

Endpoints:
    GET  /            -> the single-page UI
    GET  /health      -> {status, model_loaded}
    GET  /config      -> non-secret runtime info (ckpt, device, defaults)
    GET  /samples     -> list of server-side sample videos (eval_data/coin_videos)
    POST /upload      -> save an uploaded video, returns {video_id}
    WS   /ws          -> stream caption events for a chosen video + mode
    WS   /ws_cam      -> live webcam: browser sends JPEG frames, receives captions

Deployment env vars (all optional):
    LIVEJEPA_CKPT           predictor checkpoint path
    LIVEJEPA_UPLOAD_DIR     where uploads are stored
    LIVEJEPA_MAX_UPLOAD_MB  upload size cap (default 500)
    LIVEJEPA_TOKEN          shared secret; if set, /upload and both WS require it
"""
from __future__ import annotations
import os
import time
import uuid
import glob
import logging
import numpy as np
import yaml
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from livejepa.demo import frame_source
from livejepa.selective.online import SegmentTrigger
from livejepa.selective.pooling import moving_average

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.environ.get("LIVEJEPA_UPLOAD_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "uploads")
SAMPLE_DIR = os.path.join(ROOT, "eval_data", "coin_videos")
DEFAULT_CKPT = os.environ.get("LIVEJEPA_CKPT") or os.path.join(
    ROOT, "checkpoints_kaggle", "predictor_20000.pt")
MAX_UPLOAD_MB = int(os.environ.get("LIVEJEPA_MAX_UPLOAD_MB", "500"))
TOKEN = os.environ.get("LIVEJEPA_TOKEN", "")  # empty -> auth disabled (localhost use)
ALLOWED_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
os.makedirs(UPLOAD_DIR, exist_ok=True)

log = logging.getLogger("livejepa.web")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log.setLevel(logging.INFO)


def _token_ok(supplied) -> bool:
    import hmac
    return not TOKEN or hmac.compare_digest(str(supplied or ""), TOKEN)




class Pipeline:
    """Holds the heavy models (loaded once) and streams caption events for a video."""

    def __init__(self, config_path=None, ckpt=None):
        import threading
        cfg_path = config_path or os.path.join(ROOT, "configs", "default.yaml")
        self.cfg = yaml.safe_load(open(cfg_path))
        self.cfg["project"]["use_stubs"] = False
        self.ckpt = ckpt or (DEFAULT_CKPT if os.path.exists(DEFAULT_CKPT) else None)
        self._loaded = False
        self._load_lock = threading.Lock()   # prevent double-load (startup vs WS)
        self._infer_lock = threading.Lock()  # single GPU -> one inference at a time

    def load(self):
        if self._loaded:
            return
        with self._load_lock:
            if self._loaded:                  # re-check inside the lock
                return
            from livejepa.encoders.vision import VisionEncoder
            from livejepa.encoders.sonar import SonarSpace
            from livejepa.predictor.infer import load_predictor
            self.vision = VisionEncoder(self.cfg)
            self.sonar = SonarSpace(self.cfg)
            self.predict = load_predictor(self.cfg, self.ckpt)
            self._loaded = True

    def stream(self, video_path, mode="adaptive", hz=0.2, tau=None, max_windows=0):
        """Generator: yields one event dict per processed window.

        event = {n_steps, n_dec, caption (str|None), time (float|None), done?}
        """
        self.load()
        cfg, sc = self.cfg, self.cfg["selective"]
        K = cfg["encoders"]["vision"]["frames_per_window"]
        fps = cfg["demo"]["display_fps"]
        smooth = max(1, sc["smoothing_window"])
        tau = tau if tau is not None else sc["tau"]
        trig = SegmentTrigger(sc["window"], tau, sc["min_gap"])
        uni_stride = max(1, round(fps / max(1e-6, hz)))

        buf, recent = [], []
        n_dec = n_steps = 0
        t0 = time.time()

        def decode(e):
            return self.sonar.decode(e)[0]

        for frame in frame_source(video_path, target_fps=fps):
            buf.append(frame)
            if len(buf) > K:
                buf.pop(0)
            if len(buf) < K:
                continue
            emb = self.predict(self.vision.encode_window(buf))
            recent.append(emb)
            if len(recent) > smooth:
                recent.pop(0)
            if smooth > 1:
                emb = moving_average(np.stack(recent), smooth)[-1]
            n_steps += 1
            # always run the detector so the UI's semantic-shift meter shows the
            # exact quantity compared against tau (even in uniform mode)
            out = trig.step(emb)
            delta = None if trig.last_shift is None else round(trig.last_shift, 4)

            cap = ts = None
            if mode == "adaptive":
                if out is not None:
                    cap, ts, n_dec = decode(out[1]), time.time() - t0, n_dec + 1
            elif (n_steps - 1) % uni_stride == 0:
                cap, ts, n_dec = decode(emb), time.time() - t0, n_dec + 1

            yield {"n_steps": n_steps, "n_dec": n_dec, "caption": cap, "time": ts,
                   "delta": delta}
            if max_windows and n_steps >= max_windows:
                break

        if mode == "adaptive":
            out = trig.flush()
            if out is not None:
                n_dec += 1
                yield {"n_steps": n_steps, "n_dec": n_dec,
                       "caption": decode(out[1]), "time": time.time() - t0}
        yield {"done": True, "n_steps": n_steps, "n_dec": n_dec}


PIPE = Pipeline()
app = FastAPI(title="LiveJEPA")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # UI is same-origin; permissive CORS keeps tunnels simple
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    # kick off model loading in the background so the first request is fast; if it
    # fails (e.g. missing ckpt) we still serve the UI and report via /health.
    import threading
    threading.Thread(target=_safe_load, daemon=True).start()


def _safe_load():
    try:
        PIPE.load()
    except Exception as e:  # surfaced by /health
        PIPE._load_error = repr(e)


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": PIPE._loaded,
            "ckpt": PIPE.ckpt, "error": getattr(PIPE, "_load_error", None)}


@app.get("/config")
def config():
    """Non-secret runtime info for the UI footer."""
    import torch
    sc = PIPE.cfg["selective"]
    return {
        "ckpt": os.path.basename(PIPE.ckpt) if PIPE.ckpt else None,
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "tau": sc["tau"],
        "default_hz": 0.2,
        "max_upload_mb": MAX_UPLOAD_MB,
        "token_required": bool(TOKEN),
    }


@app.get("/samples")
def samples():
    vids = sorted(os.path.basename(p) for p in glob.glob(os.path.join(SAMPLE_DIR, "*.mp4")))
    return {"samples": vids}


THUMB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thumbs")
os.makedirs(THUMB_DIR, exist_ok=True)


@app.get("/thumb/{name}")
def thumb(name: str):
    """First-second frame of a sample/upload as a small JPEG (cached on disk)."""
    import cv2
    from fastapi.responses import FileResponse
    name = os.path.basename(name)
    src = _resolve(name)
    if not src:
        return JSONResponse({"error": "not found"}, status_code=404)
    out = os.path.join(THUMB_DIR, name + ".jpg")
    if not os.path.exists(out):
        cap = cv2.VideoCapture(src)
        fr = None
        for _ in range(30):                      # ~1 s in: skip fade-in black frames
            ok, f = cap.read()
            if not ok:
                break
            fr = f
        cap.release()
        if fr is None:
            return JSONResponse({"error": "unreadable video"}, status_code=422)
        h, w = fr.shape[:2]
        scale = 320.0 / max(1, w)
        fr = cv2.resize(fr, (320, max(1, int(h * scale))))
        cv2.imwrite(out, fr, [cv2.IMWRITE_JPEG_QUALITY, 78])
    return FileResponse(out, media_type="image/jpeg")


@app.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    if not _token_ok(request.headers.get("x-token") or request.query_params.get("token")):
        return JSONResponse({"error": "invalid token"}, status_code=401)
    name = os.path.basename(file.filename or "")
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXT:
        return JSONResponse(
            {"error": f"unsupported file type {ext or '(none)'} — "
                      f"allowed: {', '.join(sorted(ALLOWED_EXT))}"}, status_code=400)
    vid = f"{uuid.uuid4().hex}_{name}"
    dest = os.path.join(UPLOAD_DIR, vid)
    limit = MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > limit:
                f.close()
                os.remove(dest)
                return JSONResponse(
                    {"error": f"file exceeds {MAX_UPLOAD_MB} MB limit"}, status_code=413)
            f.write(chunk)
    log.info("upload: %s (%.1f MB)", vid, written / 1e6)
    return {"video_id": vid}


def _resolve(video_ref):
    """Map a client-supplied reference to an on-disk path (sample or upload)."""
    for base in (SAMPLE_DIR, UPLOAD_DIR):
        p = os.path.join(base, os.path.basename(video_ref))
        if os.path.exists(p):
            return p
    return None


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    import asyncio
    await websocket.accept()
    try:
        req = await websocket.receive_json()
        if not _token_ok(req.get("token") or websocket.query_params.get("token")):
            await websocket.send_json({"error": "invalid token"})
            await websocket.close()
            return
        path = _resolve(req.get("video", ""))
        if not path:
            await websocket.send_json({"error": f"video not found: {req.get('video')}"})
            await websocket.close()
            return
        mode = req.get("mode", "adaptive")
        hz = float(req.get("hz", 0.2))
        tau = req.get("tau")
        tau = float(tau) if tau not in (None, "") else None
        maxw = int(req.get("max_windows", 0) or 0)

        if not PIPE._infer_lock.acquire(blocking=False):   # single GPU: one job at a time
            await websocket.send_json({"busy": True,
                                       "error": "server busy with another job — try again shortly"})
            await websocket.close()
            return
        try:
            log.info("ws job start: video=%s mode=%s hz=%s tau=%s",
                     os.path.basename(path), mode, hz, tau)
            job_t0 = time.time()
            await websocket.send_json({"status": "loading models..." if not PIPE._loaded else "running",
                                       "mode": mode})
            gen = PIPE.stream(path, mode=mode, hz=hz, tau=tau, max_windows=maxw)
            loop = asyncio.get_event_loop()
            SENTINEL = object()
            while True:                               # advance the heavy generator off-loop
                ev = await loop.run_in_executor(None, next, gen, SENTINEL)
                if ev is SENTINEL:
                    break
                await websocket.send_json(ev)
                if ev.get("done"):
                    log.info("ws job done: video=%s windows=%s decodes=%s wall=%.1fs",
                             os.path.basename(path), ev.get("n_steps"),
                             ev.get("n_dec"), time.time() - job_t0)
                    break
        finally:
            PIPE._infer_lock.release()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.exception("ws job failed")
        try:
            await websocket.send_json({"error": repr(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


def _decode_frame(data_url):
    """Decode a browser 'data:image/jpeg;base64,...' frame to an RGB numpy array."""
    import base64, cv2
    b64 = data_url.split(",", 1)[-1]
    buf = np.frombuffer(base64.b64decode(b64), dtype=np.uint8)
    bgr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if bgr is None:
        return None
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


@app.websocket("/ws_cam")
async def ws_cam(websocket: WebSocket):
    """Live webcam: the browser streams JPEG frames; we keep the most recent K,
    process a window whenever the (slow) pipeline is free, and stream captions back.

    Because V-JEPA 2 is ~11 s/window on a T1000, frames that arrive while a window
    is being processed simply update the buffer (older ones drop) — we caption the
    most recent context when free, rather than queueing an ever-growing backlog."""
    import asyncio
    from collections import deque
    await websocket.accept()
    if not PIPE._infer_lock.acquire(blocking=False):
        await websocket.send_json({"busy": True,
                                   "error": "server busy with another job — try again shortly"})
        await websocket.close()
        return
    try:
        req = await websocket.receive_json()               # first msg = config
        if not _token_ok(req.get("token") or websocket.query_params.get("token")):
            await websocket.send_json({"error": "invalid token"})
            await websocket.close()
            return
        log.info("ws_cam session start: mode=%s", req.get("mode", "adaptive"))
        cam_t0 = time.time()
        mode = req.get("mode", "adaptive")
        tau = req.get("tau"); tau = float(tau) if tau not in (None, "") else None
        hz = float(req.get("hz", 0.2))
        PIPE.load()
        cfg, sc = PIPE.cfg, PIPE.cfg["selective"]
        K = cfg["encoders"]["vision"]["frames_per_window"]

        def _opt_int(key, default, lo, hi):
            """Optional per-session trigger override, clamped; falsy/bad -> default.

            Live demos on a slow GPU need a SHORTER detector window. SegmentTrigger
            clears its buffer after every fire (selective/online.py:114) and must
            re-fill before it can fire again, so `window` — not `min_gap` — sets
            both the warm-up and the floor between captions, each ≈ window ×
            seconds-per-window. On an 11 s/window T1000 the default window=8 means
            ~88 s of silence; window=3 brings that to ~33 s. Config defaults are
            unchanged, so measurement runs are unaffected."""
            v = req.get(key)
            try:
                return max(lo, min(hi, int(v))) if v not in (None, "") else default
            except (TypeError, ValueError):
                return default

        win = _opt_int("window", sc["window"], 2, 32)
        min_gap = _opt_int("min_gap", sc["min_gap"], 0, 32)
        smooth = _opt_int("smooth", max(1, sc["smoothing_window"]), 1, 9)
        tau = tau if tau is not None else sc["tau"]
        trig = SegmentTrigger(win, tau, min_gap)
        uni_stride = max(1, round(cfg["demo"]["display_fps"] / max(1e-6, hz)))
        log.info("ws_cam trigger: window=%d tau=%.3f min_gap=%d smooth=%d",
                 win, tau, min_gap, smooth)

        latest = deque(maxlen=K)
        recent = []
        n_dec = n_steps = 0
        t0 = time.time()
        state = {"stop": False}

        async def receiver():
            try:
                while not state["stop"]:
                    msg = await websocket.receive_json()
                    if msg.get("stop"):
                        state["stop"] = True; return
                    fr = msg.get("frame")
                    if fr:
                        img = _decode_frame(fr)
                        if img is not None:
                            latest.append(img)
            except Exception:
                state["stop"] = True

        recv_task = asyncio.create_task(receiver())
        loop = asyncio.get_event_loop()
        await websocket.send_json({"status": "webcam running — captions on semantic change"})

        def process_window():
            nonlocal n_dec, n_steps, recent
            window = list(latest)
            if len(window) < K:
                return None
            emb = PIPE.predict(PIPE.vision.encode_window(window[-K:]))
            recent.append(emb)
            if len(recent) > smooth:
                recent.pop(0)
            if smooth > 1:
                emb = moving_average(np.stack(recent), smooth)[-1]
            n_steps += 1
            out = trig.step(emb)
            delta = None if trig.last_shift is None else round(trig.last_shift, 4)
            cap = ts = None
            if mode == "adaptive":
                if out is not None:
                    cap, ts, n_dec = PIPE.sonar.decode(out[1])[0], time.time() - t0, n_dec + 1
            elif (n_steps - 1) % uni_stride == 0:
                cap, ts, n_dec = PIPE.sonar.decode(emb)[0], time.time() - t0, n_dec + 1
            return {"n_steps": n_steps, "n_dec": n_dec, "caption": cap, "time": ts,
                    "delta": delta}

        while not state["stop"]:
            if len(latest) < K:
                await asyncio.sleep(0.1)
                continue
            ev = await loop.run_in_executor(None, process_window)
            if ev is not None:
                await websocket.send_json(ev)
        if mode == "adaptive":                         # emit the final open segment
            out = trig.flush()
            if out is not None:
                n_dec += 1
                cap = await loop.run_in_executor(None, lambda: PIPE.sonar.decode(out[1])[0])
                await websocket.send_json({"n_steps": n_steps, "n_dec": n_dec,
                                           "caption": cap, "time": time.time() - t0})
        recv_task.cancel()
        log.info("ws_cam session done: windows=%d decodes=%d wall=%.1fs",
                 n_steps, n_dec, time.time() - cam_t0)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.exception("ws_cam session failed")
        try:
            await websocket.send_json({"error": repr(e)})
        except Exception:
            pass
    finally:
        PIPE._infer_lock.release()
        try:
            await websocket.close()
        except Exception:
            pass


@app.get("/", response_class=HTMLResponse)
def index():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
    if os.path.exists(html_path):
        return HTMLResponse(open(html_path, encoding="utf-8").read())
    return HTMLResponse("<h1>LiveJEPA</h1><p>UI not found.</p>")


@app.get("/about", response_class=HTMLResponse)
def about():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "about.html")
    if os.path.exists(html_path):
        return HTMLResponse(open(html_path, encoding="utf-8").read())
    return HTMLResponse("<h1>LiveJEPA</h1><p>About page not found.</p>")
