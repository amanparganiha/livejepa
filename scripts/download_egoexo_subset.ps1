# EgoExo4D subset download helper (Windows / PowerShell).
#
# Prerequisite: sign the license at https://ego-exo4d-data.org, then supply the
# AWS credentials the portal issued you.
#
# 1) Install the downloader CLI:
#        pip install ego4d
#
# 2) Provide your EgoExo4D AWS credentials. Do NOT hard-code them in this file
#    or commit them. Either set them for this session:
#        $env:AWS_ACCESS_KEY_ID     = "<access key id>"
#        $env:AWS_SECRET_ACCESS_KEY = "<secret access key>"
#        $env:AWS_DEFAULT_REGION    = "<region, e.g. us-east-2>"
#    or persist them once with:  aws configure
#    (EgoExo4D keys are time-limited — regenerate from the portal if downloads
#     later start returning 403/expired-token errors.)
#
# Downloads ONLY annotations + metadata + a small downscaled video subset. The
# full "recommended" set is ~14 TiB and is NOT needed for the Pareto eval — a
# few dozen validation takes and their atomic-action annotations are enough.
#
# Edit $OutDir if you want the data on another drive, then run:
#        powershell -ExecutionPolicy Bypass -File scripts/download_egoexo_subset.ps1

$ErrorActionPreference = "Stop"
$OutDir = "./eval_data/egoexo"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# 1) Annotations (small) — atomic actions / key steps used as ground truth.
egoexo -o $OutDir --parts annotations

# 2) Metadata (takes.json, etc.) so the loader can resolve video paths.
egoexo -o $OutDir --parts metadata

# 3) A small subset of downscaled (448px) videos for the keystep benchmark.
#    Restrict to a handful of takes with `--uids <take_uid> <take_uid> ...`
#    (enough to trace the Pareto curve); the CLI flags evolve, see `egoexo --help`.
egoexo -o $OutDir --parts downscaled_takes/448 --benchmarks keystep

Write-Host "Downloaded EgoExo4D subset to $OutDir"
Write-Host "Next: livejepa.data.egoexo.load_video_annotations(r'$OutDir', split='val') is ready to consume it."
