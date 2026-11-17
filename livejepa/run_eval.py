"""Real end-to-end Pareto evaluation driver.

Turns each evaluation video into a stream of predicted SONAR embeddings, runs
adaptive selective decoding vs. uniform-interval decoding across a frequency
sweep, decodes the selected embeddings with SONAR, scores time-aligned CIDEr
against the ground-truth (timestamp, caption) annotations, and plots the two
Pareto curves. This is the glue between the encoders/predictor and
``eval_pareto.sweep`` — the piece needed for the real thesis result.

Datasets:  coin (downloaded subset)  |  egoexo (EgoExo4D)
Stream modes:
  gt         SONAR embeddings of the GT captions laid out over time — a clean
             signal that isolates the selective mechanism (Phase 1 on real data).
  predictor  V-JEPA 2 over sliding windows -> trained predictor -> rescale to
             native norm — the full system (Phase 3).

Usage:
  python -m livejepa.run_eval --dataset coin --mode gt
  python -m livejepa.run_eval --dataset coin --mode predictor \
         --ckpt checkpoints/predictor_1000.pt --max-videos 3 --max-seconds 120
"""
from __future__ import annotations
import argparse
import hashlib
import os
import time
import json
import glob
import yaml
import numpy as np

from livejepa.eval_pareto import uniform_points, uniform_blocks, hz_to_stride
from livejepa.selective.offline import decode_points as adaptive_points
from livejepa.selective.online import run_online

# selection methods select_points understands; the first two are the published sweep
METHODS = ("uniform", "adaptive", "uniform_pool", "take_mean")


# --------------------------------------------------------------------------- #
# decode caching: SONAR beam decode is the runtime bottleneck. Cache by a
# rounded-embedding key so identical / repeated vectors (very common for gt
# streams and for uniform selection reused across frequencies) decode once.
# --------------------------------------------------------------------------- #
class CachedDecoder:
    """Decode with an in-memory cache, optionally persisted to disk.

    `cache_path` (JSON-lines, one {"k": sha1, "t": text} per decode) makes long
    sweeps restart-safe: a run killed after hours resumes reusing every decode
    it already paid for. Written LF and flushed per batch so a torn final line
    from a hard kill costs one entry, not the file.
    """

    def __init__(self, sonar, round_dp=4, cache_path=None):
        self.sonar, self.round_dp = sonar, round_dp
        self.cache, self.calls, self.hits = {}, 0, 0
        self.cache_path, self._fh = cache_path, None
        if cache_path:
            if os.path.exists(cache_path):
                with open(cache_path, encoding="utf-8") as f:
                    for line in f:
                        try:
                            e = json.loads(line)
                        except Exception:
                            continue
                        self.cache[e["k"]] = e["t"]
                print(f"decode cache: resumed {len(self.cache)} entries "
                      f"from {cache_path}", flush=True)
            else:
                os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
            self._fh = open(cache_path, "a", encoding="utf-8", newline="\n")

    def _key(self, emb):
        return hashlib.sha1(np.round(emb, self.round_dp).tobytes()).hexdigest()

    def decode(self, embs):
        embs = np.atleast_2d(np.asarray(embs, dtype=np.float32))
        keys = [self._key(e) for e in embs]
        miss_idx, pending = [], set()          # dedupe within the batch too
        for i, k in enumerate(keys):
            if k not in self.cache and k not in pending:
                pending.add(k)
                miss_idx.append(i)
        self.calls += len(keys)
        self.hits += len(keys) - len(miss_idx)
        if miss_idx:
            decoded = self.sonar.decode(embs[miss_idx])
            for i, txt in zip(miss_idx, decoded):
                self.cache[keys[i]] = txt
                if self._fh:
                    self._fh.write(json.dumps({"k": keys[i], "t": txt}) + "\n")
            if self._fh:
                self._fh.flush()
        return [self.cache[k] for k in keys]


