import json
import logging
import os
from config import Config

logger = logging.getLogger(__name__)

def format_as_json(headers, data, start_index=1):
    """
    Converts headers and data rows to a list of dictionaries.
    Ensures 'Sr.No.' is in a continuous sequence.
    """
    json_data = []
    if not data:
        return json_data
        
    for idx, row in enumerate(data, start=start_index):
        item = {}
        for i, header in enumerate(headers):
            # Check for various Serial Number header versions
            if header in ["Sr.No.", "Sr. No.", "Sr No", "Serial No", "Serial Number"]:
                item[header] = str(idx)
            elif i < len(row):
                item[header] = row[i]
            else:
                item[header] = ""
        json_data.append(item)
    return json_data

def save_json(headers, data, file_path=None):
    """
    Saves scraped table data to a JSON file and prints it to the console.
    """
    try:
        if not data:
            logger.warning("No data provided to save_json")
            return None

        json_data = format_as_json(headers, data)

        # Use provided path or default from config
        if file_path is None:
            file_path = Config.JSON_PATH
        
        # Create directory if it doesn't exist
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        # Save to JSON file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=4)

        logger.info(f"Data saved successfully to JSON: {file_path}")
        
        # Output to console
        print_json_console(json_data)
        
        return file_path
        
    except Exception as e:
        logger.error(f"Error saving JSON file: {e}")
        raise

def print_json_console(json_data):
    """Prints JSON data to console in a pretty format."""
    print("\n" + "="*50)
    print("JSON FORMATTED OUTPUT")
    print("="*50)
    print(json.dumps(json_data, indent=4))
    print("="*50 + "\n")
