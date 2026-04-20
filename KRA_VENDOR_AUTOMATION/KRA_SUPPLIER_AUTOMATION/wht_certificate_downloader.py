import re
import logging
import os
from pathlib import Path
from datetime import datetime
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
from playwright.sync_api import Page, TimeoutError

from config import Config

logger = logging.getLogger(__name__)

# =========================================================
# PDF TEXT EXTRACTION
# =========================================================
def extract_withholdee_name(pdf_path):
    """
    Extracts 'Name of Withholdee' from the PDF text.
    """
    if not fitz:
        logger.warning("fitz (PyMuPDF) not installed. Cannot extract PDF text.")
        return ""
    
    try:
        # Resolve to absolute path just in case
        abs_path = str(Path(pdf_path).absolute())
        if not os.path.exists(abs_path):
            logger.error(f"PDF file not found for extraction: {abs_path}")
            return ""

        doc = fitz.open(abs_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        
        # Normalize and clean text
        clean_text = " ".join(text.split())
        logger.debug(f"DEBUG - Full Normalized Text: {clean_text}")

        # Strategy 1: Regex with common KRA patterns
        patterns = [
            # Pattern for the structure found: "Name of Withholdee [NAME] Address of Withholdee"
            r"Name\s+of\s+Withholdee\s*[:\-]?\s*(.*?)\s+Address\s+of\s+Withholdee",
            # Standard colon pattern
            r"Name\s+of\s+Withholdee\s*[:\-]\s*(.*?)(?:\s{2,}|P\.O\.|\d{10}|PIN|Date|Amount|Collector|$)",
            # Just Name of Withholdee followed by name until next major field
            r"Name\s+of\s+Withholdee\s*(.*?)(?:\s{2,}|PIN|Address|Date|$)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match and match.group(1).strip() and len(match.group(1).strip()) > 2:
                extracted_name = match.group(1).strip()
                # Remove any junk like "PIN : ..." if caught
                extracted_name = re.split(r"PIN|P\.O\.|Date|Amount|:", extracted_name, flags=re.IGNORECASE)[0].strip()
                if extracted_name:
                    logger.info(f"SUCCESS - Extracted Name (Regex): {extracted_name}")
                    return extracted_name
        
        # Strategy 2: Direct split and search
        target_marker = "Name of Withholdee"
        if target_marker.lower() in clean_text.lower():
            start_idx = clean_text.lower().find(target_marker.lower()) + len(target_marker)
            sub_text = clean_text[start_idx:].strip()
            if sub_text.startswith(":") or sub_text.startswith("-"):
                sub_text = sub_text[1:].strip()
            
            # Extract until we hit a known footer/header keyword
            keywords = ["PIN", "P.O.", "Box", "Address", "Date", "Amount", "Certificate"]
            candidate = sub_text
            for kw in keywords:
                if kw in candidate:
                    candidate = candidate.split(kw)[0]
            
            candidate = candidate.strip()
            if len(candidate) > 2:
                logger.info(f"SUCCESS - Extracted Name (Split): {candidate}")
                return candidate

        # Strategy 3: Multi-line search (sometimes text extraction preserves newlines)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for i, line in enumerate(lines):
            if "Name of Withholdee" in line:
                # Check if name is on the same line
                if ":" in line:
                    val = line.split(":", 1)[1].strip()
                    if len(val) > 2:
                        logger.info(f"SUCCESS - Extracted Name (Same Line): {val}")
                        return val
                # Check next line
                if i + 1 < len(lines):
                    next_line = lines[i+1].strip()
                    if len(next_line) > 2 and ":" not in next_line:
                        logger.info(f"SUCCESS - Extracted Name (Next Line): {next_line}")
                        return next_line

        logger.warning(f"FAILURE - Could not extract withholdee name from {abs_path}")
        # Log the full text once to help the developer see the actual structure
        logger.debug(f"FULL PDF CONTENT FOR DEBUGGING:\n{text}\n" + "-"*50)
        
    except Exception as e:
        logger.error(f"Error extracting name from PDF {pdf_path}: {e}")
    return ""

# =========================================================
# DATE-WISE DOWNLOAD FUNCTION
# =========================================================
def download_wht_certificates(page: Page, headers, data, existing_info=None):
    """
    Downloads each WHT Certificate PDF into a folder named after the certificate's own date (Certificate Date from the KRA portal).
    Also updates the 'data' rows with the file path in the 'Attachment Path' column.
    If existing_paths is provided, it skips downloading if the certificate path is already known.
    """

    base_path = Path(Config.WHT_CERTIFICATE_BASE_PATH)
    
    if "Certificate Date" not in headers:
        logger.error("'Certificate Date' column not found in headers")
        return

    cert_date_col = headers.index("Certificate Date")
    
    if "WHT Certificate No" not in headers:
        logger.error("'WHT Certificate No' column not found in headers")
        return
    
    cert_no_col = headers.index("WHT Certificate No")
    
    # Ensure both "Attachment Path" and "Mapping Withholder Name" are in headers
    if "Attachment Path" not in headers:
        headers.append("Attachment Path")
    path_col_idx = headers.index("Attachment Path")
    
    if "Mapping Withholder Name" not in headers:
        headers.append("Mapping Withholder Name")
    mapping_col_idx = headers.index("Mapping Withholder Name")
    
    # Initialize columns for all rows if not present
    for row in data:
        while len(row) <= max(path_col_idx, mapping_col_idx):
            row.append("")
        
        # Pre-fill with existing path if available
        cert_no = str(row[cert_no_col]).strip()
        if existing_info and cert_no in existing_info:
            info = existing_info[cert_no]
            if info["path"]:
                row[path_col_idx] = info["path"]
                logger.debug(f"Using existing path for certificate {cert_no}: {info['path']}")
            
            if info["mapping"]:
                row[mapping_col_idx] = info["mapping"]
            elif info["path"] and Path(info["path"]).exists():
                # If path exists but mapping is missing, extract it now
                extracted_name = extract_withholdee_name(info["path"])
                if extracted_name:
                    row[mapping_col_idx] = extracted_name

    links = page.locator("a.textDecorationUnderline")
    total_links = links.count()

    if total_links == 0 or not data or len(data) < total_links:
        logger.warning(f"Link/data count mismatch or no certificates found (links: {total_links}, data rows: {len(data) if data else 0})")
        return

    logger.info(f"Found {total_links} WHT certificate(s)")

    for index in range(total_links):
        try:
            link = links.nth(index)
            certificate_no = link.inner_text().strip()
            
            # Find the correct row in data by certificate_no
            row = None
            for r in data:
                if str(r[cert_no_col]).strip() == certificate_no:
                    row = r
                    break
            
            if not row:
                logger.warning(f"Could not find matching data row for certificate {certificate_no} in current batch.")
                continue

            # Skip if already have both path and mapping
            if row[path_col_idx] and row[mapping_col_idx]:
                logger.info(f"Skipping download/extraction for certificate {certificate_no} as path and mapping already exist.")
                continue
            
            # If we have path but not mapping, extract and continue
            if row[path_col_idx] and not row[mapping_col_idx]:
                if Path(row[path_col_idx]).exists():
                    logger.info(f"Path exists for {certificate_no}, extracting name only.")
                    extracted_name = extract_withholdee_name(row[path_col_idx])
                    if extracted_name:
                        row[mapping_col_idx] = extracted_name
                    continue

            onclick_value = link.get_attribute("onclick")

            if not onclick_value:
                logger.warning(f"Missing onclick for certificate {certificate_no}")
                continue

            match = re.search(r"openPDFHdrId\('(\d+)'\)", onclick_value)
            if not match:
                logger.warning(f"Could not extract HdrId for {certificate_no}")
                continue

            hdr_id = match.group(1)
            logger.info(f"Triggering download for certificate {certificate_no} (HdrId: {hdr_id}) at index {index}...")

            # Small delay to ensure the page is ready and avoid rapid-fire blocks in headless mode
            page.wait_for_timeout(1500)

            with page.expect_download(timeout=60000) as download_info:
                # Scroll to the link to ensure it's in the viewport
                link.scroll_into_view_if_needed()
                page.evaluate(f"openPDFHdrId('{hdr_id}')")

            download = download_info.value

            safe_name = certificate_no.replace("/", "_").replace("\\", "_")
            # Get and format certificate date
            cert_date_raw = row[cert_date_col]
            try:
                cert_date = datetime.strptime(cert_date_raw, "%d/%m/%Y").strftime("%Y-%m-%d")
            except Exception as e:
                logger.warning(f"Invalid certificate date '{cert_date_raw}' for cert {certificate_no}, using RAW format as folder. Error: {e}")
                cert_date = cert_date_raw.replace("/", "-")
            
            cert_download_dir = base_path / cert_date
            cert_download_dir.mkdir(parents=True, exist_ok=True)

            file_path = cert_download_dir / f"{safe_name}.pdf"

            download.save_as(file_path)
            logger.info(f"✓ Downloaded: {file_path}")
            
            # Close any popups opened by the openPDFHdrId call to keep browser clean
            for p in page.context.pages:
                if p != page:
                    try:
                        p.close()
                    except:
                        pass

            # Update the row with the absolute file path
            row[path_col_idx] = str(file_path.absolute())

            # Extract Name and update the row
            extracted_name = extract_withholdee_name(file_path)
            if extracted_name:
                row[mapping_col_idx] = extracted_name
                logger.info(f"Successfully mapped withholdee: {extracted_name}")
            else:
                logger.warning(f"Could not extract withholdee name for {certificate_no}")
                row[mapping_col_idx] = "Not Found" # Fill with a placeholder so we know it tried

        except TimeoutError:
            logger.error(f"Timeout downloading certificate at index {index} (Cert: {certificate_no if 'certificate_no' in locals() else 'Unknown'})")
            # Clear popups even on timeout
            for p in page.context.pages:
                if p != page:
                    try: p.close()
                    except: pass
        except Exception as e:
            logger.error(f"Error downloading certificate at index {index}: {e}")
            # Clear popups even on error
            for p in page.context.pages:
                if p != page:
                    try: p.close()
                    except: pass

    logger.info(f"Completed WHT certificate downloads for all Certificate Dates.")
