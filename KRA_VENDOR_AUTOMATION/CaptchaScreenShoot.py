"""
=========================================================
Region Capture Utility (Foreground Window Only)
=========================================================
Author: Ravi Ranjan Kumar
Purpose:
 - Capture screen region from an already-open foreground window
 - Supports manual selection or fixed auto-capture
 - Designed for Chrome / TeamViewer / Secure portals
 - OCR and OpenCV compatible
=========================================================
"""

import tkinter as tk
import pyautogui
import pygetwindow as gw
import pytesseract
from pytesseract import Output
import os
import time
from datetime import datetime
import sys

# =========================================================
# CONFIGURATION
# =========================================================
SAVE_DIR = r"D:\PROJECTS\SMART_PRINTERS\KRA_Captcha"
TARGET_WINDOW_TITLE = "Chrome"  # or "TeamViewer"
TEMP_IMAGE = "temp_capture.png"

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# =========================================================
# OPTIONAL EXTRACTION MODULE
# =========================================================
try:
    from scrape_active_window import extract_table_with_opencv
except Exception:
    extract_table_with_opencv = None


# =========================================================
# FOREGROUND WINDOW HANDLER
# =========================================================
def activate_target_window():
    """
    Activates the target foreground window (Chrome / TeamViewer)
    """
    print(f"[SEARCH] Looking for window: {TARGET_WINDOW_TITLE}")
    for win in gw.getAllWindows():
        if TARGET_WINDOW_TITLE.lower() in win.title.lower():
            try:
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(1)
                print(f"[OK] Activated window: {win.title}")
                return True
            except Exception as e:
                print(f"[WARN] Could not activate window: {e}")
    print("[ERROR] Target window not found.")
    return False


# =========================================================
# REGION CAPTURE UI
# =========================================================
class RegionCapture:
    def __init__(self, auto_target=None):
        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.25)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")

        self.start_x = self.start_y = None
        self.rect = None

        self.canvas = tk.Canvas(self.root, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        if auto_target:
            self.root.after(400, lambda: self.auto_capture(auto_target))
            print("[AUTO] Using predefined capture region.")
        else:
            print("🖱 Drag mouse to select capture area. Press ESC to cancel.")

        self.root.mainloop()

    # -----------------------------------------------------
    def auto_capture(self, region):
        x, y, w, h = region
        self.rect = self.canvas.create_rectangle(
            x, y, x + w, y + h, outline="red", width=3
        )
        self.root.update()
        time.sleep(0.5)
        self.root.destroy()
        save_and_process(x, y, w, h)

    # -----------------------------------------------------
    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="red", width=3
        )

    # -----------------------------------------------------
    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    # -----------------------------------------------------
    def on_release(self, event):
        end_x, end_y = event.x, event.y
        self.root.destroy()

        x = min(self.start_x, end_x)
        y = min(self.start_y, end_y)
        w = abs(end_x - self.start_x)
        h = abs(end_y - self.start_y)

        if w > 10 and h > 10:
            save_and_process(x, y, w, h)
        else:
            print("[CANCELLED] Selected area too small.")


# =========================================================
# SCREENSHOT + EXTRACTION
# =========================================================
def save_and_process(x, y, w, h):
    try:
        if not os.path.exists(SAVE_DIR):
            os.makedirs(SAVE_DIR)

        filepath = os.path.join(SAVE_DIR, TEMP_IMAGE)

        screenshot = pyautogui.screenshot(region=(x, y, w, h))
        screenshot.save(filepath)

        print(f"[OK] Screenshot saved: {filepath}")

        if extract_table_with_opencv:
            print("[INFO] Running OpenCV extraction...")
            success = extract_table_with_opencv(filepath)
            if success:
                print("[SUCCESS] Extraction completed.")
            else:
                print("[WARN] Extraction failed. Opening image.")
                os.startfile(filepath)
        else:
            os.startfile(filepath)

    except Exception as e:
        print(f"[ERROR] Capture failed: {e}")


# =========================================================
# OCR-BASED AUTO REGION DETECTION (OPTIONAL)
# =========================================================
def find_region_by_text():
    print("[OCR] Scanning screen...")
    img = pyautogui.screenshot()
    data = pytesseract.image_to_data(img, output_type=Output.DICT)

    for i, txt in enumerate(data["text"]):
        if txt.strip().upper() == "CAPTCHA":
            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i] + 120
            h = data["height"][i] + 20
            return (x, y, w, h)
    return None


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    activate_target_window()

    # 🔧 OPTION 1: Fixed region (captcha / table)
    FIXED_REGION = (526, 724, 220, 112)

    # 🔧 OPTION 2: OCR-based detection
    # FIXED_REGION = find_region_by_text()

    RegionCapture(auto_target=FIXED_REGION)
