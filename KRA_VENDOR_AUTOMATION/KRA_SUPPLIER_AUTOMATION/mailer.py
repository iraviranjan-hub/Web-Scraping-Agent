import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv("Config.env")
load_dotenv()

logger = logging.getLogger(__name__)

# =========================================================
# EMAIL CONFIGURATION (Add these to your Config.env)
# =========================================================
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", SMTP_USERNAME)
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", SMTP_USERNAME)

def send_error_email(error_message):
    """
    Sends an email with the error message.
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured. Skipping email notification.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = "KRA iTax Automation - System Error Detected"

        body = f"""
        <html>
        <body>
            <h2 style='color: red;'>An Error has occurred in the KRA iTax System</h2>
            <p>The automation script detected a system error page while processing.</p>
            <p><strong>Error Details:</strong></p>
            <pre style='background: #f4f4f4; padding: 10px; border: 1px solid #ddd;'>
{error_message}
            </pre>
            <p>This date will be skipped or the process will terminate as per configuration.</p>
        </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
            
        logger.info(f"Error email sent successfully to {RECEIVER_EMAIL}")
        return True
    except Exception as e:
        logger.error(f"Failed to send error email: {e}")
        return False
