# LiveJEPA - export the irreplaceable parts of the project off this machine.
#
# Context: the working directory is ~120 GB, but most of it is either
# re-downloadable or redundant. This copies only what CANNOT be rebuilt, with a
# manifest so you can prove the copy arrived intact.
#
# What it copies (~19.4 GB) and why:
#   data_cache_coin_full      12.6 GB  4 days of three-lane extraction, 99.6% of
#                                      COIN. LEAST replaceable thing here: 1,650
#                                      YouTube links were ALREADY dead during
#                                      extraction and more die every month, so
#                                      re-running it would now yield less.
#   data_cache_egoexo          5.4 GB  in-domain training pairs behind the headline
#   data_cache_*_val           1.2 GB  the frozen validation sets - without these
#                                      the scaling table is no longer comparable
#   checkpoints (2 files)      0.2 GB  predictor_30000.pt (deployed, cos 0.846)
#                                      and EgoExo predictor_20000.pt (the headline)
#   eval_data/streams          0.1 GB  cached predicted streams; re-scoring is
#                                      instant with them, ~84 h without
#   eval_data/egoexo/annotations 0.2 GB ground truth (video itself is NOT copied)
#   decode caches              small   ~24k cached SONAR decodes
#
# NOT copied, deliberately:
#   eval_data/egoexo/takes  63 GB  re-downloadable with fresh EgoExo credentials
#   backups/                21 GB  redundant tars of the caches above
#   intermediate checkpoints       only the two that produced results are kept
#   data_cache_a100m               only needed to re-run C2/C3, both closed negatives
#   source code / docs / thesis    those live in git - do NOT rely on this copy
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\export_project.ps1 -Dest E:\livejepa_archive
#   powershell -ExecutionPolicy Bypass -File scripts\export_project.ps1 -Dest E:\livejepa_archive -Verify
#
# -Verify adds SHA-256 of every copied file (slow: ~10-20 min for 19 GB) and is
# worth it once, for the copy you intend to keep.
#
# Pure ASCII (PowerShell 5.1).

