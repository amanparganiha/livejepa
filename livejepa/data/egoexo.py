"""EgoExo4D evaluation helpers.

Implements the paper's *time-aligned* CIDEr: each ground-truth atomic-action
annotation is matched to its nearest decoded output in time, and CIDEr is
computed over the matched pairs. This is NOT whole-video captioning CIDEr.

`load_video_annotations` parses EgoExo4D atomic-action descriptions (the
paper's ground truth, ~143/video) into (timestamp, text) pairs and resolves
each take's downscaled video path. Everything else works with any list of
(timestamp, text) pairs, so you can still unit-test on synthetic data.
"""
from __future__ import annotations
import glob
import json
import os
import numpy as np


def align_nearest_in_time(decoded, ground_truth):
    """decoded: list[(t_hat, text)]; ground_truth: list[(t, text)].
    Returns dicts (refs, hyps) keyed by gt index, ready for a CIDEr scorer."""
    refs, hyps = {}, {}
    d_times = np.array([d[0] for d in decoded], dtype=np.float32)
    for i, (t, y) in enumerate(ground_truth):
        j = int(np.argmin(np.abs(d_times - t)))
        refs[i] = [y]
        hyps[i] = [decoded[j][1]]
    return refs, hyps


def time_aligned_cider(decoded, ground_truth):
    """Compute CIDEr-D over time-aligned pairs using pycocoevalcap.
    Returns a float score. Requires `pip install pycocoevalcap`."""
    from pycocoevalcap.cider.cider import Cider
    refs, hyps = align_nearest_in_time(decoded, ground_truth)
    score, _ = Cider().compute_score(refs, hyps)
    return float(score)


# ---- EgoExo4D dataset loading ----
# Layout produced by `egoexo -o <root> --parts annotations metadata
# downscaled_takes/448` (see scripts/download_egoexo_subset.{sh,ps1}):
#   <root>/takes.json
#   <root>/annotations/atomic_descriptions_<split>.json   (ground truth)
#   <root>/annotations/keystep_<split>.json               (coarser fallback)
#   <root>/takes/<take_name>/.../*.mp4                     (downscaled videos)

_SUBJECT_MAP = {"C": "the camera wearer", "O": "the other person"}


def _normalize_text(text, normalize_subject=True):
    """EgoExo4D atomic descriptions use 'C'/'O' for the actors
    ('C picks up the knife'). Expand the leading token so captions compare
    sensibly against a predictor that never emits 'C'."""
    text = str(text).strip()
    if normalize_subject and text[:2] in ("C ", "O "):
        return _SUBJECT_MAP[text[0]] + text[1:]
    return text


def _find_file(data_root, name, *, recursive=True):
    """Locate `name` directly under data_root, or anywhere beneath it."""
    direct = os.path.join(data_root, name)
    if os.path.exists(direct):
        return direct
    hits = glob.glob(os.path.join(data_root, "**", name), recursive=recursive)
    return hits[0] if hits else None


def _find_annotation_file(data_root, split, kind="atomic_descriptions"):
    return _find_file(data_root, os.path.join("annotations", f"{kind}_{split}.json")) \
        or _find_file(data_root, f"{kind}_{split}.json")


def load_takes(data_root):
    """Map take_uid -> {'take_name', 'root_dir'} from takes.json (best-effort).
    Returns {} if takes.json is absent (the loader then falls back to the uid)."""
    path = _find_file(data_root, "takes.json")
    if path is None:
        return {}
    with open(path, encoding="utf-8") as f:
        takes = json.load(f)
    if isinstance(takes, dict):              # some dumps key by uid already
        takes = list(takes.values())
    out = {}
    for t in takes:
        uid = t.get("take_uid") or t.get("uid")
        if uid:
            name = t.get("take_name", uid)
            out[uid] = {"take_name": name, "root_dir": t.get("root_dir", name)}
    return out


