"""Tests for the Action100M loader + cache-time token subsampling (Phase A)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.data.action100m import node_caption, iter_video_segments, is_val_video
from livejepa.data.cache import cache_sample


def _node(nid, parent, s, e, **caps):
    n = {"node_id": nid, "parent_id": parent, "start": s, "end": e, "level": 1}
    n.update(caps)
    return n


def test_node_caption_priority_and_fallback():
    n = _node(1, None, 0, 10,
              gpt={"action": {"brief": "pour the water"}, "summary": {"brief": "sum"}},
              plm_action="plm act", llama3_caption="llama cap")
    assert node_caption(n) == "pour the water"
    n = _node(1, None, 0, 10, plm_action="  chop   the onion  ")
    assert node_caption(n) == "chop the onion"          # whitespace normalized
    assert node_caption(_node(1, None, 0, 10)) is None  # nothing usable
    assert node_caption(_node(1, None, 0, 10, plm_action="x")) is None  # too short
    assert node_caption(_node(1, None, 0, 10, plm_action="YBXT1dqeugY")) is None  # id leak
    assert node_caption(_node(1, None, 0, 10, plm_action="Finished.")) is None  # 1 word


def test_iter_video_segments_leaf_duration_dedup():
    row = {"nodes": [
        _node(0, None, 0, 100, plm_action="root summary here"),       # non-leaf
        _node(1, 0, 0, 30, plm_action="whisk the eggs"),              # ok
        _node(2, 0, 30, 31, plm_action="too short duration"),         # < min_dur
        _node(3, 0, 31, 60, plm_action="whisk the eggs"),             # consecutive dup
        _node(4, 0, 60, 90, plm_action="fold in the flour"),          # ok
    ]}
    segs = list(iter_video_segments(row, min_dur=3, max_dur=60))
    assert [c for _, _, c, _ in segs] == ["whisk the eggs", "fold in the flour"]
    assert segs[0][0] == 0 and segs[0][1] == 30


def test_is_val_video_deterministic_and_sparse():
    uids = [f"vid{i:05d}" for i in range(3200)]
    val = [u for u in uids if is_val_video(u)]
    assert val == [u for u in uids if is_val_video(u)]   # deterministic
    assert 0.01 < len(val) / len(uids) < 0.07            # ~1/32


def test_cache_sample_max_tokens_matches_collate(tmp_path):
    tokens = np.random.randn(2048, 8).astype(np.float32)
    target = np.random.randn(4).astype(np.float32)
    cache_sample(str(tmp_path), "s1", tokens, target, "cap", max_tokens=256)
    d = np.load(tmp_path / "s1.npz")
    assert d["tokens"].shape == (256, 8)
    # identical rule to livejepa.train.collate
    expect = tokens[np.linspace(0, len(tokens) - 1, 256).astype(int)]
    assert np.allclose(d["tokens"].astype(np.float32), expect.astype(np.float16), atol=1e-3)
    # max_tokens=0 keeps everything
    cache_sample(str(tmp_path), "s2", tokens, target, "cap", max_tokens=0)
    assert np.load(tmp_path / "s2.npz")["tokens"].shape == (2048, 8)
