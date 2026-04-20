import logging
import sys
import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

from config import Config
from browser import BrowserManager
from login import LoginPage
from navigation import open_certificate_page, consult
from exceptions import KRAITaxSystemError
from table_scraper import extract_table
from excel_saver import save_excel
from json_saver import save_json, print_json_console, format_as_json
from sql_server_saver import save_to_sql_server, get_last_run_date, update_last_run_date
from email_sender import send_error_email

# Setup Logging
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format=Config.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        # logging.FileHandler("kra_automation.log") # Uncomment to log to file
    ]
)
logger = logging.getLogger(__name__)

def run_automation(kra_pin, kra_password, start_date, end_date):
    """
    Main workflow function.
    Returns True if completed successfully, raises Exception otherwise.
    """
    logger.info("Starting KRA iTax Automation Process...")
    
    # 1. Skip database and set current_date/end_date from input
    logger.info("=" * 80)
    logger.info("STEP 1: Setting run date range from input...")
    logger.info("=" * 80)
    
    # Commented out DB connection as requested
    # try:
    #     last_run_date = get_last_run_date()
    #     ...
    
    current_date = start_date
    logger.info(f"[OK] Running from: {current_date.strftime('%Y-%m-%d')} to: {end_date.strftime('%Y-%m-%d')}")

    # 2. Now start browser and automation
    logger.info("=" * 80)
    logger.info("STEP 2: Starting browser automation...")
    logger.info("=" * 80)
    
    with sync_playwright() as p:
        browser_manager = BrowserManager(p)
        
        try:
            # 3. Launch Browser
            page = browser_manager.launch()
            
            # 4. Initialize Login Page
            login_page = LoginPage(page)
            
            # 5. Execute Login Flow
            login_page.navigate()
            login_page.enter_pin(kra_pin)
            
            success = login_page.perform_secure_login(kra_password)
            
            if success:
                logger.info("[OK] Login completed successfully.")
                
                # 6. Navigate to Certificate Page
                logger.info("=" * 80)
                logger.info("STEP 3: Navigating to Certificate page...")
                logger.info("=" * 80)
                open_certificate_page(page)
                logger.info("[OK] Certificate page loaded successfully.")
                
                all_headers = None
                all_data_for_excel = []
                
                # 7. Scrape day by day in loop
                logger.info("=" * 80)
                logger.info("STEP 4: Starting day-by-day scraping loop...")
                logger.info("=" * 80)
                
                total_records_processed = 0
                while current_date <= end_date:
                    try:
                        logger.info("=" * 80)
                        logger.info(f"[DATE] Processing date: {current_date.strftime('%Y-%m-%d')}")
                        logger.info("=" * 80)
                        
                        consult_successful = consult(page, current_date, pin=kra_pin)
                        
                        rows_inserted = 0
                        if not consult_successful:
                            logger.info(f"[INFO] No records found for {current_date.strftime('%Y-%m-%d')}.")
                            # update_last_run_date(current_date, "no_records") # Commented out DB update
                            current_date += timedelta(days=1)
                            time.sleep(2)
                            continue
                        
                        # Extract Table Data
                        headers, data = extract_table(page)
                        if headers:
                            all_headers = headers
                        
                        if data and len(data) > 0:
                            all_data_for_excel.extend(data)
                            # rows_inserted = save_to_sql_server(headers, data) # Commented out SQL save
                            # logger.info(f"[OK] Data inserted into SQL Server: {rows_inserted} rows.")
                            # Show JSON output for the current day's data with sequential Sr.No.
                            print_json_console(format_as_json(headers, data, start_index=total_records_processed + 1))
                            total_records_processed += len(data)
                        else:
                            pass
                            # update_last_run_date(current_date, "no_data_extracted") # Commented out DB update
                        
                        # if rows_inserted > 0:
                        #     update_last_run_date(current_date, "processed") # Commented out DB update
                        
                        time.sleep(2)
                        
                    except Exception as date_error:
                        logger.error(f"[ERROR] Error scraping date {current_date.strftime('%Y-%m-%d')}: {date_error}")
                        # For minor date errors, we might want to continue or retry the whole thing.
                        # Re-raising here would cause a full process retry.
                        raise 
                    
                    current_date += timedelta(days=1)
                
                # 10. Save all collected data to Excel and JSON
                final_json_data = []
                if all_data_for_excel and len(all_data_for_excel) > 0:
                    # save_excel(all_headers, all_data_for_excel) # Commented out Excel save
                    save_json(all_headers, all_data_for_excel)
                    final_json_data = format_as_json(all_headers, all_data_for_excel)
                
                logger.info("[OK] Scraping process completed successfully!")
                return final_json_data
                
            else:
                logger.error("[ERROR] Failed to login after multiple attempts.")
                raise Exception("Login failed")
                
        except Exception as e:
            logger.exception("[ERROR] An unhandled error occurred.")
            raise  # Re-raise for retry logic
        finally:
            browser_manager.close()

if __name__ == "__main__":
    # Get runtime parameters
    print("\n" + "="*30)
    print(" KRA AUTOMATION PARAMETERS ")
    print("="*30)
    user_pin = input("Enter KRA PIN: ").strip()
    user_password = input("Enter KRA Password: ").strip()
    start_date_str = input("Enter Start Date (YYYY-MM-DD): ").strip()

    try:
        user_start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        # Targeted date is always yesterday (Today - 1 day)
        user_end_date = datetime.now() - timedelta(days=1)
        user_end_date = user_end_date.replace(hour=0, minute=0, second=0, microsecond=0)
    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DD for the Start Date.")
        sys.exit(1)

    max_retries = Config.MAX_RUNTIME_RETRIES
    retry_delay = Config.RETRY_DELAY
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"\n[START] RUN ATTEMPT {attempt}/{max_retries}")
            if run_automation(user_pin, user_password, user_start_date, user_end_date):
                logger.info("[SUCCESS] AUTOMATION COMPLETED SUCCESSFULLY!")
                break
        except KRAITaxSystemError as e:
            logger.critical(f"[KRA SYSTEM ERROR] {e}")
            send_error_email(str(e))
            logger.info("[STOP] Terminating process due to KRA system error.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"[FAIL] Attempt {attempt} failed with error: {e}")
            if attempt < max_retries:
                logger.info(f"[WAIT] Waiting {retry_delay} seconds before retrying...")
                time.sleep(retry_delay)
            else:
                logger.critical("[STOP] Maximum retries reached. Process failed.")
                sys.exit(1)
