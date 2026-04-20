from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
import logging
import time
from exceptions import KRAITaxSystemError

logger = logging.getLogger(__name__)

# =========================================================
# TABLE SCRAPING (EvenRow & oddRow WITH SCROLLING)
# =========================================================
def extract_table(page: Page):
    """
    Extracts table data from the KRA VAT Withholding Certificate page.
    Processes EvenRow and oddRow classes separately with scrolling to ensure all rows are captured.
    Returns headers and data rows.
    """
    logger.info("Starting table scraping...")

    try:
        # First check if there's a system error visible
        check_for_system_errors(page)

        # Wait for table to be attached to DOM
        # Try to find the specific results table first
        results_table_selector = "table#reprintVATCertReprintTable, table.pagebody"
        try:
            page.wait_for_selector(results_table_selector, state="attached", timeout=15000)
            logger.info("Results table found and attached to DOM")
        except:
            page.wait_for_selector("table", state="attached", timeout=30000)
            logger.info("Fallback: General table found")

        # Extract total records (with short timeout)
        try:
            total_records_locator = page.locator("text=Total Records")
            total_records_text = total_records_locator.inner_text(timeout=5000)
            total_records = total_records_text.split(":")[-1].strip()
            logger.info(f"Total Records found: {total_records}")
        except Exception:
            # If label not found, it might be an empty table or unexpected structure
            logger.debug("Total Records label not found, continuing...")
            total_records = "N/A"

        # Extract total VAT Withholding Amount
        try:
            total_amount_text = page.locator("table.pagebody tr", has_text="Total VAT Withholding Amount")
            total_amount = total_amount_text.locator("td").nth(2).inner_text().strip()
            logger.debug(f"Total VAT Withholding Amount: {total_amount}")
            print(f"Total VAT Withholding Amount: {total_amount}")
        except Exception as e:
            logger.warning(f"Could not extract Total VAT Withholding Amount: {e}")
            total_amount = "N/A"
                
        # Fixed header names (in exact order)
        fixed_headers = [
            "Sr.No.",
            "Withholder PIN",
            "Withholdee PIN",
            "Withholder Name",
            "Pay Point Name",
            "Status",
            "Invoice No",
            "Certificate Date",
            "VAT Withholding Amount",
            "WHT Certificate No"
        ]
        
        # Try to extract headers from table
        try:
            header_row = page.locator("table tr").nth(0)
            extracted_headers = [h.strip() for h in header_row.locator("th").all_text_contents()]
            
            # Use fixed headers if count matches, otherwise use extracted or fixed as fallback
            if len(extracted_headers) == len(fixed_headers):
                headers = fixed_headers
                logger.info("Using fixed header sequence (matched count)")
            elif len(extracted_headers) > 0:
                headers = extracted_headers
                logger.warning(f"Using extracted headers. Count: {len(extracted_headers)}, Expected: {len(fixed_headers)}")
            else:
                # Empty headers - use fixed headers
                headers = fixed_headers
                logger.warning("No headers extracted from table, using fixed headers")
        except Exception as e:
            # If extraction fails, use fixed headers
            headers = fixed_headers
            logger.warning(f"Header extraction failed: {e}. Using fixed headers")

        logger.info(f"Final headers ({len(headers)} columns):")
        for idx, h in enumerate(headers, 1):
            logger.info(f"  {idx:2d}. {h}")

        seen = set()
        data = []
    
        #wait for 10 seconds to load the table
        time.sleep(10)

        # Try multiple selector variations for EvenRow
        even_selectors = [
            "tr.EvenRow",
            "tr.evenRow", 
            "tr[class*='EvenRow']",
            "tr[class*='evenRow']",
            "tr[class*='Even']",
        ]
        
        # Try multiple selector variations for oddRow
        odd_selectors = [
            "tr.oddRow",
            "tr.OddRow",
            "tr[class*='oddRow']",
            "tr[class*='OddRow']",
            "tr[class*='odd']",
        ]
        
        # Find EvenRow selector that works
        even_rows = None
        even_count = 0
        for selector in even_selectors:
            try:
                test_rows = page.locator(selector)
                count = test_rows.count()
                if count > even_count:
                    even_rows = test_rows
                    even_count = count
                    logger.info(f"Found {even_count} EvenRow(s) using selector: {selector}")
            except Exception as e:
                logger.debug(f"EvenRow selector '{selector}' failed: {e}")
                continue
        
        # Find oddRow selector that works
        odd_rows = None
        odd_count = 0
        for selector in odd_selectors:
            try:
                test_rows = page.locator(selector)
                count = test_rows.count()
                if count > odd_count:
                    odd_rows = test_rows
                    odd_count = count
                    logger.info(f"Found {odd_count} oddRow(s) using selector: {selector}")
            except Exception as e:
                logger.debug(f"oddRow selector '{selector}' failed: {e}")
                continue
        
        total_row_count = even_count + odd_count
        logger.info(f"Total rows found: {even_count} EvenRow(s) + {odd_count} oddRow(s) = {total_row_count} rows")
        
        if total_row_count == 0:
            logger.warning("No EvenRow or oddRow found. Trying fallback: all table rows...")
            # Fallback: try to find any data rows (skip header)
            all_rows = page.locator("table tr")
            row_count = all_rows.count()
            logger.info(f"Total table rows (including header): {row_count}")
            
            if row_count <= 1:
                raise Exception("No data rows found in table")
            else:
                # Use all rows except header
                for i in range(1, row_count):  # Start from 1 to skip header
                    try:
                        row_locator = all_rows.nth(i)
                        _process_row(row_locator, i-1, "TableRow", seen, data, total_records, total_amount)
                    except Exception as e:
                        logger.warning(f"Error processing table row {i}: {e}")
        else:
            # Process EvenRow rows
            if even_count > 0 and even_rows:
                logger.info(f"Processing {even_count} EvenRow(s)...")
                for i in range(even_count):
                    try:
                        row_locator = even_rows.nth(i)
                        _process_row(row_locator, i, "EvenRow", seen, data, total_records, total_amount)
                    except Exception as e:
                        logger.warning(f"Error processing EvenRow {i}: {e}")
                        # Try scrolling and retry
                        try:
                            even_rows.nth(i).scroll_into_view_if_needed()
                            time.sleep(0.5)
                            _process_row(even_rows.nth(i), i, "EvenRow (retry)", seen, data, total_records, total_amount)
                        except Exception as retry_error:
                            logger.warning(f"Retry failed for EvenRow {i}: {retry_error}")
            
            # Process oddRow rows
            if odd_count > 0 and odd_rows:
                logger.info(f"Processing {odd_count} oddRow(s)...")
                for i in range(odd_count):
                    try:
                        row_locator = odd_rows.nth(i)
                        _process_row(row_locator, even_count + i, "oddRow", seen, data, total_records, total_amount)
                    except Exception as e:
                        logger.warning(f"Error processing oddRow {i}: {e}")
                        # Try scrolling and retry
                        try:
                            odd_rows.nth(i).scroll_into_view_if_needed()
                            time.sleep(0.5)
                            _process_row(odd_rows.nth(i), even_count + i, "oddRow (retry)", seen, data, total_records, total_amount)
                        except Exception as retry_error:
                            logger.debug(f"Retry failed for oddRow {i}: {retry_error}")

        if not data:
            logger.info("No data rows found on this page. Moving to next date.")
            return headers, []

        logger.info(f"Table scraping completed. Total rows: {len(data)}")
        return headers, data

    except PlaywrightTimeoutError as e:
        logger.error(f"Timeout while waiting for table: {e}")
        check_for_system_errors(page)
        raise
    except Exception as e:
        logger.error(f"Error during table scraping: {e}")
        check_for_system_errors(page)
        raise


