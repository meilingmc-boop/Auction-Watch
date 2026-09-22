<#
Sends an email notification via Gmail SMTP. Credentials never touch the
repo or chat: the app password is read from a User-scope environment
variable (AUCTION_WATCH_GMAIL_APP_PASSWORD) set once, outside of any
script, via Google App Passwords (requires 2FA on the account).

Reads the variable straight from the registry via
[Environment]::GetEnvironmentVariable(..., "User") rather than $env:,
since a process's $env: block is only rebuilt at process creation from
whatever the OS had cached at that moment - reading the registry directly
avoids depending on that timing.
#>
param(
    [Parameter(Mandatory = $true)][string]$Subject,
    [Parameter(Mandatory = $true)][string]$Body
)

$fromAddress = "meilingmc0104@gmail.com"
$toAddress = "meilingmc0104@gmail.com"

$appPassword = [Environment]::GetEnvironmentVariable("AUCTION_WATCH_GMAIL_APP_PASSWORD", "User")
if (-not $appPassword) {
    throw "AUCTION_WATCH_GMAIL_APP_PASSWORD is not set (User environment variable)."
}
$appPassword = $appPassword -replace '\s', ''

$smtp = New-Object System.Net.Mail.SmtpClient("smtp.gmail.com", 587)
$smtp.EnableSsl = $true
$smtp.Credentials = New-Object System.Net.NetworkCredential($fromAddress, $appPassword)

$mail = New-Object System.Net.Mail.MailMessage
$mail.From = $fromAddress
$mail.To.Add($toAddress)
$mail.Subject = $Subject
$mail.Body = $Body

$smtp.Send($mail)
