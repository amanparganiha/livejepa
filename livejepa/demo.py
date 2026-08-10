"""Live demo — event-driven streaming captioning.

Reads a webcam / video file, runs frozen V-JEPA 2 over sliding windows, predicts
SONAR embeddings, and decodes a caption ONLY when the streaming segment trigger
fires (the corrected `SegmentTrigger` from the online path — emits the pooled
segment at its close, one-window latency).

With a display it overlays the live caption, flashes a red "DECODE" indicator when
the expensive decode actually runs, and shows a decodes/steps counter — the
efficiency argument made visible. `--no-display` runs headless (print-only).

Usage:
    python -m livejepa.demo --config configs/default.yaml --source 0
    python -m livejepa.demo --source path/to/video.mp4 --ckpt checkpoints/predictor_XXXX.pt
    python -m livejepa.demo --source path/to/video.mp4 --no-display   # headless
    # save an annotated MP4 deliverable (headless), compare selection modes:
    python -m livejepa.demo --source vid.mp4 --ckpt ckpt.pt --no-display \
        --save-video out_adaptive.mp4 --mode adaptive
    python -m livejepa.demo --source vid.mp4 --ckpt ckpt.pt --no-display \
        --save-video out_uniform.mp4  --mode uniform --hz 0.2

--mode adaptive decodes only on semantic change (SegmentTrigger); --mode uniform
decodes at a fixed --hz interval (the baseline). Works in stub mode too.
"""
from __future__ import annotations
import argparse
import time
import yaml
import numpy as np

from livejepa.encoders.vision import VisionEncoder
from livejepa.encoders.sonar import SonarSpace
from livejepa.predictor.infer import load_predictor
from livejepa.selective.online import SegmentTrigger
from livejepa.selective.pooling import moving_average


def frame_source(source, target_fps=None):
    """Yield RGB frames from a webcam index or video path via OpenCV.

    Subsamples to `target_fps` (skipping native frames) so each processed window
    advances by ~1/target_fps of video, matching how run_eval/read_frames_at_fps
    builds streams and how the predictor was trained. Without this the window
    slides one native frame at a time (~25 fps) -> near-duplicate windows, the
    trigger barely fires, and it's ~native/target x slower than needed."""
    import cv2
    cap = cv2.VideoCapture(int(source) if str(source).isdigit() else source)
    if not cap.isOpened():
        raise SystemExit(f"Could not open source: {source}")
    native = cap.get(cv2.CAP_PROP_FPS) or 0.0
    stride = max(1, round(native / target_fps)) if (target_fps and native > 0) else 1
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % stride == 0:
            yield cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        i += 1
    cap.release()


