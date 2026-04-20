"""
Setup verification script for KRA Automation
This script checks if all dependencies and configurations are properly set up.
"""
import sys
import os

def check_python_version():
    """Check Python version"""
    print(f"[OK] Python version: {sys.version}")
    return True

def check_imports():
    """Check if all required packages are installed"""
    print("\nChecking required packages...")
    packages = {
        'playwright': 'playwright',
        'dotenv': 'python-dotenv',
        'pytesseract': 'pytesseract',
        'PIL': 'Pillow'
    }
    
    all_ok = True
    for module, package in packages.items():
        try:
            __import__(module)
            print(f"  [OK] {package} installed")
        except ImportError:
            print(f"  [FAIL] {package} NOT installed - Run: pip install {package}")
            all_ok = False
    
    return all_ok

def check_tesseract():
    """Check if Tesseract OCR is installed"""
    print("\nChecking Tesseract OCR...")
    default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(default_path):
        print(f"  [OK] Tesseract found at: {default_path}")
        return True
    else:
        print(f"  [FAIL] Tesseract NOT found at: {default_path}")
        print("  Please install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki")
        return False

def check_env_file():
    """Check if .env file exists and has required variables"""
    print("\nChecking .env file...")
    env_path = ".env"
    
    if not os.path.exists(env_path):
        print(f"  [FAIL] .env file NOT found")
        print("\n  Please create a .env file with the following content:")
        print("  KRA_PIN=your_pin_here")
        print("  KRA_PASSWORD=your_password_here")
        return False
    
    print(f"  [OK] .env file exists")
    
    # Try to load and check variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        pin = os.getenv("KRA_PIN", "")
        password = os.getenv("KRA_PASSWORD", "")
        
        if not pin or pin == "your_pin_here":
            print("  [FAIL] KRA_PIN not set or using placeholder")
            return False
        else:
            print(f"  [OK] KRA_PIN is set (length: {len(pin)})")
        
        if not password or password == "your_password_here":
            print("  [FAIL] KRA_PASSWORD not set or using placeholder")
            return False
        else:
            print(f"  [OK] KRA_PASSWORD is set (length: {len(password)})")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Error reading .env file: {e}")
        return False

def check_playwright_browsers():
    """Check if Playwright browsers are installed"""
    print("\nChecking Playwright browsers...")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                print("  [OK] Chromium browser is installed")
                return True
            except Exception as e:
                print(f"  [FAIL] Chromium browser NOT installed - Run: python -m playwright install chromium")
                print(f"    Error: {e}")
                return False
    except Exception as e:
        print(f"  [FAIL] Error checking Playwright: {e}")
        return False

def main():
    print("=" * 60)
    print("KRA Automation Setup Verification")
    print("=" * 60)
    
    results = []
    results.append(("Python Version", check_python_version()))
    results.append(("Python Packages", check_imports()))
    results.append(("Tesseract OCR", check_tesseract()))
    results.append(("Playwright Browsers", check_playwright_browsers()))
    results.append(("Environment File", check_env_file()))
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} - {name}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] All checks passed! You can run main.py now.")
    else:
        print("[ERROR] Some checks failed. Please fix the issues above.")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())

