# Enable the auto-restart task
# Run this as Administrator

schtasks /change /tn FlipkartAppRestart /enable

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Auto-restart task enabled successfully!" -ForegroundColor Green
    Write-Host ""
    schtasks /query /tn FlipkartAppRestart /fo LIST | Select-String "Status|Next Run Time"
} else {
    Write-Host "✗ Failed to enable task. Make sure to run as Administrator." -ForegroundColor Red
}

Read-Host "Press Enter to close"
