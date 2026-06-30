# Watchdog Service

Monitors the Flipkart scraper app and automatically restarts it if health checks fail.

## How it works

- Checks `http://localhost:8000/health` every 60 seconds
- If 3 consecutive health checks fail, triggers automatic restart
- Prevents restart loops (won't restart if app fails within 2 minutes of last restart)
- Logs all activity to `watchdog/watchdog.log`

## Usage

### Start the watchdog:
```powershell
.\watchdog\start-watchdog.ps1
```

Or manually:
```powershell
python watchdog\watchdog.py
```

### What it monitors:
- ✅ HTTP 200 response from `/health` endpoint
- ❌ Connection errors (app crashed/not running)
- ❌ Timeout errors (app frozen)
- ❌ Non-200 status codes

### When it restarts:
- After 3 consecutive failures (3 minutes of downtime)
- Kills all Python and ngrok processes
- Runs `start-app-ngrok.ps1`
- Waits 30s for app to start

## Logs

View real-time logs:
```powershell
Get-Content watchdog\watchdog.log -Wait -Tail 20
```

## Configuration

Edit `watchdog.py` to change:
- `CHECK_INTERVAL = 60` - How often to check (seconds)
- `FAILURE_THRESHOLD = 3` - How many failures before restart
- `REQUEST_TIMEOUT = 10` - Health check timeout (seconds)