param(
    [Parameter(Mandatory = $true)][string]$Dest,
    [switch]$Full,
    [switch]$Verify
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

# Priority = upload/copy order. If the transfer is interrupted, everything
# already moved is the stuff that mattered most. Priority 1 is ~1.7 GB and
# takes minutes; priority 6 is the 63 GB that is re-downloadable anyway.
$items = @(
    @{ P = 1; Path = "checkpoints_c1_final\predictor_30000.pt"; Note = "DEPLOYED ckpt, cos 0.846" },
    @{ P = 1; Path = "checkpoints_egoexo\predictor_20000.pt";   Note = "EgoExo ckpt, the 9.9x headline" },
    @{ P = 1; Path = "eval_data\streams";              Note = "cached predicted streams" },
    @{ P = 1; Path = "eval_data\egoexo\annotations";   Note = "EgoExo ground-truth annotations" },
    @{ P = 1; Path = "eval_data\frozen_val_uids.txt";  Note = "frozen benchmark uids" },
    @{ P = 1; Path = "eval_data\egoexo_takes_218.txt"; Note = "density-matched take list" },
    @{ P = 1; Path = "eval_data\egoexo_takes_pred40.txt"; Note = "40-take headline subset" },
    @{ P = 1; Path = "data_cache_coin_full_val";       Note = "COIN val (956-sample diverse)" },
    @{ P = 1; Path = "data_cache_coin2_val";           Note = "COIN frozen 137-sample val" },
    @{ P = 1; Path = "data_cache_egoexo_val";          Note = "EgoExo val" },
    @{ P = 2; Path = "data_cache_coin_full";           Note = "COIN train cache - LEAST replaceable" },
    @{ P = 3; Path = "data_cache_egoexo";              Note = "EgoExo in-domain train pairs" }
)
Get-ChildItem (Join-Path $repo "eval_data") -Filter "*.jsonl" -File -EA SilentlyContinue |
    ForEach-Object { $items += @{ P = 1; Path = "eval_data\$($_.Name)"; Note = "SONAR decode cache" } }

# -Full: for when storage is not the constraint (e.g. a 5 TB Drive). Adds the
# intermediate checkpoints (they let you reproduce the scaling-table rows
# without retraining), the A100M cache, and the raw EgoExo video.
if ($Full) {
    foreach ($c in @("checkpoints_c1_p1", "checkpoints_c2", "checkpoints_c3_combined",
                     "checkpoints_kaggle", "checkpoints_c1_final", "checkpoints_egoexo")) {
        $items += @{ P = 4; Path = $c; Note = "checkpoint set (scaling-table reproducibility)" }
    }
    $items += @{ P = 5; Path = "data_cache_a100m";     Note = "Action100M cache (C2/C3 negatives)" }
    $items += @{ P = 5; Path = "data_cache_a100m_val"; Note = "Action100M val" }
    $items += @{ P = 6; Path = "eval_data\egoexo\takes"; Note = "EgoExo VIDEO - re-downloadable, do last" }
    $items += @{ P = 6; Path = "eval_data\action100m";   Note = "A100M parquet manifests" }
}
$items = $items | Sort-Object { $_.P }

Write-Host "LiveJEPA export"
Write-Host "  from: $repo"
Write-Host "  to  : $Dest"
Write-Host ""

# --- space check before touching anything ---------------------------------
$need = 0
foreach ($it in $items) {
    $src = Join-Path $repo $it.Path
    if (Test-Path $src) {
        $i = Get-Item $src
        $need += if ($i.PSIsContainer) {
            (Get-ChildItem $src -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum
        } else { $i.Length }
    } else {
        Write-Host ("  MISSING (skipped): " + $it.Path) -ForegroundColor Yellow
    }
}
$needGB = [math]::Round($need / 1GB, 2)
Write-Host ("  need: " + $needGB + " GB")

New-Item -ItemType Directory -Force $Dest | Out-Null
$destRoot = (Get-Item $Dest).FullName
$drive = (Get-Item $destRoot).PSDrive
if ($drive -and $drive.Free) {
    $freeGB = [math]::Round($drive.Free / 1GB, 2)
    Write-Host ("  free on " + $drive.Name + ": " + $freeGB + " GB")
    if ($drive.Free -lt $need * 1.05) {
        Write-Host "NOT ENOUGH SPACE - aborting before copying anything." -ForegroundColor Red
        exit 1
    }
}
Write-Host ""

# --- copy ------------------------------------------------------------------
$manifest = @()
foreach ($it in $items) {
    $src = Join-Path $repo $it.Path
    if (-not (Test-Path $src)) { continue }
    $dst = Join-Path $destRoot $it.Path
    New-Item -ItemType Directory -Force (Split-Path -Parent $dst) | Out-Null

    Write-Host ("copying " + $it.Path + "  (" + $it.Note + ")")
    if ((Get-Item $src).PSIsContainer) {
        # /E subdirs incl. empty, /R:2 retries, /NFL /NDL quiet, /NP no progress spam
        robocopy $src $dst /E /R:2 /W:2 /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { Write-Host ("  robocopy FAILED (" + $LASTEXITCODE + ")") -ForegroundColor Red }
    } else {
        Copy-Item $src $dst -Force
    }

    $files = if ((Get-Item $dst).PSIsContainer) { Get-ChildItem $dst -Recurse -File } else { @(Get-Item $dst) }
    $sum = ($files | Measure-Object Length -Sum).Sum
    $manifest += [PSCustomObject]@{
        P     = $it.P
        Path  = $it.Path
        Note  = $it.Note
        Files = $files.Count
        Bytes = $sum
        MB    = [math]::Round($sum / 1MB, 1)
    }
}

# --- manifest --------------------------------------------------------------
$mfPath = Join-Path $destRoot "MANIFEST.txt"
$lines = @(
    "LiveJEPA archive manifest",
    ("created : " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    ("source  : " + $repo),
    "",
    "Source code, docs and the thesis are NOT here - they are in the git repo.",
    "This archive holds only what git cannot carry: feature caches, the two",
    "checkpoints behind the thesis results, cached streams and GT annotations.",
    "",
    "EgoExo4D annotations are licensed to the individual who was granted access.",
    "Keep this archive private; do not redistribute it.",
    ""
)
foreach ($m in $manifest) {
    $lines += ("p{0}  {1,-44} {2,7} files {3,10} MB   {4}" -f $m.P, $m.Path, $m.Files, $m.MB, $m.Note)
}
$total = ($manifest | Measure-Object Bytes -Sum).Sum
$lines += ""
$lines += ("TOTAL: {0} entries, {1} GB" -f $manifest.Count, [math]::Round($total / 1GB, 2))
Set-Content -Path $mfPath -Value $lines -Encoding UTF8
Write-Host ""
Write-Host ("wrote " + $mfPath)

if ($Verify) {
    Write-Host "hashing (slow, but this is how you know the copy is good)..."
    $hashPath = Join-Path $destRoot "SHA256SUMS.txt"
    $all = Get-ChildItem $destRoot -Recurse -File | Where-Object { $_.Name -ne "SHA256SUMS.txt" }
    $i = 0
    $out = foreach ($f in $all) {
        $i++
        if ($i % 200 -eq 0) { Write-Host ("  " + $i + "/" + $all.Count) }
        $h = Get-FileHash $f.FullName -Algorithm SHA256
        ($h.Hash + "  " + $f.FullName.Substring($destRoot.Length + 1))
    }
    Set-Content -Path $hashPath -Value $out -Encoding UTF8
    Write-Host ("wrote " + $hashPath + "  (" + $all.Count + " files)")
}

Write-Host ""
Write-Host ("DONE - " + [math]::Round($total / 1GB, 2) + " GB archived to " + $destRoot)
Write-Host "Remember: one copy is not a backup. Keep this on the laptop AND one other place."