def _draw_overlay(frame_rgb, caption, n_dec, n_steps, flash):
    """Return a BGR frame with caption / efficiency-counter / decode-flash overlays."""
    import cv2
    img = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR).copy()
    h, w = img.shape[:2]
    pct = 100.0 * n_dec / max(1, n_steps)
    cv2.rectangle(img, (0, 0), (w, 28), (0, 0, 0), -1)
    cv2.putText(img, f"decodes {n_dec} / steps {n_steps}  ({pct:.0f}% of steps)",
                (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    if flash > 0:                                          # "decode fired" indicator
        cv2.circle(img, (w - 18, 14), 8, (0, 0, 255), -1)
        cv2.putText(img, "DECODE", (w - 108, 19), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 0, 255), 2, cv2.LINE_AA)
    cv2.rectangle(img, (0, h - 40), (w, h), (0, 0, 0), -1)
    cv2.putText(img, caption[:80], (8, h - 14), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (0, 255, 0), 1, cv2.LINE_AA)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--source", default=None)
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--no-display", action="store_true", help="headless (print-only)")
    ap.add_argument("--max-frames", type=int, default=0,
                    help="stop after N processed windows (0 = run whole source; useful for quick tests)")
    ap.add_argument("--mode", default="adaptive", choices=["adaptive", "uniform"],
                    help="adaptive = decode on semantic change (SegmentTrigger); "
                         "uniform = decode at a fixed interval (baseline)")
    ap.add_argument("--hz", type=float, default=0.2,
                    help="uniform-mode decode rate (decodes/sec of stream)")
    ap.add_argument("--tau", type=float, default=None,
                    help="override adaptive shift threshold (lower = fires more often)")
    ap.add_argument("--save-video", default=None,
                    help="write an annotated MP4 (works headless; the Phase-4 deliverable)")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    source = args.source if args.source is not None else cfg["demo"]["source"]

    vision = VisionEncoder(cfg)
    sonar = SonarSpace(cfg)
    predict = load_predictor(cfg, args.ckpt)

    sc = cfg["selective"]
    K = cfg["encoders"]["vision"]["frames_per_window"]
    smooth = max(1, sc["smoothing_window"])
    fps = cfg["demo"]["display_fps"]

    tau = args.tau if args.tau is not None else sc["tau"]
    trig = SegmentTrigger(sc["window"], tau, sc["min_gap"])   # adaptive path
    uni_stride = max(1, round(fps / args.hz))                 # uniform path interval
    print(f"mode={args.mode}"
          + (f" (tau={tau})" if args.mode == "adaptive"
             else f" (every {uni_stride} steps ~= {args.hz} Hz)"))
    display = (not args.no_display) and cfg["demo"].get("show_decode_indicator", True)
    if display:
        try:
            import cv2  # noqa: F401
        except Exception as e:
            print("display unavailable, running headless:", e)
            display = False

    buf, recent_emb = [], []
    caption, n_dec, n_steps, flash = "(waiting for a stable segment...)", 0, 0, 0
    writer = None                                         # lazy cv2.VideoWriter for --save-video
    t0 = time.time()
    print("LiveJEPA demo running. Captions appear only on semantic change. (q to quit)\n")

    def emit(pooled):
        nonlocal caption, n_dec, flash
        caption = sonar.decode(pooled)[0]
        n_dec += 1
        flash = 5
        print(f"[{time.time() - t0:6.1f}s] {caption}")

    for frame in frame_source(source, target_fps=fps):
        buf.append(frame)                                 # bounded sliding window
        if len(buf) > K:
            buf.pop(0)
        if len(buf) < K:
            continue
        emb = predict(vision.encode_window(buf))
        recent_emb.append(emb)                            # bounded smoothing buffer
        if len(recent_emb) > smooth:
            recent_emb.pop(0)
        if smooth > 1:
            emb = moving_average(np.stack(recent_emb), smooth)[-1]
        n_steps += 1

        if args.mode == "adaptive":                       # decode on semantic change
            out = trig.step(emb)
            if out is not None:
                emit(out[1])
        elif (n_steps - 1) % uni_stride == 0:             # decode at fixed interval
            emit(emb)

        if display or args.save_video:                    # render the overlay once
            import cv2
            vis = _draw_overlay(frame, caption, n_dec, n_steps, flash)
            if args.save_video:
                if writer is None:
                    h, w = vis.shape[:2]
                    writer = cv2.VideoWriter(args.save_video,
                                             cv2.VideoWriter_fourcc(*"mp4v"),
                                             fps, (w, h))
                writer.write(vis)
            if display:
                cv2.imshow("LiveJEPA", vis)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break

        if args.max_frames and n_steps >= args.max_frames:
            break
        flash = max(0, flash - 1)
        time.sleep(max(0.0, 1.0 / fps - 0.001))

    if args.mode == "adaptive":
        out = trig.flush()                                # decode the final segment
        if out is not None:
            emit(out[1])
    if writer is not None:
        writer.release()
        print("wrote annotated video ->", args.save_video)
    if display:
        import cv2
        cv2.destroyAllWindows()
    print(f"\nDecoded {n_dec} captions over {n_steps} windows "
          f"({100.0 * n_dec / max(1, n_steps):.1f}% of steps) — decoding fired only on "
          f"semantic change; that gap is the efficiency win.")


if __name__ == "__main__":
    main()
