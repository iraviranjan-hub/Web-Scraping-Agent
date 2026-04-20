import os
import time
import re
from datetime import datetime, timedelta

import json
import pyautogui
import pygetwindow as gw
import pytesseract
from PIL import Image

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from sql_server_saver import save_to_sql_server

# =========================================================
# CONFIGURATION
# =========================================================
KRA_URL = "https://itax.kra.go.ke/KRA-Portal/"
KRA_PIN = os.getenv("KRA_PIN", "P000605583D")
KRA_PASSWORD = os.getenv("KRA_PASSWORD", "Smart2025")

SAVE_DIR = r"D:\PROJECTS\SMART_PRINTERS\KRA_Captcha"
TEMP_IMAGE = "temp_capture.png"
JSON_PATH = r"D:\PROJECTS\SMART_PRINTERS\vat_withholding.json"

MAX_CAPTCHA_RETRIES = 5
MAX_PROCESS_RESTARTS = 3

TARGET_WINDOW_TITLE = "Chrome"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

CAPTCHA_REGION = (456, 624, 220, 112)

# =========================================================
# CAPTCHA (UNCHANGED)
# =========================================================
def activate_target_window():
    for win in gw.getAllWindows():
        if TARGET_WINDOW_TITLE.lower() in win.title.lower():
            try:
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(1)
                return True
            except:
                pass
    return False

def capture_captcha():
    os.makedirs(SAVE_DIR, exist_ok=True)
    path = os.path.join(SAVE_DIR, TEMP_IMAGE)
    pyautogui.screenshot(region=CAPTCHA_REGION).save(path)
    return path

def extract_text_from_image(image_path):
    img = Image.open(image_path).convert("L")
    img = img.resize((img.width * 2, img.height * 2))
    img = img.point(lambda x: 0 if x < 140 else 255, "1")
    return pytesseract.image_to_string(
        img,
        config="--psm 7 -c tessedit_char_whitelist=0123456789+-*/?"
    ).strip()

def solve_expression(text):
    m = re.search(r"(\d+)([+\-*/xX])(\d+)", text.replace(" ", ""))
    if not m:
        return None
    a, op, b = m.groups()
    a, b = int(a), int(b)
    if op == "+": return a + b
    if op == "-": return a - b
    if op in ("*", "x", "X"): return a * b
    if op == "/" and b != 0: return a // b
    return None

def auto_solve_captcha():
    activate_target_window()
    time.sleep(2)
    text = extract_text_from_image(capture_captcha())
    print(f"[OCR RAW]: {text}")
    result = solve_expression(text)
    return result if result is not None and result >= 0 else None

# =========================================================
# LOGIN
# =========================================================
def login(page):
    page.goto(KRA_URL, timeout=60000)
    page.fill("#logid", KRA_PIN)
    page.click("text=Continue")
    page.fill("input[type='password']", KRA_PASSWORD)

    for attempt in range(1, MAX_CAPTCHA_RETRIES + 1):
        print(f"[CAPTCHA] Attempt {attempt}")

        captcha = auto_solve_captcha()
        if captcha is None:
            page.reload()
            continue

        page.fill("#captcahText", str(captcha))
        page.click("#loginButton")

        try:
            page.wait_for_selector("a.mainMenu[rel='Certificates']", timeout=15000)
            print("LOGIN SUCCESSFUL\n")
            return
        except PlaywrightTimeoutError:
            print("CAPTCHA FAILED – RETRYING\n")
            page.reload()
            time.sleep(3)

    raise Exception("Login failed due to CAPTCHA")

# =========================================================
# NAVIGATION
# =========================================================
def open_certificate_page(page):
    cert = page.locator("a.mainMenu[rel='Certificates']")
    cert.wait_for(timeout=20000)

    box = cert.bounding_box()
    page.mouse.move(
        box["x"] + box["width"] / 2,
        box["y"] + box["height"] / 2,
        steps=20
    )
    time.sleep(1.5)

    page.locator("text=Reprint Rental Income Withholding Certificate").click()
    page.wait_for_load_state("networkidle")

