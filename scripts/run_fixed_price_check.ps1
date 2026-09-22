<#
Task Scheduler entry point for the daily fixed-price check. Runs
fixed_price_check.py, parses its JSON, and emails a summary of qualifying
hits. Silent (log-only) when there are no hits, matching the "routine,
don't notify" behavior used elsewhere.
Logs each run to logs\fixed_price_check.log.
#>
$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "fixed_price_check.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$python = "C:\Python310\python.exe"

try {
    $output = & $python "scripts\fixed_price_check.py" 2>&1 | Out-String
} catch {
    $output = "EXCEPTION: $_"
}

Add-Content -Path $logFile -Value "===== $timestamp ====="
Add-Content -Path $logFile -Value $output

try {
    $data = $output | ConvertFrom-Json
} catch {
    & "$scriptDir\send_email.ps1" -Subject "Auction Watch: fixed-price check failed" -Body "fixed_price_check.py did not return valid JSON - see logs\fixed_price_check.log`n`n$output"
    exit 1
}

if ($data.hits.Count -gt 0) {
    $lines = $data.hits | ForEach-Object {
        "$($_.year) $($_.make) $($_.model) - Buy Now `$$($_.buyNowPrice) - $($_.suburb), $($_.state)`n$($_.url)"
    }
    $body = $lines -join "`n`n"
    & "$scriptDir\send_email.ps1" -Subject "Auction Watch: $($data.hits.Count) fixed-price hit(s) found" -Body $body
}
