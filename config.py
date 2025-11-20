"""
Configuration management for Personal Assistant
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

class Config:
    """Centralized configuration management"""
    
    def __init__(self, env_file: Optional[str] = None):
        # Load environment variables
        if env_file and Path(env_file).exists():
            load_dotenv(env_file)
        else:
            # Try to find .env in current directory or parent directories
            current_dir = Path.cwd()
            for parent in [current_dir] + list(current_dir.parents):
                env_path = parent / '.env'
                if env_path.exists():
                    load_dotenv(env_path)
                    break
        
        # Database Configuration
        self.DB_HOST = os.getenv("DB_HOST")
        self.DB_PORT = int(os.getenv("DB_PORT", "6543"))
        self.DB_NAME = os.getenv("DB_NAME", "postgres")
        self.DB_USER = os.getenv("DB_USER")
        self.DB_PASSWORD = os.getenv("DB_PASSWORD")
        
        # Email Configuration
        self.GMAIL_USERNAME = os.getenv("GMAIL_USERNAME")
        self.GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
        self.GMAIL_RECIPIENT = os.getenv("GMAIL_RECIPIENT")
        
        # Google API Configuration
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.GOOGLE_CX = os.getenv("GOOGLE_CX")
        self.SHEET_ID = os.getenv("SHEET_ID")
        
        # Service Account
        self.SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
        
        # Scheduler Configuration
        self.DAILY_SUMMARY_TIME = os.getenv("DAILY_SUMMARY_TIME", "06:00")
        
        # Validate required configurations
        self._validate()
    
    def _validate(self):
        """Validate that required configuration values are present"""
        required_configs = []
        
        # Check database configs if DB operations are needed
        if not all([self.DB_HOST, self.DB_USER, self.DB_PASSWORD]):
            required_configs.append("Database (DB_HOST, DB_USER, DB_PASSWORD)")
        
        # Check email configs if email operations are needed
        if not all([self.GMAIL_USERNAME, self.GMAIL_PASSWORD]):
            required_configs.append("Email (GMAIL_USERNAME, GMAIL_PASSWORD)")
        
        # Check Google API if search/sheets operations are needed
        if not self.GOOGLE_API_KEY:
            required_configs.append("Google API (GOOGLE_API_KEY)")
        
        if required_configs:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Missing configuration for: {', '.join(required_configs)}. "
                "Some features may not work. Please set these in .env file."
            )
    
    @property
    def db_connection_params(self):
        """Get database connection parameters as a dictionary"""
        return {
            'host': self.DB_HOST,
            'port': self.DB_PORT,
            'dbname': self.DB_NAME,
            'user': self.DB_USER,
            'password': self.DB_PASSWORD,
            'sslmode': 'require'
        }
