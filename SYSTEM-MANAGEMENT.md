# Flipkart Price Tracker - System Management

## Auto-Restart Scheduled Task

A scheduled task named `FlipkartAppRestart` runs every 2 hours to automatically restart the app.

### Check Task Status
```powershell
Get-ScheduledTask -TaskName "FlipkartAppRestart" | Select-Object TaskName, State
```

### Disable Auto-Restart (Stop automatic restarts)
```powershell
Disable-ScheduledTask -TaskName "FlipkartAppRestart"
```

### Enable Auto-Restart (Start automatic restarts)
```powershell
Enable-ScheduledTask -TaskName "FlipkartAppRestart"
```

### Remove Auto-Restart Completely
```powershell
Unregister-ScheduledTask -TaskName "FlipkartAppRestart" -Confirm:$false
```

### View Next Run Time
```powershell
Get-ScheduledTaskInfo -TaskName "FlipkartAppRestart" | Select-Object NextRunTime, LastRunTime, LastTaskResult
```

---

## SSH Remote Access

### Connection Details
- **IP Address**: Check with `.\remote-commands.ps1`
- **Username**: Vasu
- **Port**: 22

### Remote Restart Command
```bash
ssh Vasu@<laptop-ip> "cd Desktop\Freelancer\flipkart-screen; & '.\start-app-ngrok.ps1'"
```

### Check SSH Service Status
```powershell
Get-Service -Name sshd | Select-Object Name, Status, StartType
```

### Stop SSH Service
```powershell
Stop-Service -Name sshd
```

### Start SSH Service
```powershell
Start-Service -Name sshd
```

---

## Manual App Management

### Start App Manually
```powershell
& "c:\Users\Vasu\Desktop\Freelancer\flipkart-screen\start-app-ngrok.ps1"
```

### Kill Port 8000 (if app is stuck)
```powershell
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

### Check Running Python Processes
```powershell
Get-Process -Name python -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, StartTime
```

---

## Flipkart Login Cookies

### Update Cookies (login with new credentials)
```powershell
python flipkart_login.py
```

### Delete Current Cookies
```powershell
Remove-Item flipkart_cookies.json -Force
```

---

## Quick Reference

**Most Common Commands:**

1. **Disable auto-restart**: `Disable-ScheduledTask -TaskName "FlipkartAppRestart"`
2. **Enable auto-restart**: `Enable-ScheduledTask -TaskName "FlipkartAppRestart"`
3. **Manual restart**: `& "c:\Users\Vasu\Desktop\Freelancer\flipkart-screen\start-app-ngrok.ps1"`
4. **Kill stuck app**: `Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }`

---

## Files Location
All scripts are in: `c:\Users\Vasu\Desktop\Freelancer\flipkart-screen\`

- `start-app-ngrok.ps1` - Main startup script
- `setup-ssh.ps1` - SSH server installation (requires admin)
- `setup-auto-restart.ps1` - Auto-restart task setup (requires admin)
- `remote-commands.ps1` - Show remote access commands
- `flipkart_login.py` - Update Flipkart cookies

---

## Asking Copilot for Help

**Example prompts:**
- "Disable the auto-restart task"
- "Check when the app will restart next"
- "Stop SSH service"
- "Kill the app running on port 8000"
- "Update Flipkart login cookies"
- "Show me how to restart the app manually"
