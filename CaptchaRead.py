from PIL import Image
import pytesseract
import re

# Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text_from_image(image_path):
    try:
        img = Image.open(image_path)
        img = img.convert("L")  # grayscale

        text = pytesseract.image_to_string(
            img,
            config="--psm 7 -c tessedit_char_whitelist=0123456789+-*/?"
        )

        return text.strip()

    except Exception as e:
        print("OCR Error:", e)
        return None


def clean_and_solve_expression(extracted_text):
    if not extracted_text:
        print("Empty OCR output")
        return None

    print("Raw OCR:", extracted_text)

    # Normalize text
    text = extracted_text.replace("?", "").replace(" ", "")
    print("Normalized Text:", text)

    # Extract math expression (IMPORTANT FIX)
    match = re.search(r"(\d+)([+\-*/])(\d+)", text)

    if not match:
        print("No valid expression found")
        return None

    num1, operator, num2 = match.groups()
    num1, num2 = int(num1), int(num2)

    print(f"Expression Found: {num1} {operator} {num2}")

    # Safe calculation (NO eval)
    if operator == "+":
        return num1 + num2
    elif operator == "-":
        return num1 - num2
    elif operator == "*":
        return num1 * num2
    elif operator == "/":
        return num1 // num2 if num2 != 0 else None


def process_image(image_path):
    extracted_text = extract_text_from_image(image_path)
    return clean_and_solve_expression(extracted_text)


# --------------------
# Example usage
# --------------------
if __name__ == "__main__":
    image_path = r"D:\PROJECTS\SMART_PRINTERS\KRA_Captcha\temp_capture.png"

    result = process_image(image_path)

    if result is not None:
        print("✅ Result:", result)
    else:
        print("❌ Error or no result found.")
