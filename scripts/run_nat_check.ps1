<#
Task Scheduler entry point for the NAT sale check. Runs nat_check.py,
parses its JSON, and raises a native toast notification - either per
qualifying hit, or a "no hits, sale closes at X" status if none found.
Logs each run to logs\nat_check.log for later inspection.
#>
$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "nat_check.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$python = "C:\Python310\python.exe"

try {
    $output = & $python "scripts\nat_check.py" 2>&1 | Out-String
} catch {
    $output = "EXCEPTION: $_"
}

Add-Content -Path $logFile -Value "===== $timestamp ====="
Add-Content -Path $logFile -Value $output

try {
    $data = $output | ConvertFrom-Json
} catch {
    & "$scriptDir\toast.ps1" -Title "NAT check failed" -Message "nat_check.py did not return valid JSON - see logs\nat_check.log"
    exit 1
}

if ($data.hits.Count -gt 0) {
    foreach ($hit in $data.hits) {
        $msg = "$($hit.year) $($hit.make) $($hit.model) - min bid `$$($hit.minimumBid) - $($hit.suburb), $($hit.state)"
        & "$scriptDir\toast.ps1" -Title "NAT sale hit found" -Message $msg
    }
} else {
    $close = $data.nat.current_instance.closeLocal
    if (-not $close) { $close = "unknown (no current NAT instance found)" }
    & "$scriptDir\toast.ps1" -Title "NAT check: no hits" -Message "No qualifying lots this run. Sale closes $close"
}