# --------------------------------------------------------------------------- #
# stream builders
# --------------------------------------------------------------------------- #
def build_gt_stream(gt_pairs, fps, sonar, noise=0.0, seed=0, max_seconds=None):
    """Clean embedding stream from GT (timestamp, text) pairs.

    Each timestep is assigned the SONAR embedding of the nearest-in-time GT
    caption (piecewise-constant), optionally perturbed by Gaussian noise to
    emulate prediction jitter. `max_seconds` caps long takes (EgoExo4D takes can
    run very long). Returns (stream (T, d), times (T,))."""
    pairs = sorted(gt_pairs, key=lambda x: x[0])
    if max_seconds:
        pairs = [p for p in pairs if p[0] <= max_seconds] or pairs[:1]
    t_end = min(pairs[-1][0], max_seconds) if max_seconds else pairs[-1][0]
    T = max(2, int(round(t_end * fps)) + 1)
    times = np.arange(T) / fps
    uniq = list(dict.fromkeys(t for _, t in pairs))           # unique captions
    emb_by_text = {t: e for t, e in zip(uniq, sonar.encode(uniq))}
    p_times = np.array([p[0] for p in pairs], dtype=np.float32)
    rng = np.random.default_rng(seed)
    stream = np.empty((T, sonar.dim), dtype=np.float32)
    for i, tt in enumerate(times):
        text = pairs[int(np.argmin(np.abs(p_times - tt)))][1]
        e = emb_by_text[text]
        if noise > 0:
            e = e + noise * rng.standard_normal(e.shape).astype(np.float32)
        stream[i] = e
    return stream, times


def read_frames_at_fps(video_path, fps, max_seconds, resolution=256):
    """Sample RGB frames from a video at `fps` (up to max_seconds) via OpenCV.
    Returns (frames, src_times) where src_times[i] is the TRUE source timestamp
    (seconds) of frame i — so window timestamps stay correct even if the decoder
    drops frames (e.g. VFR/webm), avoiding time-alignment drift."""
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], []
    vfps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    nframes = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    dur = (nframes / vfps) if nframes else max_seconds
    dur = min(dur, max_seconds)
    T = max(1, int(dur * fps))
    want = (np.arange(T) / fps * vfps).astype(int)             # source frame idxs
    frames, src_times, wi, idx = [], [], 0, 0
    while wi < len(want):
        ok, frame = cap.read()
        if not ok:
            break
        if idx == want[wi]:
            f = cv2.resize(frame, (resolution, resolution))
            rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
            frames.append(rgb); src_times.append(idx / vfps); wi += 1
            while wi < len(want) and want[wi] == idx:          # dup if fps>vfps
                frames.append(rgb); src_times.append(idx / vfps); wi += 1
        idx += 1
    cap.release()
    return frames, src_times


def build_predictor_stream(video_path, cfg, vision, predict, fps,
                           max_seconds, win_stride=1, cache_path=None):
    """V-JEPA 2 over sliding windows -> predictor -> native-scale stream.

    Returns (stream (T, d), times (T,)). Caches to `cache_path` (npz) so reruns
    skip the expensive encoding."""
    if cache_path and os.path.exists(cache_path):
        d = np.load(cache_path)
        return d["stream"].astype(np.float32), d["times"].astype(np.float32)

    K = cfg["encoders"]["vision"]["frames_per_window"]
    res = cfg["encoders"]["vision"]["resolution"]
    frames, src_times = read_frames_at_fps(video_path, fps, max_seconds, res)
    if len(frames) < K:
        return None, None
    embs, times = [], []
    for t in range(K - 1, len(frames), win_stride):
        window = frames[t - K + 1: t + 1]
        tokens = vision.encode_window(window)
        embs.append(predict(tokens))
        times.append(float(np.mean(src_times[t - K + 1: t + 1])))  # true window-center time
    stream = np.stack(embs).astype(np.float32)
    times = np.asarray(times, dtype=np.float32)
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        np.savez_compressed(cache_path, stream=stream, times=times)
    return stream, times


