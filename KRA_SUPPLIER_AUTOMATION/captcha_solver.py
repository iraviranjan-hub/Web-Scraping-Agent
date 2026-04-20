import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
import io
import logging
from config import Config

# Configure Tesseract Path once
pytesseract.pytesseract.tesseract_cmd = Config.TESSERACT_PATH

logger = logging.getLogger(__name__)

class CaptchaSolver:
    """
    Handles Captcha image processing and solution extraction.
    Uses Tesseract OCR + Regex to solve arithmetic captchas.
    """

    @staticmethod
    def preprocess_image(image_bytes: bytes) -> Image.Image:
        """
        Applies image processing techniques to improve OCR accuracy.
        - Grayscale
        - Resizing (2x)
        - Thresholding
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img = img.convert("L")  # Convert to grayscale
            
            # Resize for better clarity (2x)
            img = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
            
            # Apply thresholding to binaraize the image (remove noise)
            # Pixels < 140 become 0 (black), others 255 (white)
            img = img.point(lambda x: 0 if x < 140 else 255, "1")
            
            return img
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            raise

    @staticmethod
    def solve(image_bytes: bytes) -> str:
        """
        Main method to solve the captcha from raw bytes.
        Returns the calculated result as a string.
        """
        try:
            # 1. Preprocess
            processed_img = CaptchaSolver.preprocess_image(image_bytes)
            
            # 2. OCR Extraction
            # Whitelist specific chars for arithmetic: digits, +, -, *, /, ?
            custom_config = r'--psm 7 -c tessedit_char_whitelist=0123456789+-*/?' 
            text = pytesseract.image_to_string(processed_img, config=custom_config).strip()
            
            logger.debug(f"Raw OCR Output: '{text}'")
            
            # 3. Clean and Validate
            return CaptchaSolver._evaluate_expression(text)
            
        except Exception as e:
            logger.error(f"Captcha solving failed: {e}")
            return None

    @staticmethod
    def _evaluate_expression(text: str) -> str:
        """
        Parses and safely evaluates a simple arithmetic expression.
        Supported formats: "10 + 5", "50 - 2", "5 * 5"
        """
        if not text:
            return None
            
        # Remove spaces and noise
        cleaned = text.replace(" ", "").replace("?", "")
        
        # Regex to find: Number - Operator - Number
        # Supports +, -, *, x, X, /
        match = re.search(r"(\d+)([+\-*/xX])(\d+)", cleaned)
        
        if not match:
            logger.warning(f"Could not find valid arithmetic expression in: {text}")
            return None
            
        a_str, op, b_str = match.groups()
        a, b = int(a_str), int(b_str)
        
        result = None
        if op == '+':
            result = a + b
        elif op == '-':
            result = a - b
        elif op in ('*', 'x', 'X'):
            result = a * b
        elif op == '/':
            if b == 0:
                logger.error("Division by zero in captcha.")
                return None
            result = a // b
            
        logger.info(f"Solved Captcha: {a} {op} {b} = {result}")
        return str(result)
