import os
import requests
import json
import logging
from pathlib import Path
import shutil
from datetime import datetime

# Set up logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sbi_repo_download.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SBI_REPO_DOWNLOADER")

# GitHub API URL for the repository base
REPO_API_URL = "https://api.github.com/repos/sahilgupta/sbi-fx-ratekeeper/contents/pdf_files"

# List of years to process
YEARS_TO_PROCESS = ["2020", "2021", "2022", "2023", "2024", "2025"]

# Cutoff date - only download files up to May 8, 2025
CUTOFF_DATE = datetime(2025, 5, 8)

def setup_directories():
    """Create necessary directories if they don't exist"""
    # Create downloads directory
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)
    
    # Create year subdirectories
    for year in YEARS_TO_PROCESS:
        year_dir = downloads_dir / year
        year_dir.mkdir(exist_ok=True)
        logger.info(f"Created directory: {year_dir}")
    
    # Log existing files structure
    logger.info("Checking existing files structure:")
    for year in YEARS_TO_PROCESS:
        year_path = downloads_dir / year
        if year_path.exists():
            files = list(year_path.glob("**/*.pdf"))
            logger.info(f"Directory {year}: {len(files)} PDF files")
    
    return downloads_dir

def download_file(url, dest_path):
    """Download a file from a URL and save it to the specified path"""
    try:
        logger.debug(f"Downloading from URL: {url}")
        response = requests.get(url)
        if response.status_code == 200:
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            # Save the file
            with open(dest_path, 'wb') as f:
                f.write(response.content)
            
            file_size = os.path.getsize(dest_path)
            logger.info(f"Successfully downloaded {dest_path} ({file_size} bytes)")
            return True
        else:
            logger.error(f"Failed to download {url}, status code: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        return False

def extract_month_from_filename(filename):
    """Extract month from filename for organizing by month"""
    # Default to file creation date if we cannot extract from filename
    try:
        # Try to extract month from filename patterns like SBI_FOREX_CARD_RATES_12052025_0430.pdf
        # where 12 is the day and 05 is the month
        
        # If the filename contains 8 consecutive digits, the 3rd and 4th are likely the month
        # (format: DDMMYYYY in the filename)
        if '_' in filename:
            parts = filename.split('_')
            for part in parts:
                if len(part) >= 8 and part.isdigit():
                    # Extract month from position 2-4
                    month_num = int(part[2:4])
                    if 1 <= month_num <= 12:
                        month_name = datetime(2020, month_num, 1).strftime('%B')
                        logger.debug(f"Extracted month from filename {filename}: {month_name}")
                        return month_name
        
        # If we can't extract a month, use the file's year directory as a fallback
        # Default to January
        return "January"
    except Exception as e:
        logger.error(f"Error extracting month from {filename}: {e}")
        return "January"  # Default to January if we can't determine month

def download_from_github_repo():
    """Download all PDF files from GitHub repository sorted by year and month"""
    downloads_dir = setup_directories()
    downloaded_files = []
    skipped_files = []
    
    # Process each year directory
    for year in YEARS_TO_PROCESS:
        year_api_url = f"{REPO_API_URL}/{year}"
        logger.info(f"Processing year directory: {year} from {year_api_url}")
        
        try:
            # Get year directory contents
            response = requests.get(year_api_url)
            
            if response.status_code == 200:
                contents = json.loads(response.text)
                logger.info(f"Found {len(contents)} items in {year} directory")
                
                # Process each file in the year directory
                for item in contents:
                    if item['type'] == 'file' and item['name'].endswith('.pdf'):
                        try:
                            # Extract month for organizing files
                            month = extract_month_from_filename(item['name'])
                            
                            # Create month directory
                            month_dir = downloads_dir / year / month
                            month_dir.mkdir(exist_ok=True)
                            
                            # Define destination file path
                            dest_path = month_dir / item['name']
                            
                            # Skip if file already exists
                            if dest_path.exists():
                                logger.info(f"File {dest_path} already exists, skipping...")
                                skipped_files.append(str(dest_path))
                                continue
                            
                            # Download the file directly to its final destination
                            logger.info(f"Downloading {item['name']} to {dest_path}...")
                            download_success = download_file(item['download_url'], dest_path)
                            
                            if download_success:
                                logger.info(f"Successfully downloaded {item['name']}")
                                downloaded_files.append(str(dest_path))
                            else:
                                logger.error(f"Failed to download {item['name']}")
                        except Exception as file_e:
                            logger.error(f"Error processing file {item['name']}: {file_e}")
            else:
                logger.error(f"Failed to get year directory contents for {year}, status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error processing year {year}: {e}")
    
    # Summary of downloads
    logger.info(f"Download summary: {len(downloaded_files)} files downloaded, {len(skipped_files)} files skipped")
    
    # Final verification
    verify_downloads(downloads_dir)
    
    return True

def verify_downloads(downloads_dir):
    """Verify that files were correctly downloaded"""
    logger.info("Verifying downloads...")
    
    # Check if downloads directory exists
    if not Path(downloads_dir).exists():
        logger.error(f"Downloads directory {downloads_dir} does not exist")
        return
    
    # Count files in each year directory
    total_files = 0
    for year in YEARS_TO_PROCESS:
        year_path = Path(downloads_dir) / year
        if year_path.exists():
            files = list(year_path.glob("**/*.pdf"))
            file_count = len(files)
            total_files += file_count
            logger.info(f"Found {file_count} PDF files in {year} directory")
            
            # List months and file counts per month
            months = set(f.parent.name for f in files)
            for month in sorted(months):
                month_files = [f for f in files if f.parent.name == month]
                logger.info(f"  - Month {month}: {len(month_files)} files")
    
    logger.info(f"Total PDFs across all years: {total_files}")

if __name__ == "__main__":
    logger.info("SBI GitHub Repository Downloader Started")
    logger.info(f"Processing year directories: {', '.join(YEARS_TO_PROCESS)}")
    
    # Check if the repository path is valid
    logger.info(f"Testing repository access to {REPO_API_URL}")
    try:
        test_response = requests.get(REPO_API_URL)
        if test_response.status_code == 200:
            logger.info("Repository access successful")
            repo_contents = json.loads(test_response.text)
            years_found = [item['name'] for item in repo_contents if item['type'] == 'dir']
            logger.info(f"Available years in repository: {years_found}")
        else:
            logger.error(f"Repository access failed with status code {test_response.status_code}")
    except Exception as e:
        logger.error(f"Exception when testing repository access: {e}")
    
    # Run the main download function
    result = download_from_github_repo()
    logger.info(f"SBI Repository Downloader execution completed with result: {'Success' if result else 'Failure'}")
