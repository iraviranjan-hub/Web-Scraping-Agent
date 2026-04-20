from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime, timedelta
import os
import json
import logging
import asyncio
from typing import Optional

# Import the existing automation logic
from main import run_automation
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(
    title="KRA iTax Automation API",
    description="Pure API for KRA scraping. No frontend, just JSON.",
    version="1.0.0"
)

# @app.get("/")
# async def root():
#     return {
#         "message": "KRA iTax Automation API is active.",
#         "endpoints": {
#             "/Kra_Vendor_scrape": "GET/POST - Run automation and get JSON result",
#             "/last_data": "GET - Get the last successfully scraped data"
#         }
#     }

# @app.get("/Kra_Vendor_scrape")
# async def scrape_get(
#     pin: str = Query(..., description="KRA PIN"),
#     password: str = Query(..., description="KRA Password"),
#     start_date: str = Query(None, description="Start date in YYYY-MM-DD format. Defaults to yesterday."),
#     timeout: int = Query(10, description="Timeout in seconds for total process execution"),
#     api_key: str = Header(None, alias="X-API-Key")
# ):


@app.get("/")
async def root():
    return {
        "message": "KRA iTax Automation API is active.",
        "endpoints": {
            "/scrape": "GET/POST - Run automation and get JSON result",
            "/Kra_Vendor_scrape": "GET/POST - Run vendor scraping automation and get JSON result",
            "/last_data": "GET - Get the last successfully scraped data"
        }
    }

@app.get("/scrape")
def scrape_get(
    pin: str = Query(..., description="KRA PIN"),
    password: str = Query(..., description="KRA Password"),
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format. Defaults to yesterday."),
    api_key: str = Header(None, alias="X-API-Key")
):


    """
    Run automation via GET request with query parameters.
    """
   # return await run_process_with_timeout(pin, password, start_date, api_key)
    return run_process(pin, password, start_date, api_key)
  
# @app.post("/Kra_Vendor_scrape")
# async def scrape_post(
#     data: dict,
#     #timeout: int = Query(120, description="Timeout in seconds for total process execution"),
#     api_key: str = Header(None, alias="X-API-Key")
# ):



@app.post("/scrape")
def scrape_post(
    data: dict,
    api_key: str = Header(None, alias="X-API-Key")
):
    """
    Run automation via POST request with JSON body.
    Expects: {"pin": "...", "password": "...", "start_date": "YYYY-MM-DD" (optional)}
    """
    pin = data.get("pin")
    password = data.get("password")
    start_date = data.get("start_date")
    
    if not pin or not password:
        raise HTTPException(status_code=400, detail="pin and password are required")
        
    #return await run_process(pin, password, start_date, api_key)
    return run_process(pin, password, start_date, api_key)





@app.get("/Kra_Vendor_scrape")
def kra_vendor_scrape_get(
    pin: str = Query(..., description="KRA PIN"),
    password: str = Query(..., description="KRA Password"),
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format. Defaults to yesterday."),
    api_key: str = Header(None, alias="X-API-Key")
):
    """
    Run vendor scraping automation via GET request with query parameters.
    Example: /Kra_Vendor_scrape?pin=P000605583d&password=Smart2025&start_date=2026-03-30
    """
    return run_process(pin, password, start_date, api_key)

@app.post("/Kra_Vendor_scrape")
def kra_vendor_scrape_post(
    data: dict,
    api_key: str = Header(None, alias="X-API-Key")
):
    """
    Run vendor scraping automation via POST request with JSON body.
    Expects: {"pin": "...", "password": "...", "start_date": "YYYY-MM-DD" (optional)}
    """
    pin = data.get("pin")
    password = data.get("password")
    start_date = data.get("start_date")
    
    if not pin or not password:
        raise HTTPException(status_code=400, detail="pin and password are required")
        
    return run_process(pin, password, start_date, api_key)




