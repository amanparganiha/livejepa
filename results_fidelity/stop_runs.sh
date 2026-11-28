#!/usr/bin/env bash
# Stop the fidelity runner AND its python child (TaskStop alone leaves them running on Windows).
cd "$(dirname "$0")/.."
[ -f results_fidelity/runner.pid ] && kill -9 "$(cat results_fidelity/runner.pid)" 2>/dev/null
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*eval_gt_fidelity*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force; 'stopped python ' + \$_.ProcessId }"
rmdir results_fidelity/.lock 2>/dev/null; echo "stopped; rerun run_cider.sh to resume (decodes are cached)"
