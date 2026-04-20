import logging
import os
import pyodbc
from datetime import datetime, timedelta
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from Config.env
load_dotenv("Config.env")
load_dotenv()  # Fallback to .env if Config.env doesn't exist

logger = logging.getLogger(__name__)

# =========================================================
# SQL SERVER CONFIGURATION (from Config.env)
# =========================================================
SQL_SERVER_CONFIG = {
    "server": os.getenv("SQL_SERVER", ""),
    "username": os.getenv("SQL_USERNAME", ""),
    "password": os.getenv("SQL_PASSWORD", ""),
    "database": os.getenv("SQL_DATABASE", ""),
    "table_name": os.getenv("SQL_TABLE", "Kra_data"),
    "LAST_RUN_DATE_TABLE_NAME": os.getenv("LAST_RUN_DATE_TABLE_NAME","Last_update_Run_Date")
}

# =========================================================
# SQL SERVER CONNECTION
# =========================================================
def get_connection():
    """
    Creates and returns a SQL Server connection.
    
    Returns:
        pyodbc.Connection: Database connection object
    """
    try:
        connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={SQL_SERVER_CONFIG['server']};"
            f"DATABASE={SQL_SERVER_CONFIG['database']};"
            f"UID={SQL_SERVER_CONFIG['username']};"
            f"PWD={SQL_SERVER_CONFIG['password']}"
        )
        
        conn = pyodbc.connect(connection_string, timeout=30)
        logger.info(f"Successfully connected to SQL Server: {SQL_SERVER_CONFIG['server']}")
        return conn
    except pyodbc.Error as e:
        logger.error(f"Error connecting to SQL Server: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error connecting to SQL Server: {e}")
        raise
# =========================================================
# LAST RUN DATE MANAGEMENT
# =========================================================
def get_last_run_date():
    """
    Reads the last successfully processed date from SQL Server.
    Returns:
        datetime | None
    """
    try:
        validate_sql_config()
        conn = get_connection()

        try:
            cursor = conn.cursor()
            table_name = SQL_SERVER_CONFIG["LAST_RUN_DATE_TABLE_NAME"]

            # Check if table exists
            cursor.execute(
                """
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = ?
                """,
                table_name,
            )
            table_exists = cursor.fetchone()[0] > 0

            if not table_exists:
                logger.warning(f"{table_name} table does not exist. Creating it.")
                cursor.execute(
                    f"""
                    CREATE TABLE [dbo].[{table_name}] (
                        [Last_update_Run_Date] DATE NOT NULL,
                        [Status] VARCHAR(50) NULL
                    )
                    """
                )
                conn.commit()
                return None

            # Fetch latest run date safely
            cursor.execute(
                f"""
                SELECT TOP 1 Last_update_Run_Date
                FROM [dbo].[{table_name}]
                ORDER BY Last_update_Run_Date DESC
                """
            )

            row = cursor.fetchone()
            cursor.close()

            if not row or not row[0]:
                logger.info("No last run date found in database")
                return None

            last_date = row[0]

            # Normalize to datetime
            if isinstance(last_date, datetime):
                return last_date.replace(hour=0, minute=0, second=0, microsecond=0)

            if hasattr(last_date, "strftime"):  # date object
                return datetime.combine(last_date, datetime.min.time())

            logger.warning(f"Unexpected date type received: {type(last_date)}")
            return None

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error getting last run date: {e}")
        return None


def update_last_run_date(run_date: datetime, status: str = "processed"):
    """
    Updates the last run date and its status after processing.
    """
    try:
        validate_sql_config()
        conn = get_connection()

        try:
            cursor = conn.cursor()
            table_name = SQL_SERVER_CONFIG["LAST_RUN_DATE_TABLE_NAME"]

            # Ensure table exists and has the Status column
            cursor.execute(
                """
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = ?
                """,
                table_name,
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    f"""
                    CREATE TABLE [dbo].[{table_name}] (
                        [Last_update_Run_Date] DATE NOT NULL,
                        [Status] VARCHAR(50) NULL
                    )
                    """
                )

            # Check if Status column exists, add if not
            cursor.execute(
                """
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = ? AND COLUMN_NAME = 'Status'
                """,
                table_name,
            )
            if cursor.fetchone()[0] == 0:
                logger.warning(f"Adding 'Status' column to {table_name} table.")
                cursor.execute(f"ALTER TABLE [dbo].[{table_name}] ADD [Status] VARCHAR(50) NULL")

            normalized_date = run_date.replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            # Delete existing entry for this date and insert new one
            # This ensures only one status per date is stored, and allows updating a status if needed
            cursor.execute(f"DELETE FROM [dbo].[{table_name}] WHERE Last_update_Run_Date = ?", normalized_date)
            cursor.execute(
                f"""
                INSERT INTO [dbo].[{table_name}] (Last_update_Run_Date, Status)
                VALUES (?, ?)
                """,
                normalized_date,
                status
            )

            conn.commit()
            cursor.close()

            logger.info(
                f"Last run date updated to {normalized_date.strftime('%Y-%m-%d')} with status: {status}"
            )

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error updating last run date: {e}")
        raise

