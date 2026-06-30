"""
Watchdog service - Monitors the Flipkart app and restarts if unhealthy
Run this: python watchdog/watchdog.py
"""
import requests
import subprocess
import time
import logging
from datetime import datetime
import os
from pathlib import Path

# Get directories
SCRIPT_DIR = Path(__file__).parent
APP_DIR = SCRIPT_DIR.parent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [WATCHDOG] %(message)s',
    handlers=[
        logging.FileHandler(SCRIPT_DIR / 'watchdog.log'),
        logging.StreamHandler()
    ]
)

# Configuration
HEALTH_CHECK_URL = "http://localhost:8000/health"
CHECK_INTERVAL = 60  # Check every 60 seconds
RESTART_SCRIPT = APP_DIR / "start-app-ngrok.ps1"
FAILURE_THRESHOLD = 3  # Restart after 3 consecutive failures
REQUEST_TIMEOUT = 10  # seconds

class AppWatchdog:
    def __init__(self):
        self.consecutive_failures = 0
        self.last_restart_time = None
        self.restart_count = 0
        
    def check_health(self):
        """Check if the app is healthy"""
        try:
            response = requests.get(HEALTH_CHECK_URL, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                return True, "OK"
            else:
                return False, f"Status code: {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Connection refused - app not running"
        except requests.exceptions.Timeout:
            return False, "Health check timeout"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def restart_app(self):
        """Restart the application using PowerShell script"""
        try:
            logging.warning(f"🔄 RESTARTING APP (Restart #{self.restart_count + 1})")
            
            # Kill existing processes first
            logging.info("Killing existing Python/ngrok processes...")
            subprocess.run(
                ["powershell", "-Command", 
                 "Get-Process python,ngrok -ErrorAction SilentlyContinue | Stop-Process -Force"],
                capture_output=True,
                timeout=10
            )
            time.sleep(2)
            
            # Start the restart script in a new PowerShell window
            logging.info(f"Executing restart script: {RESTART_SCRIPT}")
            subprocess.Popen(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(RESTART_SCRIPT)],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            
            self.last_restart_time = datetime.now()
            self.restart_count += 1
            self.consecutive_failures = 0
            
            logging.info("✅ Restart initiated - waiting 30s for app to start...")
            time.sleep(30)  # Give app time to start
            
        except Exception as e:
            logging.error(f"❌ Failed to restart app: {e}")
    
    def run(self):
        """Main watchdog loop"""
        logging.info("=" * 60)
        logging.info("🐕 Watchdog service started")
        logging.info(f"Health check URL: {HEALTH_CHECK_URL}")
        logging.info(f"Check interval: {CHECK_INTERVAL}s")
        logging.info(f"Failure threshold: {FAILURE_THRESHOLD}")
        logging.info(f"Log file: {SCRIPT_DIR / 'watchdog.log'}")
        logging.info("=" * 60)
        
        while True:
            try:
                is_healthy, message = self.check_health()
                
                if is_healthy:
                    if self.consecutive_failures > 0:
                        logging.info(f"✅ App recovered (was failing {self.consecutive_failures}x)")
                    self.consecutive_failures = 0
                    logging.info(f"✓ Health check passed: {message}")
                else:
                    self.consecutive_failures += 1
                    logging.warning(
                        f"⚠️  Health check failed ({self.consecutive_failures}/{FAILURE_THRESHOLD}): {message}"
                    )
                    
                    if self.consecutive_failures >= FAILURE_THRESHOLD:
                        # Check if we recently restarted (avoid restart loops)
                        if self.last_restart_time:
                            time_since_restart = (datetime.now() - self.last_restart_time).seconds
                            if time_since_restart < 120:  # Less than 2 minutes
                                logging.error(
                                    f"❌ App failing too quickly after restart ({time_since_restart}s). "
                                    "Waiting before retry..."
                                )
                                time.sleep(60)
                                continue
                        
                        self.restart_app()
                
                # Log status every 10 checks (10 minutes)
                if int(time.time()) % (CHECK_INTERVAL * 10) < CHECK_INTERVAL:
                    uptime_info = ""
                    if self.last_restart_time:
                        uptime = datetime.now() - self.last_restart_time
                        uptime_info = f" | Uptime: {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m"
                    logging.info(
                        f"📊 Status: Restarts={self.restart_count}{uptime_info}"
                    )
                
            except KeyboardInterrupt:
                logging.info("🛑 Watchdog stopped by user")
                break
            except Exception as e:
                logging.error(f"❌ Unexpected error in watchdog loop: {e}")
            
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    watchdog = AppWatchdog()
    watchdog.run()
