# Delete the FlipkartAppRestart scheduled task
# Run this as Administrator

Write-Host "Deleting FlipkartAppRestart task..." -ForegroundColor Yellow

schtasks /delete /tn FlipkartAppRestart /f

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Task deleted successfully!" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to delete task. Make sure to run as Administrator." -ForegroundColor Red
    Write-Host "Or the task may already be deleted." -ForegroundColor Yellow
}

Write-Host ""
Read-Host "Press Enter to close"
