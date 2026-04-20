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
        page.fill("#txtwithHoldeePin", actual_pin)
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

        # Wait for page transition / load
        page.wait_for_load_state("networkidle", timeout=10000)
        time.sleep(2) # Extra buffer for KRA's slow transitions

        # Check for "Records Not Found" message
        if page.locator("text=Records Not Found").is_visible(timeout=2000):
            logger.info(f"No records found for {target_date.strftime('%d/%m/%Y')}. Skipping this date.")
            return False
            
        # Check for iTax system errors using page content as a more robust fallback
        content = page.content()
        error_keywords = [
            "An Error has occurred",
            "Error Occurred",
            "Problem encountered in iTax",
            "Your Error Reference No. is"
        ]
        
        system_error_msg = None
        for kw in error_keywords:
            if kw in content:
                system_error_msg = kw
                break
        
        if system_error_msg:
            logger.warning(f"KRA System Error keyword '{system_error_msg}' detected in page content.")
            # Extract multiple possible error text locations
            error_details_list = []
            
            # Common error elements
            selectors = ["div.error", "div.errormsg", ".errorMessage", "#errorMsg", "table.pagebody"]
            for selector in selectors:
                try:
                    elements = page.locator(selector).all_inner_texts()
                    for text in elements:
                        if text.strip() and ("Error" in text or "Reference" in text):
                            error_details_list.append(text.strip())
                except:
                    pass
            
            if not error_details_list:
                # Last resort: capture visible text from body
                body_text = page.locator("body").inner_text()
                if "Error" in body_text:
                    error_details_list.append(body_text[:1000]) # Cap it
            
            # Clean up and join error details
            error_details = " | ".join(sorted(list(set(error_details_list))))
            if not error_details or len(error_details) < 10:
                error_details = f"iTax System Error detected (Keyword: {system_error_msg})"
                
            logger.error(f"KRA iTax System Error Detected: {error_details}")
            print(f"\n{'='*50}")
            print(f" [CRITICAL ERROR] KRA iTax System Error Detected")
            print(f" Message: {error_details}")
            print(f"{'='*50}\n")
            
            # Raise a specific exception that main.py can handle to stop the process and send mail
            raise KRAITaxSystemError(error_details)

        # Wait for results table to appear
        logger.info("Waiting for results table...")
        page.wait_for_selector("table", state="attached", timeout=20000)
        logger.info("Consultation completed successfully. Results table loaded.")
        return True
        
    except PlaywrightTimeoutError as e:
        logger.error(f"Timeout during consultation: {e}")
        return False # Indicate failure due to timeout
    except Exception as e:
        logger.error(f"Error during consultation: {e}")
        raise # Re-raise other unexpected exceptions

