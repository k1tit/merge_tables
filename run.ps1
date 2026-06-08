$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "Запуск из: $PWD"
python merge_columns.py @args
if ($LASTEXITCODE -ne 0) {
    Write-Host "ОШИБКА: скрипт завершился с кодом $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Enter для выхода"
    exit $LASTEXITCODE
}
Read-Host "Enter для выхода"
