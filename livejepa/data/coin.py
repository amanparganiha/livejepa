"""COIN dataset loader — training data for the predictor (Phase 2).

COIN (coin-dataset.github.io): 11,827 instructional YouTube videos, 180 tasks,
each annotated with step segments (start, end, label). The step labels are
short imperative phrases ("pour water into the cup"), which is exactly the
(clip -> caption) supervision the predictor needs.

Workflow:
1. Get the annotation file (public, no license wait):
   https://raw.githubusercontent.com/coin-dataset/annotations/master/COIN.json
2. Download some videos with yt-dlp into a directory named <video_id>.mp4
   (any subset works — the loader skips missing videos).
3. Iterate step clips:  iter_step_clips(json_path, videos_dir, k_frames=16)
   yields (sample_id, frames_list, caption) ready for data/cache.build_cache.
"""
from __future__ import annotations
import json
import os
import numpy as np

COIN_ANNOTATIONS_URL = (
    "https://raw.githubusercontent.com/coin-dataset/annotations/master/COIN.json"
)


def load_annotations(json_path):
    """Returns {video_id: {"subset", "class", "steps": [(start, end, label), ...]}}."""
    with open(json_path, encoding="utf-8") as f:
        db = json.load(f)["database"]
    out = {}
    for vid, meta in db.items():
        out[vid] = {
            "subset": meta.get("subset", "training"),
            "class": meta.get("class", ""),
            "steps": [
                (float(a["segment"][0]), float(a["segment"][1]), str(a["label"]))
                for a in meta.get("annotation", [])
            ],
        }
    return out


def sample_step_frames(video_path, start, end, k_frames=16, resolution=256):
    """Decode k evenly spaced RGB frames from [start, end] seconds via OpenCV.
    Returns a list of HxWx3 uint8 arrays, or None if the clip can't be read."""
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    lo = max(0, int(start * fps))
    hi = min(max(lo + 1, int(end * fps)), max(1, n - 1))
    idxs = np.linspace(lo, hi, k_frames).astype(int)
    frames = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.resize(frame, (resolution, resolution))
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()
    return frames if len(frames) == k_frames else None


def iter_step_clips(json_path, videos_dir, k_frames=16, resolution=256,
                    subset="training", max_clips=None, exts=(".mp4", ".mkv", ".webm")):
    """Yield (sample_id, frames_list, caption) for every annotated step whose
    video exists in `videos_dir`. Skips unreadable/missing videos silently."""
    ann = load_annotations(json_path)
    count = 0
    for vid, meta in ann.items():
        if subset and meta["subset"] != subset:
            continue
        path = next((os.path.join(videos_dir, vid + e) for e in exts
                     if os.path.exists(os.path.join(videos_dir, vid + e))), None)
        if path is None:
            continue
        for j, (s, e, label) in enumerate(meta["steps"]):
            frames = sample_step_frames(path, s, e, k_frames, resolution)
            if frames is None:
                continue
            yield f"coin_{vid}_{j:03d}", frames, label
            count += 1
            if max_clips and count >= max_clips:
                return


def gt_caption_stream(json_path, video_id):
    """For Phase 1 validation: the ground-truth (timestamp, caption) sequence
    of one video — encode these with SONAR to get a clean embedding stream."""
    ann = load_annotations(json_path)
    meta = ann[video_id]
    return [((s + e) / 2.0, label) for s, e, label in meta["steps"]]
