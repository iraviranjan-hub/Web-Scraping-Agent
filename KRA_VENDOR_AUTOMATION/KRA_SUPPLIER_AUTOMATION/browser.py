from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from config import Config
import logging

logger = logging.getLogger(__name__)

class BrowserManager:
    """
    Manages the Playwright browser session.
    Ensures consistent setup and teardown of browser resources.
    """
    
    def __init__(self, playwright_instance):
        self.playwright = playwright_instance
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None

    def launch(self) -> Page:
        """
        Launches the browser with configured arguments and returns a page.
        """
        logger.info("Launching browser...")
        self.browser = self.playwright.chromium.launch(
            headless=Config.HEADLESS_MODE,
            args=Config.BROWSER_ARGS
        )
        
        # Create a context. Viewport=None allows the window to size fully to the maximized window.
        self.context = self.browser.new_context(
            viewport=None,
            accept_downloads=True
        )
        
        self.page = self.context.new_page()
        logger.info("Browser launched successfully.")
        return self.page

    def close(self):
        """Clean up browser resources."""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        logger.info("Browser resources closed.")