def _process_row(row_locator, index, row_type, seen, data, total_records, total_amount):
    """Helper function to process a single row"""
    try:
        # Check if row is visible, if not scroll to it
        try:
            is_visible = row_locator.is_visible()
            if not is_visible:
                logger.debug(f"{row_type} {index} not visible, scrolling to it...")
                row_locator.scroll_into_view_if_needed()
                time.sleep(0.5)  # Brief wait for scroll to complete
        except Exception as e:
            logger.debug(f"Could not check visibility for {row_type} {index}, attempting scroll: {e}")
            try:
                row_locator.scroll_into_view_if_needed()
                time.sleep(0.5)
            except:
                pass
        
        # Extract cell data
        cells = row_locator.locator("td").all_text_contents()
        cleaned = tuple(c.replace("\xa0", "").strip() for c in cells)

        # Check if this row contains system error indicators
        row_text = " ".join(cleaned)
        if "Error" in row_text and ("Reference" in row_text or "encountered" in row_text or "occurred" in row_text):
            logger.warning(f"Detected system error text in row data: {row_text}")
            raise KRAITaxSystemError(row_text[:500])

        if cleaned and cleaned not in seen:
            # --- 🔍 DATA VALIDATION FILTER ---
            # A valid data row should have:
            # 1. At least 8-10 columns
            # 2. Sr.No. should be a digit
            # 3. Withholder PIN should look like a PIN (e.g., starts with P or A)
            
            if len(cleaned) < 8:
                logger.debug(f"Skipping row with too few columns: {len(cleaned)}")
                return

            sr_no = cleaned[0]
            pin = cleaned[1] if len(cleaned) > 1 else ""
            
            # Simple heuristic: Sr.No should be numeric and PIN should not be empty
            if not sr_no.isdigit():
                logger.debug(f"Skipping row with non-numeric Sr.No: {sr_no}")
                return
            
            # If PIN is empty or contains "Reprint" or "Setup", it's likely menu junk
            if not pin or any(x in pin for x in [">>", "Reprint", "setup", "Calendar"]):
                logger.debug(f"Skipping junk row (PIN: {pin})")
                return

            seen.add(cleaned)
            row_data = list(cleaned)
            data.append(row_data)
            logger.info(f"{row_type} {len(data)} extracted: {row_data}")
        elif cleaned in seen:
            logger.debug(f"{row_type} {index} is duplicate, skipping")
        elif not cleaned:
            logger.warning(f"{row_type} {index} has no cell data")
            
    except Exception as e:
        logger.warning(f"Error processing {row_type} {index}: {e}")
        raise

def check_for_system_errors(page: Page):
    """Checks the page for KRA iTax system errors using content and indicators."""
    content = page.content()
    error_keywords = [
        "An Error has occurred",
        "Error Occurred",
        "Problem encountered in iTax",
        "Your Error Reference No. is"
    ]
    
    system_error_detected = False
    for kw in error_keywords:
        if kw in content:
            system_error_detected = True
            break
    
    if system_error_detected:
        # Extract error details
        error_details_list = []
        selectors = ["div.error", "div.errormsg", ".errorMessage", "#errorMsg", "table.pagebody"]
        for selector in selectors:
            try:
                elements = page.locator(selector).all_inner_texts()
                for text in elements:
                    if text.strip() and ("Error" in text or "Reference" in text):
                        error_details_list.append(text.strip())
            except:
                pass
        
        error_details = " | ".join(sorted(list(set(error_details_list))))
        if not error_details:
            error_details = "iTax System Error detected (content check)"
        
        logger.error(f"KRA iTax System Error Detected: {error_details}")
        raise KRAITaxSystemError(error_details)
