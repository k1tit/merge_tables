$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host ""
Write-Host "merge_columns — интерактивная сборка" -ForegroundColor Cyan
Write-Host "Папка: $PWD"
Write-Host ""
python merge_columns.py @args
exit $LASTEXITCODE
