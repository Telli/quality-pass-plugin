$runner = Get-Command python3, python, py -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $runner) { Write-Error 'Python 3.9+ is required'; exit 2 }
if ($runner.Name -eq 'py.exe' -or $runner.Name -eq 'py') {
    & $runner.Source -3 (Join-Path $PSScriptRoot 'install-codex.py') @args
} else {
    & $runner.Source (Join-Path $PSScriptRoot 'install-codex.py') @args
}
exit $LASTEXITCODE