# =========================================================
# SANITIZE COLUMN NAMES FOR SQL
# =========================================================
def sanitize_column_name(name: str) -> str:
    """
    Sanitizes column names for SQL Server compatibility.
    Removes special characters and spaces, replaces with underscores.
    
    Args:
        name: Original column name
        
    Returns:
        str: Sanitized column name
    """
    # Remove special characters, keep alphanumeric and spaces
    sanitized = ''.join(c if c.isalnum() or c == ' ' else '_' for c in name)
    # Replace spaces with underscores
    sanitized = sanitized.replace(' ', '_')
    # Remove multiple consecutive underscores
    while '__' in sanitized:
        sanitized = sanitized.replace('__', '_')
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    # Ensure it starts with a letter or underscore
    if sanitized and not sanitized[0].isalpha():
        sanitized = 'Col_' + sanitized
    return sanitized if sanitized else 'Column'

# =========================================================
# COLUMN MAPPING (Scraped Headers -> Database Columns)
# =========================================================
# Maps the scraped header names to the actual database column names
COLUMN_MAPPING = {
    "Withholder Name": "Withholder_Name",
    "Invoice No": "Invoice_No",
    "Certificate Date": "Certificate_Date",
    "VAT Withholding Amount": "VAT_holding_Amount",
    "WHT Certificate No": "WHT_Certificate_No"
}

def filter_and_map_columns(headers: List[str], data: List[List]):
    """
    Filters and maps data to only include the specified database columns.
    
    Args:
        headers: List of scraped column headers
        data: List of data rows
        
    Returns:
        tuple: (filtered_headers, filtered_data) - Only the columns that match the mapping
    """
    # Find indices of columns we want to keep (in order of COLUMN_MAPPING)
    column_indices = []
    db_column_names = []
    
    # Iterate through headers with index to preserve order
    for idx, scraped_header in enumerate(headers):
        if scraped_header in COLUMN_MAPPING:
            column_indices.append(idx)
            db_column_names.append(COLUMN_MAPPING[scraped_header])
    
    if not column_indices:
        raise ValueError(f"None of the scraped headers match the database columns. Scraped headers: {headers}")
    
    # Verify we found all required columns
    missing_columns = set(COLUMN_MAPPING.keys()) - set(headers)
    if missing_columns:
        logger.warning(f"Some expected columns not found in scraped data: {missing_columns}")
    
    # Filter data to only include mapped columns
    filtered_data = []
    for row in data:
        filtered_row = [row[idx] if idx < len(row) else '' for idx in column_indices]
        filtered_data.append(filtered_row)
    
    logger.info(f"Filtered columns: {len(db_column_names)} out of {len(headers)} total columns")
    logger.info(f"Database columns: {db_column_names}")
    
    return db_column_names, filtered_data

# =========================================================
# VALIDATE SQL SERVER CONFIG
# =========================================================
def validate_sql_config():
    """
    Validates that all required SQL Server configuration is present.
    
    Raises:
        ValueError: If any required configuration is missing
    """
    missing = []
    if not SQL_SERVER_CONFIG['server']:
        missing.append("SQL_SERVER")
    if not SQL_SERVER_CONFIG['username']:
        missing.append("SQL_USERNAME")
    if not SQL_SERVER_CONFIG['password']:
        missing.append("SQL_PASSWORD")
    if not SQL_SERVER_CONFIG['database']:
        missing.append("SQL_DATABASE")
    if not SQL_SERVER_CONFIG['table_name']:
        missing.append("SQL_TABLE")
    
    if missing:
        raise ValueError(f"Missing required SQL Server configuration in Config.env: {', '.join(missing)}")

