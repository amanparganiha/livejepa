#!/usr/bin/env bash
# EgoExo4D subset download helper.
# Prerequisite: sign the license at https://ego-exo4d-data.org (~48h approval),
# then install the CLI:  pip install ego4d
#
# Download ONLY annotations + a small validation subset of videos — the full
# "recommended" set is ~14 TiB and you do not need it. A few hundred validation
# videos and their key-step annotations are enough for the Pareto evaluation.
#
# Edit OUT_DIR and the universities/takes you want, then run:  bash scripts/download_egoexo_subset.sh

set -euo pipefail
OUT_DIR="./eval_data/egoexo"
mkdir -p "$OUT_DIR"

# 1) Annotations (small) — key steps / atomic actions used as ground truth.
egoexo -o "$OUT_DIR" --parts annotations

# 2) Metadata so you can pick a subset.
egoexo -o "$OUT_DIR" --parts metadata

# 3) A small subset of downscaled videos (edit --universities / --benchmarks
#    or pass a --uids file to restrict to a few hundred takes).
#    See `egoexo --help` for current flags; the CLI evolves.
egoexo -o "$OUT_DIR" --parts downscaled_takes/448 \
  --benchmarks keystep \
  # --uids your_subset_uids.txt

echo "Downloaded EgoExo4D subset to $OUT_DIR"
echo "Next: implement load_video_annotations() in livejepa/data/egoexo.py"
