# KRA Automation Setup and Debugging Guide

## Current Status

✅ **All dependencies are installed:**
- Python 3.11.5
- playwright
- python-dotenv
- pytesseract
- Pillow (PIL)
- Tesseract OCR (installed at default path)

✅ **Playwright browsers installed:**
- Chromium browser is ready

❌ **Missing Configuration:**
- `.env` file with credentials is required

## Setup Instructions

### Step 1: Create .env File

Create a file named `.env` in the project root directory with the following content:

```
KRA_PIN=your_actual_pin_here
KRA_PASSWORD=your_actual_password_here
```

**Important:** Replace `your_actual_pin_here` and `your_actual_password_here` with your real KRA credentials.

### Step 2: Verify Setup

Run the setup verification script:

```bash
python test_setup.py
```

This will check all dependencies and configuration.

### Step 3: Run the Automation

Once the `.env` file is created with valid credentials, run:

```bash
python main.py
```

## Bugs Fixed

### 1. Logic Error in Page Validation (Fixed)
- **File:** `login.py` line 41
- **Issue:** Used `and` instead of `or` for page validation
- **Fix:** Changed to properly validate that either the page title contains "KRA" OR the PIN input is visible

### 2. Captcha Refresh Flow (Fixed)
- **File:** `login.py` `_refresh_captcha()` method
- **Issue:** After page reload, only password was re-entered, but PIN was missing
- **Fix:** Now properly re-enters both PIN and password after reload

## Debugging Tips

### Common Issues:

1. **Missing .env file:**
   - Error: `Missing required configuration: KRA_PIN, KRA_PASSWORD`
   - Solution: Create `.env` file with your credentials

2. **Tesseract not found:**
   - Error: `TesseractNotFoundError`
   - Solution: Install Tesseract OCR or set `TESSERACT_PATH` in `.env`

3. **Playwright browser not installed:**
   - Error: `Executable doesn't exist`
   - Solution: Run `python -m playwright install chromium`

4. **Network/Timeout issues:**
   - Error: `TimeoutError` or `Navigation timeout`
   - Solution: Check internet connection, increase timeout in `config.py`, or check if KRA website is accessible

5. **Captcha solving failures:**
   - The script retries up to 5 times automatically
   - If all attempts fail, check Tesseract OCR installation and image quality

## Testing the Setup

Run the verification script to check everything:

```bash
python test_setup.py
```

All checks should show `[PASS]` before running the main script.

## Project Structure

- `main.py` - Main entry point
- `config.py` - Configuration management
- `browser.py` - Browser management
- `login.py` - Login page automation
- `captcha_solver.py` - CAPTCHA solving using OCR
- `test_setup.py` - Setup verification script

## Next Steps

1. Create `.env` file with your credentials
2. Run `python test_setup.py` to verify setup
3. Run `python main.py` to start automation
4. Monitor the logs for any issues

