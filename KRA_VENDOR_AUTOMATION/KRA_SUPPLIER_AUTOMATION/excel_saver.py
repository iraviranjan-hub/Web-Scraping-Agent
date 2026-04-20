import pandas as pd
import logging
import os
from config import Config
from datetime import datetime

logger = logging.getLogger(__name__)

# =========================================================
# SAVE EXCEL
# =========================================================
def save_excel(headers, data, file_path=None):
    """
    Saves scraped table data to an Excel file.
    
    Args:
        headers: List of column headers
        data: List of data rows (each row is a list)
        file_path: Optional custom file path. If not provided, uses Config.EXCEL_PATH
    
    Returns:
        str: Path to the saved Excel file
    """
    try:
        # Fixed header sequence (fallback if headers are empty)
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
        
        # Validate inputs and use fixed headers as fallback
        if not headers or not isinstance(headers, list) or len(headers) == 0:
            logger.warning("Headers are empty or invalid, using fixed headers")
            headers = fixed_headers
        
        if not data or not isinstance(data, list):
            raise ValueError("Data must be a non-empty list")
        if len(data) > 0 and not isinstance(data[0], (list, tuple)):
            raise ValueError("Data rows must be lists or tuples")
        
        # Use provided path or default from config
        if file_path is None:
            file_path = Config.EXCEL_PATH
        
        # Create directory if it doesn't exist
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Created directory: {directory}")
        
        # Validate that headers match data columns
        if data and len(data) > 0:
            expected_cols = len(data[0])
            actual_header_count = len(headers)
            
            logger.debug(f"Header count: {actual_header_count}, Data columns per row: {expected_cols}")
            
            if actual_header_count != expected_cols:
                logger.warning(f"Header count ({actual_header_count}) doesn't match data column count ({expected_cols})")
                
                if actual_header_count < expected_cols:
                    # Add missing column names
                    missing = expected_cols - actual_header_count
                    # Check if summary columns are missing
                    summary_columns = ["Total Records", "Total VAT Withholding Amount"]
                    missing_summary = [col for col in summary_columns if col not in headers]
                    
                    if missing_summary and len(missing_summary) <= missing:
                        # Add missing summary columns first
                        headers = headers + missing_summary
                        missing = missing - len(missing_summary)
                    
                    # Add generic column names for remaining missing columns
                    if missing > 0:
                        headers = headers + [f"Column_{i+1}" for i in range(missing)]
                    
                    logger.warning(f"Fixed header mismatch. Added {expected_cols - actual_header_count} missing headers")
                elif actual_header_count > expected_cols:
                    # Trim excess headers (keep summary columns if they exist)
                    summary_columns = ["Total Records", "Total VAT Withholding Amount"]
                    summary_in_headers = [col for col in summary_columns if col in headers]
                    other_headers = [col for col in headers if col not in summary_columns]
                    
                    # Keep other headers up to expected count, then add summary
                    keep_count = expected_cols - len(summary_in_headers)
                    headers = other_headers[:keep_count] + summary_in_headers
                    logger.warning(f"Trimmed headers to match data column count")
        
        # Fixed header sequence (exact 10 headers in order)
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
        
        # Remove any summary columns from headers if present
        summary_columns = ["Total Records", "Total VAT Withholding Amount"]
        cleaned_headers = [h for h in headers if h not in summary_columns]
        
        # Use fixed headers if count matches, otherwise use cleaned headers
        if len(cleaned_headers) == len(fixed_headers):
            final_headers = fixed_headers
            logger.info("Using fixed header sequence")
        else:
            # Use cleaned headers but ensure they match expected count
            if len(cleaned_headers) == len(data[0]) if data else 0:
                final_headers = cleaned_headers
                logger.info(f"Using cleaned headers from table ({len(cleaned_headers)} columns)")
            else:
                # Fallback: use fixed headers and adjust data if needed
                final_headers = fixed_headers
                logger.warning(f"Header count mismatch. Using fixed headers. Expected {len(fixed_headers)}, got {len(cleaned_headers)}")
        
        # Process data: Remove summary columns if present
        processed_data = []
        for row in data:
            # Remove last 2 columns if they are summary columns (total_records, total_amount)
            if len(row) > len(final_headers):
                # Trim excess columns (assuming last 2 are summary)
                processed_row = row[:len(final_headers)]
            elif len(row) < len(final_headers):
                # Add empty values if row is shorter
                processed_row = list(row) + [""] * (len(final_headers) - len(row))
            else:
                processed_row = list(row)
            processed_data.append(processed_row)
        
        logger.info(f"Processed data: {len(processed_data)} rows, {len(final_headers)} columns")
        logger.info("=" * 80)
        logger.info("Excel Header Sequence (in order):")
        for idx, header in enumerate(final_headers, 1):
            logger.info(f"  {idx:2d}. {header}")
        logger.info("=" * 80)
        
        # Create DataFrame with proper column order
        df = pd.DataFrame(processed_data, columns=final_headers)
        
        logger.debug(f"Final column order: {list(df.columns)}")
        
        # Save to Excel
        logger.info(f"Saving data to Excel file: {file_path}")
        df.to_excel(file_path, index=False, engine='openpyxl')
        
        # Verify file was created
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            logger.info(f"Data saved successfully to: {file_path}")
            logger.info(f"File size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
            logger.info(f"Total rows saved: {len(data)}")
            return file_path
        else:
            raise Exception(f"Excel file was not created at: {file_path}")
            
    except ImportError as e:
        logger.error("pandas or openpyxl not installed. Install with: pip install pandas openpyxl")
        raise
    except Exception as e:
        logger.error(f"Error saving Excel file: {e}")
        raise


def save_excel_with_timestamp(headers, data, base_path=None, prefix="kra_data"):
    """
    Saves scraped table data to an Excel file with timestamp in filename.
    
    Args:
        headers: List of column headers
        data: List of data rows (each row is a list)
        base_path: Optional base directory path. If not provided, uses current directory
        prefix: Prefix for the filename (default: "kra_data")
    
    Returns:
        str: Path to the saved Excel file
    """
    try:
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.xlsx"
        
        if base_path:
            file_path = os.path.join(base_path, filename)
        else:
            file_path = filename
        
        logger.info(f"Saving with timestamped filename: {filename}")
        return save_excel(headers, data, file_path)
        
    except Exception as e:
        logger.error(f"Error saving Excel file with timestamp: {e}")
        raise

