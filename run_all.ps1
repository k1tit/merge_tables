$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host ""
Write-Host "merge_columns — сборка из ВСЕХ папок SOrg (3801–3806)" -ForegroundColor Cyan
Write-Host "Папка: $PWD"
Write-Host ""
python merge_columns.py --all --no-menu @args
exit $LASTEXITCODE
