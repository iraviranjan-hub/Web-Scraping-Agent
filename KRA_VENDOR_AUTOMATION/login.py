from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
import logging
from config import Config
import time
from captcha_solver import CaptchaSolver

logger = logging.getLogger(__name__)

class LoginPage:
    """
    Page Object Model for the KRA iTax Login operations.
    Encapsulates all selectors and interactions for the login flow.
    """
    
    def __init__(self, page: Page):
        self.page = page

    # ==========================
    # Selectors
    # ==========================
    # First Screen
    INPUT_PIN = "#logid"
    BTN_CONTINUE = "text=Continue"
    
    # Second Screen
    INPUT_PASSWORD = "input[type='password']"
    INPUT_CAPTCHA = "#captcahText"
    BTN_LOGIN = "#loginButton"
    IMG_CAPTCHA = "#captcha_img"
    
    # Validation
    DASHBOARD_ELEMENT = "a.mainMenu[rel='Certificates']"  # Good indicator of success
    ERROR_MESSAGE = ".error, #errorDiv" # Generic error content selector (adjust as needed)

    def navigate(self):
        """Navigates to the KRA portal and validates load."""
        logger.info(f"Navigating to {Config.KRA_URL}")
        self.page.goto(Config.KRA_URL, timeout=Config.DEFAULT_TIMEOUT)
        
        # Wait for page to be ready
        self.page.wait_for_load_state("networkidle", timeout=10000)
        
        # Validate page load - check title and PIN input field
        page_title = self.page.title()
        pin_visible = self.page.is_visible(self.INPUT_PIN)
        
        logger.debug(f"Page title: {page_title}")
        logger.debug(f"PIN input visible: {pin_visible}")
        
        if "KRA" not in page_title and not pin_visible:
            # Try waiting a bit more for the PIN field
            try:
                self.page.wait_for_selector(self.INPUT_PIN, timeout=5000)
                pin_visible = True
            except PlaywrightTimeoutError:
                pass
        
        # Final validation - PIN field must be visible (title check is secondary)
        if not pin_visible:
            raise Exception(f"Failed to load KRA Portal login page. Title: '{page_title}', PIN field visible: {pin_visible}")
        
        logger.info(f"Page loaded successfully. Title: '{page_title}'")

    def enter_pin(self, pin: str):
        """Enters the KRA PIN and clicks continue."""
        logger.info(f"Entering PIN: {pin}")
        self.page.fill(self.INPUT_PIN, pin)
        self.page.click(self.BTN_CONTINUE)
        
        # Wait for Password field to appear
        try:
            self.page.wait_for_selector(self.INPUT_PASSWORD, state="visible", timeout=10000)
            logger.info("Proceeded to password section.")
        except PlaywrightTimeoutError:
            raise Exception("Failed to transition to password screen. Invalid PIN or system lag.")

    def perform_secure_login(self, password: str) -> bool:
        """
        Handles the password entry and captcha solving loop.
        Returns True if login is successful, False otherwise.
        """
        logger.info("Attempting login sequence...")
        
        # Enter Password once (it usually stays filled unless page refreshes)
        self.page.fill(self.INPUT_PASSWORD, password)
        
        for attempt in range(1, Config.MAX_CAPTCHA_RETRIES + 1):
            logger.info(f"Captcha Attempt {attempt}/{Config.MAX_CAPTCHA_RETRIES}")
            
            # 1. Capture and Solve Captcha
            captcha_val = self._handle_captcha()
            if not captcha_val:
                logger.warning("Could not solve captcha. Reloading captcha image...")
                self._refresh_captcha()
                continue
                
            # 2. Enter Captcha and Submit
            self.page.fill(self.INPUT_CAPTCHA, captcha_val)
            
            # Click login and wait for reaction
            # We use a race condition check: Success vs Error vs Timeout
            try:
                with self.page.expect_navigation(timeout=5000): # Sometimes it navigates
                    self.page.click(self.BTN_LOGIN)
            except:
                pass # Navigation might not trigger immediately or at all if AJAX
                
            # 3. Validation
            try:
                # Check for success
                self.page.wait_for_selector(self.DASHBOARD_ELEMENT, timeout=5000)
                logger.info("Login Successful! Dashboard detected.")
                return True
            except PlaywrightTimeoutError:
                # Check for specific error (e.g., Wrong Captcha)
                # Note: You might need to inspect the DOM to find the exact error text element
                # For now, we assume if dashboard isn't there, we failed.
                logger.warning(f"Login attempt {attempt} failed (Dashboard not found). Retrying...")
                
                # If we are here, likely captcha was wrong or page refreshed.
                # In a real scenario, we might need to check if password field is still there.
                if self.page.is_visible(self.INPUT_PASSWORD):
                     self._refresh_captcha()
                else:
                    # If we aren't on password page anymore but not logged in, something weird happened
                    logger.error("Lost focus of login page during retry.")
                    return False
                    
        return False

    def _handle_captcha(self) -> str:
        """Captures captcha element and solves it."""
        try:
            # Wait for image to be stable
            self.page.wait_for_selector(self.IMG_CAPTCHA, state="visible")
            time.sleep(1) # Brief setling time
            
            # Screenshot the element directly
            captcha_bytes = self.page.locator(self.IMG_CAPTCHA).screenshot()
            
            return CaptchaSolver.solve(captcha_bytes)
        except Exception as e:
            logger.error(f"Error handling captcha: {e}")
            return None

    def _refresh_captcha(self):
        """Refreshes the page or clicks a refresh button if available."""
        # Simple page reload is often safest if no refresh button, 
        # BUT page reload might clear password and PIN.
        # Based on screenshots/knowledge, often there isn't one, so we might need to reload.
        logger.info("Refreshing login page state...")
        self.page.reload()
        
        # Wait for page to load and re-enter credentials
        self.page.wait_for_selector(self.INPUT_PIN)
        self.page.fill(self.INPUT_PIN, Config.KRA_PIN)
        self.page.click(self.BTN_CONTINUE)
        
        # Wait for password field and re-fill password after reload
        self.page.wait_for_selector(self.INPUT_PASSWORD)
        self.page.fill(self.INPUT_PASSWORD, Config.KRA_PASSWORD)
