#!/usr/bin/env bash
# Exact check (2026-11-26, pre-registered in WORKLOG): VL-JEPA's "exact" selective decoding
# (no smoothing, no pooling: decode the raw step at each Ward segment's midpoint) against
# plain uniform, GT stream, faithful benchmark. Analyse with results_fidelity/exact_check.py.
# Single instance (shares results_fidelity/.lock with run_cider.sh); stop with stop_runs.sh,
# then rerun this script to resume (decodes are cached).
set -u
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
if ! mkdir results_fidelity/.lock 2>/dev/null; then echo "another runner holds results_fidelity/.lock"; exit 1; fi
trap 'rmdir results_fidelity/.lock 2>/dev/null' EXIT
echo $$ > results_fidelity/runner.pid
name=E1_proc219_first_exact
echo "=== $name start $(date '+%F %T')"
python scripts/eval_gt_fidelity.py --config configs/fidelity_exact.yaml \
  --uids-file eval_data/egoexo_takes_proc219.txt --passes first --max-seconds 0 \
  --methods uniform,adaptive --cider full --decode-cache eval_data/decode_cache_proc219.jsonl \
  --out "results_fidelity/$name" > "results_fidelity/$name.log" 2>&1
rc=$?
echo "=== $name exit $rc $(date '+%F %T')"
exit $rc