# --------------------------------------------------------------------------- #
# selection + scoring
# --------------------------------------------------------------------------- #
def _smooth_stream(x, w):
    """Moving-average smooth each embedding dim over a window of w steps.

    Denoises the (noisy) predictor-mode stream before adaptive segmentation so
    Ward boundaries land on real semantic transitions rather than per-step noise.
    w<=1 is a no-op. A mean of native-scale vectors stays native-scale, so the
    pooled result remains in-distribution for the SONAR decoder."""
    x = np.asarray(x, dtype=np.float32)
    w = int(w)
    if w <= 1 or len(x) <= 2:
        return x
    k = np.ones(w, dtype=np.float32) / w
    return np.stack([np.convolve(x[:, j], k, mode="same")
                     for j in range(x.shape[1])], axis=1).astype(np.float32)


def select_points(method, stream, hz, fps, sel_cfg):
    """Return (decode_indices, embeddings_to_decode) for a method at frequency hz."""
    T = len(stream)
    stride = hz_to_stride(hz, fps)
    if method == "uniform":
        idxs = uniform_points(T, stride)
        return idxs, np.asarray(stream)[idxs]
    if method == "adaptive":
        # match uniform's decode budget exactly so the two curves are compared
        # at the same requested frequency (not just T//stride vs range(...))
        n_seg = max(1, min(T, len(uniform_points(T, stride))))
        # smoothing_window/linkage default to no-op/ward -> reproduces prior runs
        s = _smooth_stream(stream, sel_cfg.get("smoothing_window", 1))
        return adaptive_points(s, n_seg, pool=sel_cfg.get("pool", "mean"),
                               linkage=sel_cfg.get("linkage", "ward"))
    if method == "uniform_pool":
        # Uniform PLACEMENT given adaptive's treatment of the stream: the same
        # pre-smoothing and the same pooling (each fixed block's mean, or the
        # smoothed step itself when pool='none'). This is the like-for-like
        # baseline: VL-JEPA (sec. 4.6) reports that average pooling helps both
        # schedules, so a uniform that decodes raw single steps is handicapped.
        s = _smooth_stream(stream, sel_cfg.get("smoothing_window", 1))
        idxs, blocks = uniform_blocks(T, stride)
        if sel_cfg.get("pool", "mean") == "mean":
            return idxs, np.stack([s[a:b].mean(0) for a, b in blocks])
        return idxs, s[idxs]
    if method == "take_mean":
        # A reference, not a schedule: ONE decode per video, the mean of the
        # whole stream, timestamped mid-video; hz is ignored. It measures how
        # much of a time-aligned score can be had with no timing at all.
        return [T // 2], np.asarray(stream, dtype=np.float32).mean(0, keepdims=True)
    raise ValueError(method)


def corpus_cider(decoded_per_video, gt_per_video):
    """Pool time-aligned (ref, hyp) pairs across all videos -> one CIDEr-D."""
    from pycocoevalcap.cider.cider import Cider
    refs, hyps, k = {}, {}, 0
    for decoded, gt in zip(decoded_per_video, gt_per_video):
        if not decoded:
            continue
        d_times = np.array([d[0] for d in decoded], dtype=np.float32)
        for (t, y) in gt:
            j = int(np.argmin(np.abs(d_times - t)))
            refs[k], hyps[k] = [y], [decoded[j][1]]
            k += 1
    if not refs:
        return 0.0
    return float(Cider().compute_score(refs, hyps)[0])


# --------------------------------------------------------------------------- #
# dataset iteration
# --------------------------------------------------------------------------- #
def iter_coin_videos(cfg):
    """Yield (video_id, video_path, gt_pairs) for downloaded COIN videos.

    cfg['eval']['coin_split'] in {all, val, train} restricts to the class-based
    held-out split (mirrors scripts/build_coin_cache.py: last video per
    multi-video class -> val) so predictor-mode eval doesn't score on the
    predictor's own training videos. Prefers .mp4 (OpenCV seek hangs on webm)."""
    from collections import defaultdict
    from livejepa.data.coin import load_annotations
    root = cfg["eval"]["data_root"]
    vdir = os.path.join(root, "coin_videos")
    ann = load_annotations(os.path.join(root, "COIN.json"))
    exts = (".mp4", ".mkv", ".webm")
    by_id = {}
    for p in sorted(glob.glob(os.path.join(vdir, "*")),
                    key=lambda x: (os.path.splitext(x)[1].lower() != ".mp4", x)):
        vid = os.path.splitext(os.path.basename(p))[0].split(".")[0]
        if os.path.splitext(p)[1] in exts and vid in ann and ann[vid]["steps"]:
            by_id.setdefault(vid, p)                            # .mp4 variant wins
    split = cfg["eval"].get("coin_split", "all")
    if split in ("train", "val"):
        by_class = defaultdict(list)
        for vid in sorted(by_id):
            by_class[ann[vid]["class"]].append(vid)
        val = {v[-1] for v in by_class.values() if len(v) >= 2}
        keep = val if split == "val" else (set(by_id) - val)
        by_id = {v: p for v, p in by_id.items() if v in keep}
    for vid, path in sorted(by_id.items()):
        gt = [((s + e) / 2.0, label) for s, e, label in ann[vid]["steps"]]
        yield vid, path, gt


def iter_egoexo_videos(cfg, require_video=True, gt_source="atomic", uids=None):
    """Yield (take_uid, video_path|None, gt_pairs) for EgoExo4D val takes.

    require_video=True (predictor mode) yields only takes whose downscaled video
    is on disk; False (gt mode) yields every annotated take from annotations
    alone, so the mechanism can be validated without downloading videos.
    gt_source: 'atomic' (dense atomic-action descriptions, the paper's GT) or
    'keystep' (coarser, temporally-stable step segments)."""
    from livejepa.data.egoexo import (load_video_annotations,
                                      load_atomic_descriptions, load_keystep_annotations)
    root = os.path.join(cfg["eval"]["data_root"], "egoexo")
    if require_video:
        for uid, path, gt in load_video_annotations(root, split="val", source=gt_source):
            if uids is None or uid in uids:
                yield uid, path, gt
    else:
        loader = (load_keystep_annotations if gt_source == "keystep"
                  else load_atomic_descriptions)
        gt = loader(root, split="val")
        # densest takes first: with --max-videos N this reproduces the paper's
        # protocol shape (their 218 val videos average ~143 annotations/video;
        # ranking by annotation count selects the comparable subset). Ties break
        # by uid so the ordering — and any cached artifacts — stay deterministic.
        for uid in sorted(gt, key=lambda u: (-len(gt[u]), u)):
            if uids is None or uid in uids:
                yield uid, None, gt[uid]


def iter_eval_videos(cfg, dataset, require_video=True, gt_source="atomic", uids=None):
    if dataset == "coin":
        return iter_coin_videos(cfg)
    return iter_egoexo_videos(cfg, require_video, gt_source, uids)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def run(cfg, dataset, mode, ckpt, freqs, max_videos, max_seconds, win_stride,
        gt_noise, gt_source, out_png, out_json, uids_file=None, decode_cache=None,
        methods=("uniform", "adaptive")):
    uids = None
    if uids_file:
        uids = {l.strip() for l in open(uids_file) if l.strip()}
        print(f"take filter: {len(uids)} uids from {uids_file}", flush=True)
    from livejepa.encoders.sonar import SonarSpace
    sonar = SonarSpace(cfg)
    dec = CachedDecoder(sonar, cache_path=decode_cache)
    fps = cfg["eval"]["fps"]
    sel_cfg = cfg["selective"]

    # predictor mode loads V-JEPA 2 + the predictor on the first stream that is
    # not already cached: with every stream cached they would sit idle next to
    # the SONAR decoder and spill an 8 GB GPU into shared memory
    vision = predict = None

    # 1. build a stream + GT for each video
    built = []
    stream_dir = os.path.join(cfg["eval"]["data_root"], "streams")
    for vid, path, gt in iter_eval_videos(cfg, dataset,
                                          require_video=(mode == "predictor"),
                                          gt_source=gt_source, uids=uids):
        if max_videos and len(built) >= max_videos:
            break
        t0 = time.time()
        if mode == "gt":
            stream, times = build_gt_stream(gt, fps, sonar, noise=gt_noise,
                                            max_seconds=max_seconds)
        else:
            K = cfg["encoders"]["vision"]["frames_per_window"]
            ck = "randproj" if not ckpt else f"{os.path.basename(ckpt)}.{int(os.path.getmtime(ckpt))}"
            cache_path = os.path.join(
                stream_dir,
                f"{dataset}_{vid}_K{K}_fps{fps}_ws{win_stride}_ms{int(max_seconds)}_{ck}.npz")
            if vision is None and not os.path.exists(cache_path):
                from livejepa.encoders.vision import VisionEncoder
                from livejepa.predictor.infer import load_predictor
                vision = VisionEncoder(cfg)
                predict = load_predictor(cfg, ckpt)
            stream, times = build_predictor_stream(
                path, cfg, vision, predict, fps, max_seconds, win_stride, cache_path)
        if stream is None or len(stream) < 2:
            print(f"  skip {vid} (no/short stream)")
            continue
        # score against GT within the stream's covered span (mirror max_seconds cap)
        gt_s = [p for p in gt if p[0] <= max_seconds] or gt[:1] if max_seconds else gt
        built.append((vid, stream, times, gt_s))
        print(f"  {vid}: stream T={len(stream)} steps, {len(gt)} GT events "
              f"({time.time()-t0:.1f}s)")
    if not built:
        raise SystemExit("No usable videos. Check eval.data_root and downloads.")

    if mode == "predictor":                                     # free encoder memory
        try:
            import torch; del vision; torch.cuda.empty_cache()
        except Exception:
            pass

    # 2. sweep frequency for each method, pooling CIDEr across videos.
    #    Partial results are flushed after every (method, hz) so a killed run
    #    still leaves usable curves behind (see decode cache for resumability).
    results = {}
    t_sweep = time.time()

    def _summary(partial):
        return {"dataset": dataset, "mode": mode, "ckpt": ckpt,
                "n_videos": len(built), "fps": fps, "max_seconds": max_seconds,
                "gt_source": gt_source, "partial": partial, "results": results}

    for method in methods:
        curve = []
        results[method] = curve            # bound early so flushes see progress
        for hz in freqs:
            t_hz = time.time()
            decoded_pv, gts_pv, n_dec, secs = [], [], 0, 0.0
            for n_v, (vid, stream, times, gt) in enumerate(built, 1):
                idxs, embs = select_points(method, stream, hz, fps, sel_cfg)
                caps = dec.decode(embs)
                decoded_pv.append(list(zip([float(times[i]) for i in idxs], caps)))
                gts_pv.append(gt)
                n_dec += len(idxs); secs += len(stream) / fps
                if n_v % 50 == 0:
                    print(f"    {method} {hz:g}Hz: {n_v}/{len(built)} takes | "
                          f"cache {dec.hits}/{dec.calls} | {time.time()-t_hz:.0f}s",
                          flush=True)
            cider = corpus_cider(decoded_pv, gts_pv)
            avg_hz = n_dec / secs if secs else 0.0
            curve.append({"target_hz": hz, "avg_hz": avg_hz,
                          "n_decodes": n_dec, "cider": cider})
            print(f"  [{method:8}] target={hz:5.2f}Hz avg={avg_hz:5.3f}Hz "
                  f"n={n_dec:4d} CIDEr={cider:.3f}  "
                  f"({time.time()-t_hz:.0f}s, total {(time.time()-t_sweep)/60:.0f}m)",
                  flush=True)
            if out_json:
                json.dump(_summary(True), open(out_json, "w"), indent=2)

    print(f"decode cache: {dec.hits}/{dec.calls} hits "
          f"({100*dec.hits/max(1,dec.calls):.0f}% reused)")

    summary = _summary(False)
    if out_json:
        json.dump(summary, open(out_json, "w"), indent=2)
        print("wrote", out_json)
    if out_png:
        plot_pareto(results, out_png, title=f"LiveJEPA Pareto — {dataset} ({mode} stream)")
    return summary


def plot_pareto(results, out_png, title="LiveJEPA Pareto"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 5))
    styles = {"uniform": dict(marker="s", color="#888", ls="--"),
              "adaptive": dict(marker="o", color="#2c7fb8", ls="-"),
              "uniform_pool": dict(marker="^", color="#e6550d", ls="-."),
              "take_mean": dict(marker="x", color="#333", ls="none", ms=9)}
    for method, curve in results.items():
        xs = [c["avg_hz"] for c in curve]
        ys = [c["cider"] for c in curve]
        order = np.argsort(xs)
        ax.plot(np.array(xs)[order], np.array(ys)[order],
                label=method, **styles.get(method, {}))
    ax.set_xscale("log")
    ax.set_xlabel("avg decoding frequency (Hz, log)")
    ax.set_ylabel("time-aligned CIDEr-D")
    ax.set_title(title)
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.tight_layout(); fig.savefig(out_png, dpi=130)
    print("wrote", out_png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--dataset", default="coin", choices=["coin", "egoexo"])
    ap.add_argument("--mode", default="gt", choices=["gt", "predictor"])
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--max-videos", type=int, default=0, help="0 = all")
    ap.add_argument("--max-seconds", type=float, default=180.0,
                    help="cap video length for predictor mode")
    ap.add_argument("--win-stride", type=int, default=1,
                    help="encode every Nth window (predictor mode)")
    ap.add_argument("--gt-noise", type=float, default=0.0,
                    help="Gaussian noise added to gt-mode stream (rel. to native scale)")
    ap.add_argument("--freqs", default=None,
                    help="comma-separated Hz; default = config eval.freq_sweep_hz minus 2.0")
    ap.add_argument("--gt-source", default="atomic", choices=["atomic", "keystep"],
                    help="egoexo GT/stream source: dense atomic descriptions or coarse keysteps")
    ap.add_argument("--coin-split", default="all", choices=["all", "train", "val"],
                    help="restrict COIN videos to the held-out class-based split (val = held out)")
    ap.add_argument("--out", default=None, help="output basename (png+json)")
    ap.add_argument("--uids-file", default=None,
                    help="text file of take uids (one per line) to evaluate, "
                         "e.g. eval_data/egoexo_takes_218.txt")
    ap.add_argument("--decode-cache", default="eval_data/decode_cache.jsonl",
                    help="on-disk SONAR decode cache (JSONL) making long sweeps "
                         "restart-safe; pass '' to disable")
    ap.add_argument("--methods", default="uniform,adaptive",
                    help="comma-separated selection methods: uniform, adaptive, "
                         "uniform_pool (uniform placement with adaptive's smoothing "
                         "and pooling -- the like-for-like baseline), take_mean "
                         "(one decode per video; a reference)")
    args = ap.parse_args()
    methods = [m for m in args.methods.split(",") if m]
    bad = [m for m in methods if m not in METHODS]
    if bad:
        ap.error(f"unknown method(s) {bad}; choose from {list(METHODS)}")

    cfg = yaml.safe_load(open(args.config))
    cfg["project"]["use_stubs"] = False
    cfg["eval"]["coin_split"] = args.coin_split
    if args.freqs:
        freqs = [float(x) for x in args.freqs.split(",")]
    else:                                                       # drop the saturated 2 Hz point by default
        freqs = [f for f in cfg["eval"]["freq_sweep_hz"] if f < 2.0]
    base = args.out or f"results_{args.dataset}_{args.mode}"
    run(cfg, args.dataset, args.mode, args.ckpt, freqs,
        args.max_videos, args.max_seconds, args.win_stride, args.gt_noise,
        args.gt_source, out_png=base + ".png", out_json=base + ".json",
        uids_file=args.uids_file, decode_cache=args.decode_cache or None,
        methods=methods)


if __name__ == "__main__":
    main()
