import os
import requests
import hashlib
import datetime
import time
import re
import logging
from pathlib import Path
import PyPDF2
import io

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sbi_forex_downloader.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SBI_FOREX_DOWNLOADER")

# URLs to check for forex card rates
URLS = [
    "https://sbi.co.in/documents/16012/1400784/FOREX_CARD_RATES.pdf",
    "https://bank.sbi/documents/16012/1400784/FOREX_CARD_RATES.pdf"
]

def setup_directories():
    """Create necessary directories if they don't exist"""
    Path("downloads").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)
    
    # Create last_hash.txt if it doesn't exist
    if not os.path.exists("data/last_hash.txt"):
        with open("data/last_hash.txt", "w") as f:
            f.write("")
            
    # Create last_date.txt if it doesn't exist
    if not os.path.exists("data/last_date.txt"):
        with open("data/last_date.txt", "w") as f:
            f.write("")

def get_last_hash():
    """Get the hash of the last downloaded PDF"""
    try:
        with open("data/last_hash.txt", "r") as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Error reading last hash: {e}")
        return ""

def save_hash(file_hash):
    """Save the hash of the downloaded PDF"""
    try:
        with open("data/last_hash.txt", "w") as f:
            f.write(file_hash)
    except Exception as e:
        logger.error(f"Error saving hash: {e}")

def get_last_date():
    """Get the date of the last downloaded PDF"""
    try:
        with open("data/last_date.txt", "r") as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Error reading last date: {e}")
        return ""

def save_date(date_str):
    """Save the date of the downloaded PDF"""
    try:
        with open("data/last_date.txt", "w") as f:
            f.write(date_str)
    except Exception as e:
        logger.error(f"Error saving date: {e}")

def extract_date_from_pdf(pdf_bytes):
    """Extract the date and time from the PDF content"""
    try:
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = pdf_reader.pages[0].extract_text()
        
        # Try to find date pattern in format DD-MM-YYYY or similar
        date_pattern = r'Date\s*(\d{2}-\d{2}-\d{4})'
        date_match = re.search(date_pattern, text)
        
        # Try to find time pattern in format HH:MM AM/PM or similar
        time_pattern = r'(\d{1,2}:\d{2}\s*(?:AM|PM)?)'
        time_match = re.search(time_pattern, text)
        
        date_str = date_match.group(1) if date_match else ""
        time_str = time_match.group(1) if time_match else ""
        
        return f"{date_str} {time_str}".strip()
    except Exception as e:
        logger.error(f"Error extracting date from PDF: {e}")
        return ""

def download_forex_rates():
    """Download forex rates PDF and save if it's new"""
    setup_directories()
    last_hash = get_last_hash()
    last_date = get_last_date()
    
    for url in URLS:
        try:
            logger.info(f"Checking URL: {url}")
            response = requests.get(url, timeout=30)
            
            if response.status_code != 200:
                logger.warning(f"Failed to download from {url}, status code: {response.status_code}")
                continue
                
            # Calculate hash of the downloaded content
            content_hash = hashlib.md5(response.content).hexdigest()
            
            # If this is a new file (hash is different)
            if content_hash != last_hash:
                # Extract date from PDF
                pdf_date = extract_date_from_pdf(response.content)
                
                if not pdf_date:
                    logger.warning("Could not extract date from PDF. Using current datetime.")
                    pdf_date = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
                
                # Only save if date is different or last_date is empty
                if pdf_date != last_date or not last_date:
                    # Format filename with date
                    clean_date = pdf_date.replace(":", "").replace(" ", "_").replace("-", "")
                    filename = f"downloads/SBI_FOREX_CARD_RATES_{clean_date}.pdf"
                    
                    # Save the PDF
                    with open(filename, "wb") as f:
                        f.write(response.content)
                    
                    # Update hash and date
                    save_hash(content_hash)
                    save_date(pdf_date)
                    
                    logger.info(f"New forex rates downloaded: {filename}")
                    return True
                else:
                    logger.info(f"PDF date ({pdf_date}) is the same as last download. Skipping.")
            else:
                logger.info("No new forex rates available (content hash is the same).")
            
            # If we've successfully reached this URL, no need to try others
            break
                
        except Exception as e:
            logger.error(f"Error downloading from {url}: {e}")
    
    return False

if __name__ == "__main__":
    logger.info("SBI Forex Card Rates Downloader Started")
    download_forex_rates()
    logger.info("Downloader execution completed")
