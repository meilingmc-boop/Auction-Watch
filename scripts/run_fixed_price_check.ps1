<#
Task Scheduler entry point for the daily fixed-price check. Runs
fixed_price_check.py, parses its JSON, and raises a native toast
notification per qualifying hit. Silent (log-only) when there are no hits,
matching the "routine, don't notify" behavior used elsewhere.
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
    & "$scriptDir\toast.ps1" -Title "Fixed-price check failed" -Message "fixed_price_check.py did not return valid JSON - see logs\fixed_price_check.log"
    exit 1
}

if ($data.hits.Count -gt 0) {
    foreach ($hit in $data.hits) {
        $msg = "$($hit.year) $($hit.make) $($hit.model) - Buy Now `$$($hit.buyNowPrice) - $($hit.suburb), $($hit.state)"
        & "$scriptDir\toast.ps1" -Title "Fixed-price hit found" -Message $msg
    }
}
