# Re-vendor a slim OpenEnv submission tree into remorph-demo for Hugging Face Spaces.
# Source defaults to ..\remorph-openenv-submission relative to this demo repo.

$ErrorActionPreference = "Stop"
$demoRoot = Split-Path -Parent $PSScriptRoot
$src = if ($env:REMORPH_OPENENV_VENDOR_SRC) { $env:REMORPH_OPENENV_VENDOR_SRC } else { Join-Path (Split-Path $demoRoot) "remorph-openenv-submission" }
$dst = Join-Path $demoRoot "remorph-openenv-submission"

if (-not (Test-Path (Join-Path $src "openenv.yaml"))) {
    Write-Error "Source OpenEnv repo not found at: $src (set REMORPH_OPENENV_VENDOR_SRC to override)"
}

if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item (Join-Path $src "remorph_openenv") $dst -Recurse
$coreFiles = @("openenv.yaml", "pyproject.toml", "requirements.txt")
foreach ($f in $coreFiles) { Copy-Item (Join-Path $src $f) $dst }
$trainReq = Join-Path $src "requirements-training.txt"
if (Test-Path $trainReq) { Copy-Item $trainReq $dst }
New-Item -Force -ItemType Directory (Join-Path $dst "artifacts\submission\training_run") | Out-Null
New-Item -Force -ItemType Directory (Join-Path $dst "artifacts\submission\telemetry") | Out-Null
Copy-Item (Join-Path $src "artifacts\submission\training_run\*") (Join-Path $dst "artifacts\submission\training_run")
Copy-Item (Join-Path $src "artifacts\submission\telemetry\rollouts.jsonl") (Join-Path $dst "artifacts\submission\telemetry")
Copy-Item (Join-Path $src "artifacts\submission\benchmark_report.json") (Join-Path $dst "artifacts\submission")
New-Item -Force -ItemType Directory (Join-Path $dst "scripts") | Out-Null
Copy-Item (Join-Path $src "scripts\train_trl_grpo.py") (Join-Path $dst "scripts")
Write-Host "Vendored OpenEnv submission into: $dst"