# =========================================================
# CONSULT
# =========================================================
def consult(page, pin):
    y = datetime.now() - timedelta(days=1)

    page.fill("#txtwithHoldeePin", pin)
  #  page.select_option("#mnth", value=str(y.month))
#  page.select_option("#year", value=str(y.year))
    page.fill("#dtOfCert", y.strftime("%d/%m/%Y"))

    page.once("dialog", lambda d: d.accept())
    page.click("#submitBtn")

    page.wait_for_selector("table", state="attached", timeout=20000)



# =========================================================
# TABLE SCRAPING (ONLY EvenRow & oddRow – NO SCROLLING)
# =========================================================
def extract_table(page):
    print("STARTING TABLE SCRAPING\n")

    page.wait_for_selector("table", state="attached", timeout=30000)

    total_records = (
        page.locator("text=Total Records")
        .inner_text()
        .split(":")[-1]
        .strip()
    )

    total_amount = page.locator(
        "//td[normalize-space()='Total VAT Withholding Amount']/following-sibling::td[1]"
    ).text_content().strip()


    time.sleep(10)

    header_row = page.locator("table tr").nth(0)
    headers = [h.strip() for h in header_row.locator("th").all_text_contents()]
    headers += ["Total Records", "Total VAT Withholding Amount"]

    print(headers)

    print("HEADERS:")
    for h in headers:
        print("   ", h)
    print("-" * 100)

    seen = set()
    data = []

    # 🔥 ONLY DATA ROWS (NO SCROLLING)
    rows = page.locator("tr.EvenRow, tr.oddRow")
    visible = rows.count()

    print(f"Total data rows detected: {visible}")

    for i in range(visible):
        cells = rows.nth(i).locator("td").all_text_contents()
        cleaned = tuple(c.replace("\xa0", "").strip() for c in cells)

        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            row_data = list(cleaned) + [total_records, total_amount]
            data.append(row_data)
            print(f"ROW {len(data)} → {row_data}")

    if not data:
        raise Exception("❌ NO DATA SCRAPED")

    print(f"\nTOTAL ROWS SCRAPED: {len(data)}\n")
    return headers, data


# =========================================================
# RUN ONCE
# =========================================================
def run_once(p):
    browser = p.chromium.launch(
        headless=True,
        args=["--start-maximized"]
    )
    context = browser.new_context(viewport=None)
    page = context.new_page()

    try:
        login(page)
        open_certificate_page(page)
        consult(page, KRA_PIN)
        headers, data = extract_table(page)
        
        # --- 🗄️ DATABASE SAVER ---
        print("🗄️ SAVING TO DATABASE...")
        try:
            rows_inserted = save_to_sql_server(headers, data)
            print(f"✅ SUCCESSFULLY SAVED {rows_inserted} ROWS TO DATABASE")
        except Exception as db_err:
            print(f"⚠️ Database Save encountered an error: {db_err}")

        # Add JSON output
        json_data = []
        for idx, row in enumerate(data, start=1):
            item = {}
            for i, h in enumerate(headers):
                if h in ["Sr.No.", "Sr. No.", "Sr No", "Serial No"]:
                    item[h] = str(idx)
                else:
                    item[h] = row[i] if i < len(row) else ""
            json_data.append(item)
        
        print("\n--- JSON OUTPUT ---")
        print(json.dumps(json_data, indent=4))
        print("-------------------\n")
        
        with open(JSON_PATH, "w") as f:
            json.dump(json_data, f, indent=4)
        print(f"JSON SAVED -> {JSON_PATH}\n")

    finally:
        browser.close()

# =========================================================
# MAIN
# =========================================================
def main():
    with sync_playwright() as p:
        for attempt in range(1, MAX_PROCESS_RESTARTS + 1):
            print(f"\n🔄 PROCESS ATTEMPT {attempt}\n")
            try:
                run_once(p)
                print("🎉 PROCESS COMPLETED SUCCESSFULLY")
                return
            except Exception as e:
                print("❌ ERROR:", e)
                print("♻ RETRYING PROCESS...\n")

        print("⛔ MAX RETRIES REACHED")

# =========================================================
if __name__ == "__main__":
    main()
