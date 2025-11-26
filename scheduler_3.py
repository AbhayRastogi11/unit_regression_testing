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
# Common log file name (same in all 3 files)
LOG_FILE = os.environ.get("PIPELINE_LOG_FILE", "weather_pipeline.log")
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),                     # Console
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
                # Update environment variable
                set_access_token(access_token)
                self.last_token_refresh = datetime.now()
                logger.info(f"✅ Access token refreshed successfully at {self.last_token_refresh.strftime('%Y-%m-%d %H:%M:%S')}")
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
            logger.info("=" * 50)
            logger.info("📧 Starting Event_sending.py execution...")
            
            # Run the script
            result = subprocess.run(
                [sys.executable, self.script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                text=True,
                timeout=300,  # 5 minute timeout
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
                
            logger.info("=" * 50)
                    
        except subprocess.TimeoutExpired:
            logger.error("⏰ Event_sending.py execution timed out (5 minutes)")
        except Exception as e:
            logger.error(f"❌ Error executing Event_sending.py: {e}")
    
    def start(self):
        """Start the scheduler"""
        logger.info("=" * 60)
        logger.info("🚀 EVENT SENDING SCHEDULER WITH TOKEN REFRESH STARTED")
        logger.info("=" * 60)
        logger.info(f"📄 Script: {self.script_path}")
        logger.info(f"⏱️  Execution interval: {self.interval_seconds/60} minutes")
        logger.info(f"🔑 Token refresh interval: {self.token_manager.token_refresh_interval/60} minutes")
        logger.info("Press Ctrl+C to stop the scheduler")
        logger.info("=" * 60)
        
        try:
            # Start the token refresh thread
            self.token_manager.start_token_refresh_thread()
            
            while self.running:
                # Record start time
                start_time = datetime.now()
                self.run_count += 1
                
                logger.info(f"📋 Scheduler run #{self.run_count} started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Show token status
                if self.token_manager.last_token_refresh:
                    token_age = datetime.now() - self.token_manager.last_token_refresh
                    logger.info(f"🔑 Token last refreshed: {token_age.total_seconds()/60:.1f} minutes ago")
                
                # Run the script
                self.run_event_script()
                
                # Calculate sleep time
                execution_time = (datetime.now() - start_time).total_seconds()
                sleep_time = max(0, self.interval_seconds - execution_time)
                
                if sleep_time > 0:
                    next_run = datetime.now() + timedelta(seconds=sleep_time)
                    logger.info(f"⏳ Execution completed in {execution_time:.2f} seconds.")
                    logger.info(f"💤 Next run at {next_run.strftime('%H:%M:%S')} (sleeping for {sleep_time:.0f} seconds)")
                    logger.info("-" * 40)
                    time.sleep(sleep_time)
                else:
                    logger.warning(f"⚠️  Execution took {execution_time:.2f} seconds, which exceeds the {self.interval_seconds} second interval!")
                    logger.info("-" * 40)
                    
        except KeyboardInterrupt:
            logger.info("=" * 60)
            logger.info("🛑 SCHEDULER STOPPED BY USER (Ctrl+C)")
            logger.info("=" * 60)
            self.running = False
        except Exception as e:
            logger.critical(f"💥 Scheduler error: {e}")
            self.running = False
        finally:
            # Stop token refresh thread
            self.token_manager.stop()

def main():
    """Main function"""
    print("=" * 60)
    print("🌦️  Weather Advisory Event Sending Scheduler")
    print("🔑 With Automatic OAuth2 Token Refresh")
    print("📝 All output will be logged to scheduler.log")
    print("=" * 60)
    
    # Parameters
    script_path = "Event_sending.py"
    interval_minutes = 2
    
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

ACCESS_TOKEN = None  # global variable

def set_access_token(token: str) -> None:
    global ACCESS_TOKEN
    ACCESS_TOKEN = token

def get_access_token() -> str:
    from typing import Optional
    global ACCESS_TOKEN
    if not ACCESS_TOKEN:
        # yahan pe tum logging bhi use kar sakte ho agar chaho
        raise RuntimeError("ACCESS_TOKEN is not set in token_store yet.")
    return ACCESS_TOKEN
