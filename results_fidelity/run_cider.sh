#!/usr/bin/env bash
# Fidelity rerun, part 2 (launched 2026-11-25 ~23:45): full CIDEr on the faithful benchmark,
# then the semantic attribution runs. Single instance (lock dir); stop with stop_runs.sh.
set -u
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
if ! mkdir results_fidelity/.lock 2>/dev/null; then echo "another runner holds results_fidelity/.lock"; exit 1; fi
trap 'rmdir results_fidelity/.lock 2>/dev/null' EXIT
echo $$ > results_fidelity/runner.pid
run() { name=$1; shift; echo "=== $name start $(date '+%F %T')"; python scripts/eval_gt_fidelity.py "$@" --out "results_fidelity/$name" > "results_fidelity/$name.log" 2>&1; echo "=== $name exit $? $(date '+%F %T')"; }
ALL4=uniform,uniform_pool,adaptive,take_mean
run C1_proc219_first_full_cider --uids-file eval_data/egoexo_takes_proc219.txt --passes first --max-seconds 0 --methods uniform,adaptive,uniform_pool,take_mean --cider full --decode-cache eval_data/decode_cache_proc219.jsonl
run S3_218_first_full     --uids-file eval_data/egoexo_takes_218.txt     --passes first --max-seconds 0   --methods $ALL4
run S4_218_all_full       --uids-file eval_data/egoexo_takes_218.txt     --passes all   --max-seconds 0   --methods $ALL4
run S2_proc219_all_full   --uids-file eval_data/egoexo_takes_proc219.txt --passes all   --max-seconds 0   --methods $ALL4
run S5_proc219_first_cap360 --uids-file eval_data/egoexo_takes_proc219.txt --passes first --max-seconds 360 --methods $ALL4
echo "=== ALL DONE $(date '+%F %T')"
