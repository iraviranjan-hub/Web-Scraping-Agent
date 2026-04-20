import os
import logging
from dotenv import load_dotenv

# Load environment variables from Config.env or .env file if it exists
load_dotenv("Config.env")  # Try Config.env first
load_dotenv()  # Fallback to .env if Config.env doesn't exist

class Config:
    """Centralized configuration for KRA iTax Automation."""
    
    # Base URLs
    KRA_URL = "https://itax.kra.go.ke/KRA-Portal/"
    
    # Credentials (Securely loaded)
    KRA_PIN = os.getenv("KRA_PIN", "")
    KRA_PASSWORD = os.getenv("KRA_PASSWORD", "")
    
    # System Paths
    # Default to standard install location if not set
    TESSERACT_PATH = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    
    # Output Paths
    JSON_PATH = os.getenv("JSON_PATH", "kra_data.json")    # Default to current directory
    WHT_CERTIFICATE_BASE_PATH = os.getenv("WHT_CERTIFICATE_BASE_PATH", "Certificates")
    
    # Security
    API_KEY = os.getenv("KRA_API_KEY", "KRA-ADMIN-786-92") # Default fallback key
    

 # API Server Configuration
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8103))
    


    # Automation Settings
    DB_ENABLED = os.getenv("DB_ENABLED", "False").lower() == "false"
    HEADLESS_MODE = True  # Set to True for production loop execution if desired
    BROWSER_ARGS = [
        "--start-maximized",
        "--disable-infobars",
        "--disable-notifications",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-popup-blocking"
    ]
    
    # Timeouts & Retries
    DEFAULT_TIMEOUT = 60000  # 60 seconds
    MAX_CAPTCHA_RETRIES = 5
    MAX_RUNTIME_RETRIES = 5
    RETRY_DELAY = 5 # seconds between major retries
    
    # Logging Configuration
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    @staticmethod
    def validate():
        """Validate critical configuration is present."""
        missing = []
        if not Config.KRA_PIN:
            missing.append("KRA_PIN")
        if not Config.KRA_PASSWORD:
            missing.append("KRA_PASSWORD")
            
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
