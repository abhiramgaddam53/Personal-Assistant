"""
Configuration management for Personal Assistant
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Centralized configuration class"""
    
    # Base paths
    BASE_DIR = Path(__file__).parent.absolute()
    DATA_DIR = BASE_DIR / "data"
    
    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)
    
    # File paths
    SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", str(DATA_DIR / "service-account.json"))
    SAMPLE_DOCS_FILE = str(DATA_DIR / "sample.txt")
    VECTORSTORE_PATH = str(DATA_DIR / "vectorstore")
    
    # Google API Configuration
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GOOGLE_CX = os.getenv("GOOGLE_CX")
    SHEET_ID = os.getenv("SHEET_ID")
    
    # Google Services Scopes
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/tasks',
        'https://www.googleapis.com/auth/calendar'
    ]
    
    # Email Configuration
    GMAIL_USERNAME = os.getenv("GMAIL_USERNAME")
    GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
    GMAIL_RECIPIENT = os.getenv("GMAIL_RECIPIENT")
    IMAP_SERVER = "imap.gmail.com"
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    
    # Database Configuration
    DB_CONFIG = {
        "host": os.getenv("DB_HOST", "aws-0-ap-southeast-1.pooler.supabase.com"),
        "port": int(os.getenv("DB_PORT", "6543")),
        "dbname": os.getenv("DB_NAME", "postgres"),
        "user": os.getenv("DB_USER", "postgres.ixruzjparquranqfdvdm"),
        "password": os.getenv("DB_PASSWORD"),
        "sslmode": "require"
    }
    
    # Connection Pool Configuration
    DB_POOL_MIN_CONN = 1
    DB_POOL_MAX_CONN = 10
    
    # LLM Configuration
    LLM_MODEL = os.getenv("LLM_MODEL", "models/gemini-2.0-flash-exp")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    
    # Embeddings Configuration
    EMBEDDINGS_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Scheduler Configuration
    DAILY_SUMMARY_TIME = os.getenv("DAILY_SUMMARY_TIME", "06:00")  # HH:MM format
    
    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Email Fetch Configuration
    MAX_EMAILS_TO_FETCH = int(os.getenv("MAX_EMAILS_TO_FETCH", "5"))
    EMAIL_CACHE_TIMEOUT = 300  # 5 minutes in seconds
    
    # Timezone
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required_vars = {
            "GOOGLE_API_KEY": cls.GOOGLE_API_KEY,
            "GMAIL_USERNAME": cls.GMAIL_USERNAME,
            "GMAIL_PASSWORD": cls.GMAIL_PASSWORD,
            "DB_PASSWORD": cls.DB_CONFIG["password"]
        }
        
        missing = [key for key, value in required_vars.items() if not value]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True
