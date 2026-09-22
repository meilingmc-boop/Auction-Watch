<#
Task Scheduler entry point for the NAT sale check. Runs nat_check.py,
parses its JSON, and emails a summary - either the qualifying hits, or a
"no hits, sale closes at X" status if none found.
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
    & "$scriptDir\send_email.ps1" -Subject "Auction Watch: NAT check failed" -Body "nat_check.py did not return valid JSON - see logs\nat_check.log`n`n$output"
    exit 1
}

function Format-Upcoming([string]$label, $entries) {
    if (-not $entries -or $entries.Count -eq 0) {
        return "$label`: none currently listed"
    }
    $rows = $entries | ForEach-Object { "  - $($_.saleName) - closes $($_.closeLocal) ($($_.count) lot(s))" }
    return "$label`:`n" + ($rows -join "`n")
}

$upcomingBlock = (Format-Upcoming "Upcoming Model Y auctions" $data.upcoming.model_y) + "`n`n" + (Format-Upcoming "Upcoming SEALION 7 auctions" $data.upcoming.sealion_7)

if ($data.hits.Count -gt 0) {
    $lines = $data.hits | ForEach-Object {
        "$($_.year) $($_.make) $($_.model) - min bid `$$($_.minimumBid) (current minimum bid, not a hammer price) - $($_.suburb), $($_.state)`n$($_.url)"
    }
    $body = ($lines -join "`n`n") + "`n`n---`n`n" + $upcomingBlock
    & "$scriptDir\send_email.ps1" -Subject "Auction Watch: $($data.hits.Count) NAT sale hit(s) found" -Body $body
} else {
    $close = $data.nat.current_instance.closeLocal
    if (-not $close) { $close = "unknown (no current NAT instance found)" }
    $body = "No qualifying lots this run. Sale closes $close`n`n---`n`n" + $upcomingBlock
    & "$scriptDir\send_email.ps1" -Subject "Auction Watch: NAT check - no hits" -Body $body
}
