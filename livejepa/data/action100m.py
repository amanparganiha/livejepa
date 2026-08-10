"""Action100M-preview loader — paper-aligned training data for the predictor.

Action100M (arXiv:2601.10592, `facebook/action100m-preview` on HF, FAIR
noncommercial research license) is the dataset VL-JEPA itself trained on:
1.2M instructional videos segmented into a hierarchical "tree of captions"
(the preview covers ~10%). Each parquet row is one video:

    video_uid : YouTube id
    metadata  : {title, description, asr ...}
    nodes     : list of segments, each with
        start, end          (seconds)
        node_id, parent_id, level   (tree structure; parent_id null at root)
        plm_caption, plm_action     (PLM-3B)
        llama3_caption              (leaf nodes)
        gpt : {summary: {brief, detailed}, action: {brief, detailed, actor}}

We keep LEAF segments (finest granularity — the "one action, one sentence"
supervision the predictor needs) with an imperative-style caption, preferring
`gpt.action.brief` and falling back through the other caption fields.

Downloads: the parquet shards live at
    https://huggingface.co/datasets/facebook/action100m-preview/resolve/main/data/part-000NN.parquet
(28 shards). `scripts/download_action100m.py` fetches videos; this module only
parses annotations.
"""
from __future__ import annotations
import glob
import hashlib
import os

PARQUET_URL = ("https://huggingface.co/datasets/facebook/action100m-preview/"
               "resolve/main/data/part-{:05d}.parquet")
N_SHARDS = 28


def _get(d, *keys):
    """Nested dict lookup tolerant of None/missing/py-or-numpy containers."""
    for k in keys:
        if d is None:
            return None
        d = d.get(k) if hasattr(d, "get") else None
    return d


import re

_ID_LIKE = re.compile(r"^[A-Za-z0-9_-]+$")   # a bare token (e.g. a leaked video uid)


def node_caption(node):
    """Best imperative-style caption for a node, or None.

    Filters observed annotation noise: leaked bare identifiers ("YBXT1dqeugY")
    and one-word non-actions ("Finished.")."""
    for cand in (_get(node, "gpt", "action", "brief"),
                 node.get("plm_action"),
                 node.get("llama3_caption"),
                 node.get("plm_caption"),
                 _get(node, "gpt", "summary", "brief")):
        if cand and isinstance(cand, str):
            c = " ".join(cand.split()).strip()
            if 8 <= len(c) <= 200 and len(c.split()) >= 2 and not _ID_LIKE.match(c):
                return c
    return None


def iter_video_segments(row, min_dur=3.0, max_dur=60.0, leaf_only=True):
    """Yield (start, end, caption, node_id) for usable segments of one parquet row."""
    nodes = row.get("nodes") or []
    nodes = [n for n in nodes if n is not None]
    parents = {n.get("parent_id") for n in nodes if n.get("parent_id") is not None}
    last_cap = None
    for n in nodes:
        if leaf_only and n.get("node_id") in parents:
            continue                               # has children -> not a leaf
        try:
            s, e = float(n["start"]), float(n["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (min_dur <= e - s <= max_dur):
            continue
        cap = node_caption(n)
        if cap is None or cap == last_cap:          # drop gaps + consecutive dups
            continue
        last_cap = cap
        yield s, e, cap, n.get("node_id")


def load_segments(parquet_dir, min_dur=3.0, max_dur=60.0, leaf_only=True,
                  max_videos=0):
    """Parse all part-*.parquet in `parquet_dir`.

    Returns {video_uid: [(start, end, caption, node_id), ...]} for videos with
    at least one usable segment. Uses pyarrow via pandas per-shard (each shard
    is a few thousand rows — fine in memory one at a time)."""
    import pandas as pd
    out = {}
    shards = sorted(glob.glob(os.path.join(parquet_dir, "part-*.parquet")))
    if not shards:
        raise FileNotFoundError(f"no part-*.parquet in {parquet_dir} — "
                                "download shards first (see PARQUET_URL)")
    for shard in shards:
        df = pd.read_parquet(shard, columns=["video_uid", "nodes"])
        for row in df.itertuples(index=False):
            segs = list(iter_video_segments(
                {"nodes": list(row.nodes) if row.nodes is not None else []},
                min_dur, max_dur, leaf_only))
            if segs:
                out[row.video_uid] = segs
            if max_videos and len(out) >= max_videos:
                return out
    return out


def is_val_video(video_uid, one_in=32):
    """Deterministic video-level split: ~1/one_in of videos go to val.
    Hash-based -> stable across machines/runs; freeze by keeping one_in fixed."""
    h = int(hashlib.sha1(video_uid.encode()).hexdigest(), 16)
    return h % one_in == 0