# =========================================================
# SAVE DATA TO SQL SERVER
# =========================================================
def save_to_sql_server(headers: List[str], data: List[List], table_name: Optional[str] = None):
    """
    Saves scraped table data to SQL Server.
    
    Args:
        headers: List of column headers
        data: List of data rows (each row is a list)
        table_name: Optional custom table name. If not provided, uses SQL_SERVER_CONFIG['table_name']
    
    Returns:
        int: Number of rows inserted
    """
    try:
        if not headers or not isinstance(headers, list) or len(headers) == 0:
            raise ValueError("Headers must be a non-empty list")
        
        if not data or not isinstance(data, list):
            raise ValueError("Data must be a non-empty list")
        
        if len(data) > 0 and not isinstance(data[0], (list, tuple)):
            raise ValueError("Data rows must be lists or tuples")
        
        # Use provided table name or default from config
        if table_name:
            SQL_SERVER_CONFIG['table_name'] = table_name
        
        # Validate configuration
        validate_sql_config()
        
        # Filter and map columns to database column names
        db_headers, filtered_data = filter_and_map_columns(headers, data)
        
        logger.info(f"Connecting to SQL Server: {SQL_SERVER_CONFIG['server']}")
        logger.info(f"Database: {SQL_SERVER_CONFIG['database']}")
        logger.info(f"Table: {SQL_SERVER_CONFIG['table_name']}")
        logger.info(f"Inserting {len(db_headers)} columns: {db_headers}")
        
        # Connect to database
        conn = get_connection()
        
        try:
            cursor = conn.cursor()
            table_name = SQL_SERVER_CONFIG['table_name']
            
            # Find Invoice_No column index in db_headers
            invoice_no_index = None
            if "Invoice_No" in db_headers:
                invoice_no_index = db_headers.index("Invoice_No")
            else:
                logger.warning("Invoice_No column not found. Cannot check for duplicates.")
            
            # Get existing Invoice Numbers from database to prevent duplicates
            existing_invoices = set()
            if invoice_no_index is not None:
                try:
                    select_existing_query = f"SELECT DISTINCT [Invoice_No] FROM [{SQL_SERVER_CONFIG['database']}].[dbo].[{table_name}] WHERE [Invoice_No] IS NOT NULL AND [Invoice_No] != ''"
                    cursor.execute(select_existing_query)
                    existing_results = cursor.fetchall()
                    existing_invoices = {str(row[0]).strip() for row in existing_results if row[0]}
                    logger.info(f"Found {len(existing_invoices)} existing Invoice Numbers in database")
                except Exception as e:
                    logger.warning(f"Could not fetch existing Invoice Numbers: {e}. Proceeding without duplicate check.")
            
            # Prepare insert query using database column names
            columns = ', '.join([f"[{h}]" for h in db_headers])
            placeholders = ', '.join(['?' for _ in db_headers])
            
            insert_query = f"""
                INSERT INTO [{SQL_SERVER_CONFIG['database']}].[dbo].[{table_name}] 
                ({columns})
                VALUES ({placeholders})
            """
            
            # Filter out duplicates and insert only new rows
            rows_inserted = 0
            rows_skipped = 0
            
            for row_idx, row in enumerate(filtered_data, 1):
                try:
                    # Ensure row has same number of columns as database headers
                    if len(row) < len(db_headers):
                        # Pad with empty strings if row is shorter
                        row = list(row) + [''] * (len(db_headers) - len(row))
                    elif len(row) > len(db_headers):
                        # Trim if row is longer
                        row = list(row[:len(db_headers)])
                    
                    # Check for duplicate Invoice Number
                    if invoice_no_index is not None and len(existing_invoices) > 0:
                        invoice_no = str(row[invoice_no_index]).strip() if invoice_no_index < len(row) else ''
                        if invoice_no and invoice_no in existing_invoices:
                            rows_skipped += 1
                            logger.debug(f"Row {row_idx} skipped - duplicate Invoice Number: {invoice_no}")
                            continue
                        # Add to existing set to prevent duplicates within the same batch
                        if invoice_no:
                            existing_invoices.add(invoice_no)
                    
                    # Convert all values to strings and handle None
                    row_values = [str(val) if val is not None else '' for val in row]
                    
                    cursor.execute(insert_query, row_values)
                    rows_inserted += 1
                    
                    if row_idx % 100 == 0:
                        logger.debug(f"Processed {row_idx} rows, inserted {rows_inserted}, skipped {rows_skipped}...")
                        
                except Exception as e:
                    logger.warning(f"Error inserting row {row_idx}: {e}")
                    logger.debug(f"Row data: {row}")
                    continue
            
            # Commit transaction
            conn.commit()
            cursor.close()
            
            logger.info(f"Successfully inserted {rows_inserted} new rows into '{table_name}'")
            if rows_skipped > 0:
                logger.info(f"Skipped {rows_skipped} duplicate rows (based on Invoice Number)")
            logger.info(f"Total rows processed: {len(filtered_data)}")
            
            return rows_inserted
            
        finally:
            conn.close()
            logger.info("Database connection closed")
            
    except ImportError as e:
        logger.error("pyodbc not installed. Install with: pip install pyodbc")
        raise
    except Exception as e:
        logger.error(f"Error saving data to SQL Server: {e}")
        raise

# =========================================================
# SAVE WITH TIMESTAMP (OPTIONAL)
# =========================================================
def save_to_sql_server_with_timestamp(headers: List[str], data: List[List], 
                                     table_name: Optional[str] = None, 
                                     suffix: Optional[str] = None):
    """
    Saves scraped table data to SQL Server with optional timestamp suffix in table name.
    
    Args:
        headers: List of column headers
        data: List of data rows (each row is a list)
        table_name: Base table name (optional)
        suffix: Optional suffix to append to table name
    
    Returns:
        int: Number of rows inserted
    """
    try:
        original_table_name = SQL_SERVER_CONFIG['table_name']
        
        if table_name:
            base_name = table_name
        else:
            base_name = original_table_name
        
        if suffix:
            final_table_name = f"{base_name}_{suffix}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_table_name = f"{base_name}_{timestamp}"
        
        logger.info(f"Saving with table name: {final_table_name}")
        return save_to_sql_server(headers, data, final_table_name)
        
    except Exception as e:
        logger.error(f"Error saving to SQL Server with timestamp: {e}")
        raise
