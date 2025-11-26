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
import Event_sending

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
        """Execute the Event_sending main() directly in the same process."""
        try:
            logger.info(f"🚀 Starting Event_sending.main() (run #{self.run_count + 1})...")
            
            # ✅ yahan direct function call ho raha hai – NO subprocess
            Event_sending.main()
            
            logger.info("✅ Event_sending.main() completed successfully")
            self.run_count += 1

        except Exception as e:
            logger.error(f"❌ Error running Event_sending.main(): {e}", exc_info=True)

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

            if not self.token_manager.refresh_token():
                logger.error("❌ Initial token refresh failed. Event_sending may fail until token is fixed.")
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



