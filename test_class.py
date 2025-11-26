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
        self._current_token = None  # ✅ in-memory token storage only
       
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
                # ✅ store only in memory (no env)
                self._current_token = access_token
                self.last_token_refresh = datetime.now()
                logger.info(
                    f"✅ Access token refreshed successfully at "
                    f"{self.last_token_refresh.strftime('%Y-%m-%d %H:%M:%S')}"
                )
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
   
    def get_current_token(self):
        """Get the current access token (in-memory only)"""
        print(1)
        # ✅ if no token yet, try to refresh once
        if not self._current_token:
            refreshed = self.refresh_token()
            if not refreshed:
                return False
        return self._current_token  
   
    def stop(self):
        """Stop the token refresh thread"""
        self.running = False
        if self.token_refresh_thread and self.token_refresh_thread.is_alive():
            logger.info("🛑 Stopping token refresh thread...")
