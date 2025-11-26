import time
import subprocess
import sys
import os
from datetime import datetime, timedelta
import logging
import threading
from dotenv import load_dotenv

# Import the OAuth2 function
from Oauth2 import get_microsoft_access_token
from token_store import set_access_token

# Load environment variables
load_dotenv()

# Configure logging to write to both console AND file
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.environ.get("SCHEDULER_LOG_FILE", "scheduler.log")

# Ensure the directory for logs exists (if log file has a path)
log_dir = os.path.dirname(LOG_FILE)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)

# Create a formatter
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Configure root logger
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),  # Console log
        logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')  # Common log file
    ]
)
logger = logging.getLogger("Scheduler")

class TokenManager:
    def __init__(self):
        self.client_id = os.environ.get("CLIENT_ID")
        self.client_secret = os.environ.get("CLIENT_SECRET")
        self.tenant_id = os.environ.get("TENANT_ID")
        self.scope = "https://graph.microsoft.com/.default"
        self.token_refresh_interval = 30 * 60  # 30 minutes in seconds
        self.last_token_refresh = None
        self.token_refresh_thread = None
        self.running = True
        
        if not self.client_id or not self.client_secret:
            raise ValueError("CLIENT_ID and CLIENT_SECRET must be set in environment variables")
    
    def refresh_token(self):
        """Refresh the OAuth2 access token"""
        try:
            logger.info("🔑 Refreshing OAuth2 access token...")
            
            access_token = get_microsoft_access_token(
                client_id=self.client_id,
                client_secret=self.client_secret,
                tenant_id=self.tenant_id,
                scope=self.scope
            )
            
            if access_token:
                # Update in-memory token store instead of environment variable
                set_access_token(access_token)
                self.last_token_refresh = datetime.now()
                logger.info(f"✅ Access token refreshed successfu...lly at {self.last_token_refresh.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"   Token length: {len(access_token)} characters")
                return True
            else:
                logger.error("❌ Failed to refresh access token")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error refreshing token: {e}")
            return False
    
    def start_token_refresh_thread(self):
        """Start the background token refresh thread"""
        def token_refresh_worker():
            # Initial token refresh
            self.refresh_token()
            
            while self.running:
                time.sleep(self.token_refresh_interval)
                if self.running:  # Check again after sleep
                    self.refresh_token()
        
        self.token_refresh_thread = threading.Thread(target=token_refresh_worker, daemon=True)
        self.token_refresh_thread.start()
        logger.info(f"🔄 Token refresh thread started (every {self.token_refresh_interval/60} minutes)")
    
    def stop(self):
        """Stop the token refresh thread"""
        self.running = False
        if self.token_refresh_thread and self.token_refresh_thread.is_alive():
            logger.info("🛑 Stopping token refresh thread...")

class EventSendingScheduler:
    def __init__(self, script_path="Event_sending.py", interval_minutes=2):
        self.script_path = script_path
        self.interval_seconds = interval_minutes * 60
        self.running = True
        self.run_count = 0
        
        # Initialize token manager
        self.token_manager = TokenManager()
        
        # Verify the script exists
        if not os.path.exists(self.script_path):
            raise FileNotFoundError(f"Script not found: {self.script_path}")
    
    def run_event_script(self):
        """Execute the Event_sending.py script"""
        try:
            logger.info(f"🚀 Starting Event_sending.py (run #{self.run_count + 1})...")
            
            # Run the script using subprocess to capture output
            result = subprocess.run(
                [sys.executable, self.script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # Log all output line by line
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.strip():
                        logger.info(f"[Event_sending] {line}")
            
            # Log completion status
            if result.returncode == 0:
                logger.info("✅ Event_sending.py completed successfully")
            else:
                logger.error(f"❌ Event_sending.py failed with return code {result.returncode}")
            
            self.run_count += 1
        
        except Exception as e:
            logger.error(f"❌ Error running Event_sending.py: {e}")
    
    def start(self):
        """Start the scheduling loop"""
        logger.info(f"📅 Scheduler started. Running {self.script_path} every {self.interval_seconds/60} minutes.")
        
        # Start token refresh thread
        self.token_manager.start_token_refresh_thread()
        
        try:
            while self.running:
                start_time = datetime.now()
                self.run_event_script()
                end_time = datetime.now()
                
                elapsed = (end_time - start_time).total_seconds()
                sleep_time = max(0, self.interval_seconds - elapsed)
                
                if sleep_time > 0:
                    logger.info(f"⏳ Sleeping for {sleep_time:.1f} seconds before next run...")
                    time.sleep(sleep_time)
                else:
                    logger.warning("⚠️ Script execution took longer than the scheduled interval!")
        
        except KeyboardInterrupt:
            logger.info("🛑 Scheduler interrupted by user (Ctrl+C)")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the scheduler and clean up"""
        logger.info("🧹 Stopping scheduler and cleaning up resources...")
        self.running = False
        self.token_manager.stop()
        logger.info("✅ Scheduler stopped.")

def main():
    script_path = os.environ.get("EVENT_SCRIPT_PATH", "Event_sending.py")
    interval_minutes_str = os.environ.get("SCHEDULER_INTERVAL_MINUTES", "2")
    
    try:
        interval_minutes = float(interval_minutes_str)
        if interval_minutes <= 0:
            raise ValueError("SCHEDULER_INTERVAL_MINUTES must be positive")
    except ValueError:
        logger.error(
            f"⚠️ Invalid SCHEDULER_INTERVAL_MINUTES='{interval_minutes_str}', defaulting to 2 minutes."
        )
        interval_minutes = 2.0
    
    logger.info(f"📂 Using script: {script_path}")
    logger.info(f"⏱️ Interval: {interval_minutes} minutes")
    
    try:
        scheduler = EventSendingScheduler(script_path, interval_minutes)
        scheduler.start()
    except FileNotFoundError as e:
        logger.critical(f"📁 Setup error: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.critical(f"🔧 Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"💥 Scheduler initialization error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()




# token_store.py

ACCESS_TOKEN = None

def set_access_token(token: str) -> None:
    global ACCESS_TOKEN
    ACCESS_TOKEN = token

def get_access_token() -> str:
    global ACCESS_TOKEN
    if not ACCESS_TOKEN:
        raise RuntimeError("ACCESS_TOKEN is not set in token_store yet.")
    return ACCESS_TOKEN
