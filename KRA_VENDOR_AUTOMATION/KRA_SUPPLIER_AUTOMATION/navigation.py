from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
import logging
from config import Config
import time
from datetime import datetime, timedelta
from exceptions import KRAITaxSystemError

logger = logging.getLogger(__name__)

# =========================================================
# NAVIGATION
# =========================================================
def open_certificate_page(page: Page):
    """
    Navigates to the VAT Withholding Certificate Reprint page.
    Uses mouse movement to ensure proper menu interaction.
    """
    logger.info("Opening Certificate page...")
    
    try:
        cert = page.locator("a.mainMenu[rel='Certificates']")
        cert.wait_for(timeout=20000)
        logger.info("Certificates menu found.")

        # Robust hover with retry logic
        submenu_item = page.locator("a:has-text('Reprint VAT Withholding Certificate')")
        
        # Ensure the parent is fully visible before interacting
        cert.wait_for(state="visible", timeout=10000)

        for attempt in range(3):
            logger.info(f"Hover attempt {attempt + 1} on Certificates menu...")
            cert.scroll_into_view_if_needed()
            
            # Force trigger JS events (extremely reliable for legacy systems)
            cert.dispatch_event("mouseenter")
            cert.dispatch_event("mouseover")
            
            # Then perform the visual mouse move with steps as requested
            box = cert.bounding_box()
            if box:
                page.mouse.move(
                    box["x"] + box["width"] / 2,
                    box["y"] + box["height"] / 2,
                    steps=20
                )
            else:
                cert.hover() # Fallback

            # Give a short time for the menu animation to trigger
            time.sleep(2)
            
            if submenu_item.is_visible():
                logger.info("Submenu 'Reprint VAT Withholding Certificate' is now visible.")
                break
            
            if attempt < 2:
                logger.warning("Submenu not visible yet, resetting mouse position and retrying...")
                # Reset mouse to top-left to 'de-trigger' any sticky hovers
                page.mouse.move(0, 0)
                time.sleep(1)

        # Final check and click the submenu item
        if not submenu_item.is_visible():
            logger.error("Submenu failed to appear after multiple hover attempts.")
            # Last-ditch effort: try to wait a bit longer or find by selector
            submenu_item.wait_for(state="attached", timeout=5000)

        logger.info("Clicking on 'Reprint VAT Withholding Certificate'...")
        submenu_item.click()
        page.wait_for_load_state("networkidle")
        logger.info("Certificate page loaded successfully.")
        
    except PlaywrightTimeoutError as e:
        logger.error(f"Timeout while opening certificate page: {e}")
        raise
    except Exception as e:
        logger.error(f"Error opening certificate page: {e}")
        raise

# =========================================================
# CONSULT
# =========================================================
def consult(page: Page, target_date: datetime = None, pin: str = None):
    """
    Fills the consultation form with the specified date and submits.
    If no date is provided, uses yesterday's date.
    Handles dialog popups automatically.
    
    Args:
        page: Playwright page object
        target_date: datetime object for the date to query. If None, uses yesterday.
        pin: KRA PIN to use for the form. If None, uses Config.KRA_PIN.
    """
    logger.info("Starting consultation process...")
    
    try:
        # Use provided date or default to yesterday
        if target_date is None:
            target_date = datetime.now() - timedelta(days=1)
        
        logger.info(f"Using date: {target_date.strftime('%d/%m/%Y')}")
        
        # Determine PIN to use
        actual_pin = pin if pin else Config.KRA_PIN
        
        # Fill the form fields
        logger.info("Filling consultation form...")
        page.fill("#txtwithHolderPin", actual_pin)
        logger.debug(f"Filled PIN: {actual_pin}")
        
        page.select_option("#mnth", value=str(target_date.month))
        logger.debug(f"Selected month: {target_date.month}")
        
        page.select_option("#year", value=str(target_date.year))
        logger.debug(f"Selected year: {target_date.year}")
        
        page.fill("#dtOfCert", target_date.strftime("%d/%m/%Y"))
        logger.debug(f"Filled date: {target_date.strftime('%d/%m/%Y')}")

        # Handle dialog popup (accept it automatically)
        page.once("dialog", lambda d: d.accept())
        logger.debug("Dialog handler set to auto-accept")
        
        # Submit the form
        logger.info("Submitting consultation form...")
        page.click("#submitBtn")

        # Give it a few seconds to process as requested
        time.sleep(3)

        # Check for indicators in a loop for a few more seconds if needed
        for _ in range(3):
            page_text = page.inner_text("body")
            
            # 1. Check for "Records Not Found"
            if "Records Not Found" in page_text or "No records found" in page_text:
                logger.info(f"Confirmed: No records found for {target_date.strftime('%d/%m/%Y')}.")
                return False
                
            # 2. Check for even/odd rows (Actual Data)
            if page.locator("tr.EvenRow, tr.oddRow").count() > 0:
                logger.info("Data rows detected. Proceeding to extraction.")
                return True
                
            # 3. Check for session timeout
            if "session has expired" in page_text.lower() or "login again" in page_text.lower():
                logger.error("Session expired during consultation")
                raise Exception("KRA Session Expired")
                
            # 4. Check for System Error
            if "Error Occurred" in page_text or "An Error has occurred" in page_text:
                logger.error("System error detected on page")
                return False # Just skip if it's a generic error to keep it clean

            time.sleep(1)

        # Final check for table before giving up on this day
        if page.locator("table").count() > 0:
            logger.info("Table found. Proceeding.")
            return True
            
        logger.info(f"No clear results or table found for {target_date.strftime('%d/%m/%Y')}. Skipping.")
        return False


        
    except PlaywrightTimeoutError as e:
        logger.error(f"Timeout during consultation: {e}")
        return False # Indicate failure due to timeout
    except Exception as e:
        logger.error(f"Error during consultation: {e}")
        raise # Re-raise other unexpected exceptions

