import os
import requests
import json
import re
from datetime import datetime
import logging
from pathlib import Path
import shutil

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("one_time_repo_download.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ONE_TIME_REPO_DOWNLOADER")

# GitHub API URL for the repository
REPO_API_URL = "https://api.github.com/repos/sahilgupta/sbi-fx-ratekeeper/contents/csv_files"

# Cutoff date - only download files up to May 8, 2025
CUTOFF_DATE = datetime(2025, 5, 8)

def setup_directories():
    """Create necessary directories if they don't exist"""
    Path("temp_downloads").mkdir(exist_ok=True)
    Path("downloads").mkdir(exist_ok=True)

def download_file(url, filename):
    """Download a file from a URL and save it"""
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            return True
        else:
            logger.error(f"Failed to download {url}, status code: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        return False

def extract_date_from_filename(filename):
    """Extract date from filename patterns like SBI_FOREX_CARD_RATES_12052025_0430.pdf"""
    try:
        # Try to find date pattern in format like 12052025_0430
        date_pattern = r'(\d{2})(\d{2})(\d{4})_?(\d{2})(\d{2})?'
        match = re.search(date_pattern, filename)
        
        if match:
            day, month, year = match.group(1), match.group(2), match.group(3)
            return datetime(int(year), int(month), int(day))
        else:
            # If no match, use current date
            return datetime.now()
    except Exception as e:
        logger.error(f"Error extracting date from filename {filename}: {e}")
        return datetime.now()

def is_before_cutoff(file_date):
    """Check if file date is before or equal to cutoff date"""
    return file_date <= CUTOFF_DATE

def download_from_github_repo():
    """Download files from GitHub repository up to cutoff date"""
    setup_directories()
    downloaded_files = []
    
    try:
        # Get repository contents
        response = requests.get(REPO_API_URL)
        if response.status_code != 200:
            logger.error(f"Failed to get repository contents, status code: {response.status_code}")
            return False
        
        contents = json.loads(response.text)
        
        for item in contents:
            if item['type'] == 'file' and (item['name'].endswith('.pdf') or item['name'].endswith('.csv')):
                # Extract date from filename
                file_date = extract_date_from_filename(item['name'])
                
                # Only download if before cutoff date
                if is_before_cutoff(file_date):
                    # Destination filename in temp directory
                    dest_filename = os.path.join("temp_downloads", item['name'])
                    
                    # Skip if file already exists in final downloads directory
                    final_filename = os.path.join("downloads", item['name'])
                    if os.path.exists(final_filename):
                        logger.info(f"File {final_filename} already exists, skipping...")
                        continue
                    
                    # Download the file
                    logger.info(f"Downloading {item['name']} to {dest_filename}...")
                    download_success = download_file(item['download_url'], dest_filename)
                    
                    if download_success:
                        logger.info(f"Successfully downloaded {item['name']}")
                        downloaded_files.append(dest_filename)
                    else:
                        logger.error(f"Failed to download {item['name']}")
                else:
                    logger.info(f"Skipping {item['name']} as it's after the cutoff date")
            
            elif item['type'] == 'dir':
                # If it's a directory, process it recursively
                process_directory(item['url'], downloaded_files)
        
        # After downloading all files, merge them into the downloads directory
        merge_files_to_downloads(downloaded_files)
                
        return True
                
    except Exception as e:
        logger.error(f"Error processing GitHub repository: {e}")
        return False

def process_directory(directory_url, downloaded_files):
    """Process a directory in the repository recursively"""
    try:
        # Get directory contents
        response = requests.get(directory_url)
        if response.status_code != 200:
            logger.error(f"Failed to get directory contents, status code: {response.status_code}")
            return
        
        contents = json.loads(response.text)
        
        for item in contents:
            if item['type'] == 'file' and (item['name'].endswith('.pdf') or item['name'].endswith('.csv')):
                # Extract date from filename
                file_date = extract_date_from_filename(item['name'])
                
                # Only download if before cutoff date
                if is_before_cutoff(file_date):
                    # Destination filename in temp directory
                    dest_filename = os.path.join("temp_downloads", item['name'])
                    
                    # Skip if file already exists in final downloads directory
                    final_filename = os.path.join("downloads", item['name'])
                    if os.path.exists(final_filename):
                        logger.info(f"File {final_filename} already exists, skipping...")
                        continue
                    
                    # Download the file
                    logger.info(f"Downloading {item['name']} to {dest_filename}...")
                    download_success = download_file(item['download_url'], dest_filename)
                    
                    if download_success:
                        logger.info(f"Successfully downloaded {item['name']}")
                        downloaded_files.append(dest_filename)
                    else:
                        logger.error(f"Failed to download {item['name']}")
                else:
                    logger.info(f"Skipping {item['name']} as it's after the cutoff date")
            
            elif item['type'] == 'dir':
                # If it's a directory, process it recursively
                process_directory(item['url'], downloaded_files)
                
    except Exception as e:
        logger.error(f"Error processing directory {directory_url}: {e}")

def merge_files_to_downloads(file_list):
    """Move downloaded files from temp directory to downloads directory"""
    logger.info("Merging downloaded files to downloads directory...")
    
    for file_path in file_list:
        filename = os.path.basename(file_path)
        destination = os.path.join("downloads", filename)
        
        try:
            shutil.move(file_path, destination)
            logger.info(f"Moved {filename} to downloads directory")
        except Exception as e:
            logger.error(f"Error moving {filename}: {e}")
    
    # Try to remove the temp directory if it's empty
    try:
        if not os.listdir("temp_downloads"):
            os.rmdir("temp_downloads")
            logger.info("Removed empty temp_downloads directory")
    except Exception as e:
        logger.error(f"Error removing temp_downloads directory: {e}")

if __name__ == "__main__":
    logger.info("One-time SBI GitHub Repository Downloader Started")
    logger.info(f"Downloading files up to {CUTOFF_DATE.strftime('%Y-%m-%d')}")
    download_from_github_repo()
    logger.info("One-time Repository Downloader execution completed")
