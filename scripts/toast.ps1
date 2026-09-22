<#
Shows a native Windows toast notification. No external modules required -
uses the WinRT toast APIs directly, borrowing PowerShell's own registered
AppUserModelID so CreateToastNotifier works without a Start Menu shortcut.
#>
param(
    [Parameter(Mandatory = $true)][string]$Title,
    [Parameter(Mandatory = $true)][string]$Message
)

[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null

function Escape-Xml([string]$s) {
    return $s -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;'
}

$safeTitle = Escape-Xml $Title
$safeMessage = Escape-Xml $Message

$template = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>$safeTitle</text>
      <text>$safeMessage</text>
    </binding>
  </visual>
</toast>
"@

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml

$appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
