"""Extract and cache (V-JEPA 2 tokens, SONAR target) pairs for training.

This is a TEMPLATE. Wire in your dataset's (frames, caption) iterator for
COIN / Action100M-preview / etc., then run:

    python scripts/extract_features.py --config configs/default.yaml

In stub mode it will fabricate a tiny synthetic cache so you can test
train.py end-to-end without any data or models.
"""
import argparse, os, sys
import yaml, numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from livejepa.encoders.vision import VisionEncoder
from livejepa.encoders.sonar import SonarSpace
from livejepa.data.cache import build_cache


def your_clip_iterator(cfg, args):
    """Yield (sample_id, frames_list, caption). COIN is wired in; pass
    --coin-json and --videos-dir (see livejepa/data/coin.py for setup)."""
    if args.coin_json and args.videos_dir:
        from livejepa.data.coin import iter_step_clips
        vc = cfg["encoders"]["vision"]
        return iter_step_clips(args.coin_json, args.videos_dir,
                               k_frames=vc["frames_per_window"],
                               resolution=vc["resolution"],
                               max_clips=args.max_clips)
    raise SystemExit(
        "Provide --coin-json and --videos-dir (or --synthetic). "
        "See livejepa/data/coin.py for how to get COIN annotations + videos."
    )


def synthetic_clip_iterator(n=64, K=16, H=64, W=64):
    """Fabricate tiny clips so the pipeline can be tested without data."""
    captions = ["person opens fridge", "person pours water", "person chops onion",
                "person stirs pot", "person washes dish", "person wipes table"]
    rng = np.random.default_rng(0)
    for i in range(n):
        cap = captions[i % len(captions)]
        base = (i % len(captions)) * 30
        frames = [np.clip(base + rng.integers(0, 40, (H, W, 3)), 0, 255).astype("uint8")
                  for _ in range(K)]
        yield f"synth_{i:04d}", frames, cap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--synthetic", action="store_true",
                    help="use the built-in synthetic clips (default in stub mode)")
    ap.add_argument("--coin-json", default=None, help="path to COIN.json annotations")
    ap.add_argument("--videos-dir", default=None, help="dir of <video_id>.mp4 files")
    ap.add_argument("--max-clips", type=int, default=None)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))

    vision = VisionEncoder(cfg)
    sonar = SonarSpace(cfg)

    use_synth = args.synthetic or (cfg["project"]["use_stubs"] and not args.coin_json)
    clips = synthetic_clip_iterator() if use_synth else your_clip_iterator(cfg, args)
    build_cache(cfg, clips, vision, sonar)


if __name__ == "__main__":
    main()