@app.get("/last_data")
async def get_last_data(api_key: str = Header(None, alias="X-API-Key")):
    """
    Returns the most recent data saved in the JSON file.
    """
    validate_key(api_key)
    
    if not os.path.exists(Config.JSON_PATH):
        return JSONResponse({"status": "error", "message": "No data found. Run scraping first."}, status_code=404)
        
    try:
        with open(Config.JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Error reading data: {str(e)}"}, status_code=500)

def validate_key(api_key: str):
    if api_key != Config.API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Key")

async def run_process_with_timeout(pin, password, start_date_str, api_key, timeout_seconds: int):
    """
    Wraps the automation process with a timeout to prevent 504 Gateway errors.
    If the process takes longer than timeout_seconds, it returns a 504 error response.
    """
    try:
        # Run the synchronous run_process in a separate thread to avoid blocking the event loop
        # and enforce the timeout using asyncio.wait_for
        return await asyncio.wait_for(
            asyncio.to_thread(run_process, pin, password, start_date_str, api_key),
            timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.error(f"Scraping operation timed out after {timeout_seconds} seconds for PIN: {pin}")
        return JSONResponse({
            "status": "error",
            "message": f"Operation timed out after {timeout_seconds} seconds. The process may still be running on the server. Please check /last_data later."
        }, status_code=504)

def run_process(pin, password, start_date_str, api_key):
    # validate_key(api_key) # Uncomment if you want to enforce security
    
    try:
        # Date processing
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        else:
            # Default to yesterday
            start_date = datetime.now() - timedelta(days=1)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
        # Target date is always yesterday
        end_date = datetime.now() - timedelta(days=1)
        end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if start_date > end_date:
            return JSONResponse({
                "status": "error", 
                "message": f"Start date ({start_date_str}) cannot be in the future (Target end date: {end_date.strftime('%Y-%m-%d')})"
            }, status_code=400)

        max_retries = Config.MAX_RUNTIME_RETRIES
        retry_delay = Config.RETRY_DELAY
        last_error = "Unknown error"

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Attempt {attempt}/{max_retries} for PIN: {pin}")
                # Run the automation synchronously
                result_data = run_automation(pin, password, start_date, end_date)
                
                return {
                    "status": "success",
                    "attempt": attempt,
                    "count": len(result_data) if result_data else 0,
                    "data": result_data if result_data else [],
                    "message": "Scraping completed" if result_data else "No records found"
                }
            except Exception as e:
                last_error = str(e)
                logger.error(f"Attempt {attempt} failed: {last_error}")
                if attempt < max_retries:
                    import time
                    time.sleep(retry_delay)
                else:
                    break

        return JSONResponse({
            "status": "error",
            "message": f"All {max_retries} attempts failed. Last error: {last_error}"
        }, status_code=500)
            
    except Exception as e:
        logger.error(f"Internal API Error: {str(e)}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

# if __name__ == "__main__":
#     print("\n" + "="*50)
#     print("KRA AUTOMATION PURE API STARTING")
#     print("Access at: http://localhost:8103")
#     print("Try: http://localhost:8103/Kra_Vendor_scrape?pin=YOUR_PIN&password=YOUR_PASS&start_date=yyyy-mm-dd")
#     print("="*50 + "\n")
#     uvicorn.run(app, host="0.0.0.0", port=8103)




if __name__ == "__main__":
    print("\n" + "="*70)
    print("KRA AUTOMATION PURE API STARTING")
    print(f"Access at: http://localhost:{Config.API_PORT}")
    print(f"\nAvailable Endpoints:")
    print(f"  - GET:  http://localhost:{Config.API_PORT}/scrape?pin=YOUR_PIN&password=YOUR_PASS&start_date=yyyy-mm-dd")
    print(f"  - GET:  http://localhost:{Config.API_PORT}/Kra_Vendor_scrape?pin=YOUR_PIN&password=YOUR_PASS&start_date=yyyy-mm-dd")
    print(f"\nAPI Documentation: http://localhost:{Config.API_PORT}/docs")
    print("="*70 + "\n")
    uvicorn.run(app, host=Config.API_HOST, port=Config.API_PORT)