def _find_take_video(data_root, take_info):
    """Best-effort: find one egocentric downscaled video file for a take."""
    name, root = take_info.get("take_name", ""), take_info.get("root_dir", "")
    seen, vids = set(), []
    for d in (os.path.join(data_root, root),
              os.path.join(data_root, "takes", name),
              os.path.join(data_root, "takes", root)):
        if d and d not in seen and os.path.isdir(d):
            seen.add(d)
            vids += glob.glob(os.path.join(d, "**", "*.mp4"), recursive=True)
    if not vids:
        return None
    # prefer aria/ego streams and the downscaled (448) variant
    def score(p):
        pl = p.lower()
        return 2 * (("aria" in pl) or ("ego" in pl)) + (("downscaled" in pl) or ("448" in pl))
    return max(vids, key=score)


def load_atomic_descriptions(data_root, split="val", normalize_subject=True):
    """Return {take_uid: [(timestamp_seconds, text), ...] sorted by time}.

    Parses annotations/atomic_descriptions_<split>.json, whose shape is
    {"annotations": {take_uid: [ {"descriptions": [ {"timestamp", "text"}, ...]}, ...]}}.
    Robust to a take mapping straight to a single descriptions dict, and to a
    few alternate field names.
    """
    path = _find_annotation_file(data_root, split, "atomic_descriptions")
    if path is None:
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    anns = data.get("annotations", data) if isinstance(data, dict) else {}
    out = {}
    for uid, passes in anns.items():
        if isinstance(passes, dict):
            passes = [passes]
        pairs = []
        for p in passes:
            if not isinstance(p, dict):
                continue
            for d in p.get("descriptions", []):
                t = d.get("timestamp", d.get("timestamp_sec", d.get("time")))
                txt = d.get("text", d.get("description", d.get("narration_text")))
                if t is None or txt is None:
                    continue
                pairs.append((float(t), _normalize_text(txt, normalize_subject)))
        if pairs:
            out[uid] = sorted(pairs, key=lambda x: x[0])
    return out


def load_keystep_annotations(data_root, split="val"):
    """Fallback ground truth: keystep segments -> (midpoint_time, description)."""
    path = _find_annotation_file(data_root, split, "keystep")
    if path is None:
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    anns = data.get("annotations", data) if isinstance(data, dict) else {}
    out = {}
    for uid, meta in anns.items():
        segs = meta.get("segments", []) if isinstance(meta, dict) else []
        pairs = []
        for s in segs:
            a, b = s.get("start_time"), s.get("end_time")
            txt = s.get("step_description") or s.get("label")
            if a is None or b is None or not txt:
                continue
            pairs.append(((float(a) + float(b)) / 2.0, str(txt).strip()))
        if pairs:
            out[uid] = sorted(pairs, key=lambda x: x[0])
    return out


def load_video_annotations(data_root, split="val", source="atomic",
                           normalize_subject=True):
    """Yield (take_uid, video_path, [(t_seconds, text), ...]) for EgoExo4D takes.

    data_root: the EgoExo4D download root (e.g. ./eval_data/egoexo).
    source:    'atomic' (atomic-action descriptions — matches the paper's
               protocol) or 'keystep' (coarser step segments, fallback).
    Only takes whose downscaled video is found on disk are yielded; takes with
    annotations but no downloaded video are skipped. `video_path` is a string
    path — decode frames from it in the eval driver, then run the
    vision-encoder -> predictor stack to build the embedding stream that
    `eval_pareto.sweep` consumes alongside these annotations.
    """
    gt = (load_keystep_annotations(data_root, split) if source == "keystep"
          else load_atomic_descriptions(data_root, split, normalize_subject))
    if not gt:
        raise FileNotFoundError(
            f"No {source} annotations under {data_root!r} for split {split!r}. "
            "Fetch them with scripts/download_egoexo_subset (the 'annotations' "
            "part), or pass source='keystep'."
        )
    takes = load_takes(data_root)
    for uid, pairs in gt.items():
        info = takes.get(uid, {"take_name": uid, "root_dir": uid})
        video_path = _find_take_video(data_root, info)
        if video_path is not None:
            yield uid, video_path, pairs
