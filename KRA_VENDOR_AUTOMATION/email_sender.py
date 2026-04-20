import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from config import Config

logger = logging.getLogger(__name__)

def send_error_email(error_message):
    """
    Sends an email with the error details.
    SMTP settings should be configured in Config.env.
    """
    # Email configuration from Config (which loads from Config.env)
    sender_email = getattr(Config, "SMTP_SENDER", "")
    receiver_email = getattr(Config, "SMTP_RECEIVER", "")
    smtp_server = getattr(Config, "SMTP_SERVER", "smtp.gmail.com")
    smtp_port = getattr(Config, "SMTP_PORT", 587)
    smtp_username = getattr(Config, "SMTP_USERNAME", "")
    smtp_password = getattr(Config, "SMTP_PASSWORD", "")

    if not all([sender_email, receiver_email, smtp_username, smtp_password]):
        logger.warning("Email settings not fully configured in Config.env. Skipping email notification.")
        print("[WARNING] Email settings incomplete. Please check Config.env for SMTP_SENDER, SMTP_RECEIVER, SMTP_USERNAME, SMTP_PASSWORD.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = "KRA iTax Automation Error Notification"

        body = f"""
Dear Team,

An error occurred during the KRA iTax automation process.

Error Details:
{error_message}

The process has been terminated to prevent data inconsistencies.

Regards,
KRA Automation System
"""
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        server.quit()

        logger.info(f"Error email sent successfully to {receiver_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send error email: {e}")
        return False
