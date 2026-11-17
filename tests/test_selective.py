"""Unit tests for the selective-decoding layer (the core contribution).
Run with: python -m pytest tests/ -q   (no heavy models needed)."""
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from livejepa.selective.offline import segment_stream, temporal_connectivity, decode_points
from livejepa.selective.online import VarianceTrigger, run_online, run_online_segments
from livejepa.selective.pooling import moving_average
from livejepa.eval_pareto import uniform_points, uniform_blocks
from livejepa.run_eval import select_points


def make_event_stream(events=5, seg_len=40, dim=64, noise=0.05, seed=0):
    rng = np.random.default_rng(seed)
    centers = rng.standard_normal((events, dim)).astype(np.float32)
    centers /= np.linalg.norm(centers, axis=1, keepdims=True)
    stream, labels = [], []
    for e in range(events):
        for _ in range(seg_len):
            stream.append(centers[e] + noise * rng.standard_normal(dim))
            labels.append(e)
    return np.stack(stream).astype(np.float32), np.array(labels)


def test_temporal_connectivity_shape():
    conn = temporal_connectivity(5)
    assert conn.shape == (5, 5)
    # only off-diagonal neighbors connected
    dense = conn.toarray()
    assert dense[0, 1] == 1 and dense[1, 0] == 1
    assert dense[0, 2] == 0


def test_segments_are_contiguous():
    stream, _ = make_event_stream()
    labels, mids, pooled = segment_stream(stream, n_segments=5)
    # each segment id should occupy a contiguous time range
    for s in np.unique(labels):
        idx = np.where(labels == s)[0]
        assert idx.max() - idx.min() == len(idx) - 1, "segment not contiguous"
    assert pooled.shape == (5, stream.shape[1])
    assert len(mids) == 5


def test_segment_recovers_event_count_roughly():
    stream, gt = make_event_stream(events=5, seg_len=40)
    labels, _, _ = segment_stream(stream, n_segments=5)
    # boundaries should align reasonably with true event changes
    pred_changes = np.where(np.diff(labels) != 0)[0]
    true_changes = np.where(np.diff(gt) != 0)[0]
    assert len(pred_changes) == len(true_changes) == 4


def test_decode_points_pool_vs_exact():
    stream, _ = make_event_stream()
    mids_a, emb_a = decode_points(stream, 5, pool="mean")
    mids_b, emb_b = decode_points(stream, 5, pool="none")
    assert mids_a == mids_b
    assert emb_a.shape == emb_b.shape


def test_online_trigger_fires_on_change():
    stream, _ = make_event_stream(events=5, seg_len=40)
    idxs, embs = run_online(stream, window=8, tau=0.15, min_gap=4)
    # should fire several times (roughly once per event), not every step
    assert 3 <= len(idxs) <= 30
    assert embs.shape[1] == stream.shape[1]


def test_online_trigger_quiet_on_static():
    # a static stream should fire at most once after the buffer fills
    dim = 64
    v = np.ones(dim, dtype=np.float32)
    stream = np.stack([v + 0.001 * np.random.default_rng(i).standard_normal(dim)
                       for i in range(120)])
    idxs, _ = run_online(stream, window=8, tau=0.15, min_gap=4)
    assert len(idxs) <= 2


def test_segment_trigger_emits_at_midpoints_not_boundaries():
    # the corrected online trigger should fire ~once per event at interior
    # segment midpoints (not double-fire at boundaries like the naive one)
    stream, _ = make_event_stream(events=5, seg_len=40)
    idxs, embs = run_online_segments(stream, window=8, tau=0.15, min_gap=4)
    assert 4 <= len(idxs) <= 7                       # ~one per event, no boundary doubles
    assert embs.shape[1] == stream.shape[1]
    assert all(0 < i < len(stream) for i in idxs)
    assert 8 <= idxs[0] <= 32                        # first fire near midpoint ~20, not 0/40


def test_moving_average_is_causal_and_shape_preserving():
    stream, _ = make_event_stream()
    sm = moving_average(stream, window=3)
    assert sm.shape == stream.shape
    # first element unchanged (causal, window starts at itself)
    assert np.allclose(sm[0], stream[0])


def test_uniform_blocks_partition_the_stream_around_uniform_points():
    for T in (2, 3, 7, 40, 41, 719):
        for stride in (1, 2, 3, 4, 7, 40, 100, 1000):
            idxs, blocks = uniform_blocks(T, stride)
            assert idxs == uniform_points(T, stride)
            assert len(blocks) == len(idxs)
            assert blocks[0][0] == 0 and blocks[-1][1] == T        # covers the stream
            assert all(a < b for a, b in blocks)
            assert all(x[1] == y[0] for x, y in zip(blocks, blocks[1:]))  # no gap/overlap
            assert all(a <= i < b for i, (a, b) in zip(idxs, blocks))


def test_uniform_pool_keeps_uniform_budget_and_timestamps():
    stream, _ = make_event_stream()
    sel = {"smoothing_window": 3, "pool": "mean", "linkage": "ward"}
    for hz in (1.0, 0.2, 0.05, 0.01):
        iu, eu = select_points("uniform", stream, hz, 2.0, sel)
        ip, ep = select_points("uniform_pool", stream, hz, 2.0, sel)
        ia, _ = select_points("adaptive", stream, hz, 2.0, sel)
        assert ip == iu and len(ia) == len(iu)                   # same budget, same times
        assert ep.shape == eu.shape
    # with no smoothing and no pooling it is exactly plain uniform
    raw = {"smoothing_window": 1, "pool": "none"}
    iu, eu = select_points("uniform", stream, 0.2, 2.0, raw)
    ip, ep = select_points("uniform_pool", stream, 0.2, 2.0, raw)
    assert ip == iu and np.allclose(ep, eu)


def test_take_mean_is_one_decode_of_the_whole_stream():
    stream, _ = make_event_stream()
    idxs, embs = select_points("take_mean", stream, 0.5, 2.0, {})
    assert idxs == [len(stream) // 2] and embs.shape == (1, stream.shape[1])
    assert np.allclose(embs[0], stream.mean(0))


def test_adaptive_uses_fewer_decodes_than_dense_at_quality():
    # adaptive with N=events should match event count; dense uniform needs many more
    stream, _ = make_event_stream(events=5, seg_len=40)
    mids, _ = decode_points(stream, 5)
    assert len(mids) == 5  # 5 decodes capture 5 events
    T = len(stream)
    uniform_1hz_equiv = len(range(0, T, 4))  # dense uniform
    assert len(mids) < uniform_1hz_equiv
