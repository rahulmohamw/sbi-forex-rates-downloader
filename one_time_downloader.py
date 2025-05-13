import os
import requests
import json
import re
from datetime import datetime
import logging
from pathlib import Path
import shutil

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
    # Create temp downloads directory for staging files
    temp_dir = Path("temp_downloads")
    temp_dir.mkdir(exist_ok=True)
    
    # Create main downloads directory
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)
    
    # Create year subdirectories to match source repository structure
    for year in YEARS_TO_PROCESS:
        year_dir = downloads_dir / year
        year_dir.mkdir(exist_ok=True)
        logger.info(f"Created directory: {year_dir}")
        
        # Also create temp year directories
        temp_year_dir = temp_dir / year
        temp_year_dir.mkdir(exist_ok=True)
    
    # Log existing files structure
    logger.info("Checking existing files structure:")
    for year in YEARS_TO_PROCESS:
        year_path = downloads_dir / year
        if year_path.exists():
            files = list(year_path.glob("*.pdf"))
            logger.info(f"Directory {year}: {len(files)} PDF files")
    
    return downloads_dir

def download_file(url, filename):
    """Download a file from a URL and save it"""
    try:
        logger.debug(f"Attempting to download from URL: {url}")
        response = requests.get(url)
        if response.status_code == 200:
            os.makedirs(os.path.dirname(filename), exist_ok=True)  # Ensure directory exists
            with open(filename, 'wb') as f:
                f.write(response.content)
            logger.debug(f"File saved to {filename} with size {os.path.getsize(filename)} bytes")
            return True
        else:
            logger.error(f"Failed to download {url}, status code: {response.status_code}")
            logger.debug(f"Response content: {response.text[:200]}...")
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
            logger.debug(f"Extracted date from {filename}: {day}/{month}/{year}")
            return datetime(int(year), int(month), int(day))
        else:
            # If no match found, try another common format
            alt_pattern = r'(\d{1,2})[-_](\d{1,2})[-_](\d{4})'
            alt_match = re.search(alt_pattern, filename)
            if alt_match:
                day, month, year = alt_match.group(1), alt_match.group(2), alt_match.group(3)
                logger.debug(f"Extracted date using alt pattern from {filename}: {day}/{month}/{year}")
                return datetime(int(year), int(month), int(day))
            
            # For files without dates, use file year as fallback
            year_in_path = re.search(r'/(20\d{2})/', filename)
            if year_in_path:
                year = year_in_path.group(1)
                logger.debug(f"Using year from path for {filename}: {year}")
                return datetime(int(year), 1, 1)  # Default to January 1st of that year
                
            logger.warning(f"Could not extract date from {filename}, using current date")
            return datetime.now()
    except Exception as e:
        logger.error(f"Error extracting date from filename {filename}: {e}")
        return datetime.now()

def is_before_cutoff(file_date):
    """Check if file date is before or equal to cutoff date"""
    result = file_date <= CUTOFF_DATE
    if not result:
        logger.debug(f"File date {file_date.strftime('%Y-%m-%d')} is after cutoff date {CUTOFF_DATE.strftime('%Y-%m-%d')}")
    return result

def create_month_subdirectory(base_dir, file_date):
    """Create month subdirectory based on file date and return path"""
    month_name = file_date.strftime('%B')  # Full month name
    month_dir = base_dir / month_name
    month_dir.mkdir(exist_ok=True)
    return month_dir

def download_from_github_repo():
    """Download files from GitHub repository up to cutoff date"""
    downloads_dir = setup_directories()
    downloaded_files = []
    skipped_files = []
    
    try:
        # Get authentication token from environment if available
        auth_token = os.environ.get('GITHUB_TOKEN')
        headers = {'Authorization': f'token {auth_token}'} if auth_token else {}
        
        # Process each year directory
        for year in YEARS_TO_PROCESS:
            year_api_url = f"{REPO_API_URL}/{year}"
            logger.info(f"Processing year directory: {year} from {year_api_url}")
            
            # Get year directory contents
            response = requests.get(year_api_url, headers=headers)
            
            if response.status_code == 200:
                contents = json.loads(response.text)
                logger.info(f"Found {len(contents)} items in {year} directory")
                
                # Process each file in the year directory
                for item in contents:
                    if item['type'] == 'file' and item['name'].endswith('.pdf'):
                        try:
                            # Extract date from filename
                            file_date = extract_date_from_filename(item['name'])
                            
                            # Only download if before cutoff date
                            if is_before_cutoff(file_date):
                                # Use year-based directory structure
                                temp_year_dir = Path("temp_downloads") / year
                                temp_year_dir.mkdir(exist_ok=True)
                                
                                # Create month subdirectory based on file date
                                temp_month_dir = create_month_subdirectory(temp_year_dir, file_date)
                                
                                dest_filename = temp_month_dir / item['name']
                                
                                # Create corresponding month directory in downloads
                                downloads_month_dir = create_month_subdirectory(downloads_dir / year, file_date)
                                final_filename = downloads_month_dir / item['name']
                                
                                # Skip if file already exists in final downloads directory
                                if final_filename.exists():
                                    logger.info(f"File {final_filename} already exists, skipping...")
                                    skipped_files.append(str(final_filename))
                                    continue
                                
                                # Download the file
                                logger.info(f"Downloading {item['name']} to {dest_filename}...")
                                download_success = download_file(item['download_url'], dest_filename)
                                
                                if download_success:
                                    logger.info(f"Successfully downloaded {item['name']}")
                                    downloaded_files.append(str(dest_filename))
                                else:
                                    logger.error(f"Failed to download {item['name']}")
                            else:
                                logger.info(f"Skipping {item['name']} as it's after the cutoff date")
                        except Exception as file_e:
                            logger.error(f"Error processing file {item['name']}: {file_e}", exc_info=True)
            else:
                logger.error(f"Failed to get year directory contents for {year}, status code: {response.status_code}")
                logger.debug(f"Response content: {response.text[:200]}...")
        
        # Summary before merging
        logger.info(f"Download summary: {len(downloaded_files)} files downloaded, {len(skipped_files)} files skipped")
        
        # After downloading all files, merge them into the downloads directory
        merge_files_to_downloads(downloaded_files)
        
        # Final verification
        verify_downloads(downloads_dir, downloaded_files)
                
        return True
                
    except Exception as e:
        logger.error(f"Error processing GitHub repository: {e}", exc_info=True)
        return False

def merge_files_to_downloads(file_list):
    """Move downloaded files from temp directory to downloads directory while maintaining year/month structure"""
    logger.info(f"Merging {len(file_list)} downloaded files to downloads directory...")
    
    moved_count = 0
    for file_path in file_list:
        file_path = Path(file_path)
        
        # Extract year and month from the path structure (temp_downloads/YEAR/MONTH/filename)
        year = file_path.parent.parent.name
        month = file_path.parent.name
        filename = file_path.name
        
        # Destination preserves the year/month structure
        destination = Path("downloads") / year / month / filename
        
        try:
            # Check if source file exists and has content
            if not file_path.exists():
                logger.error(f"Source file {file_path} does not exist")
                continue
                
            file_size = file_path.stat().st_size
            logger.debug(f"Moving file {filename} with size {file_size} bytes to {destination}")
            
            # Ensure destination directory exists
            destination.parent.mkdir(exist_ok=True)
            
            # Move the file
            shutil.move(str(file_path), str(destination))
            moved_count += 1
            logger.info(f"Moved {filename} to {destination}")
        except Exception as e:
            logger.error(f"Error moving {filename}: {e}", exc_info=True)
    
    logger.info(f"Successfully moved {moved_count} out of {len(file_list)} files to downloads directory")
    
    # Try to remove the temp directory if it's empty
    try:
        temp_dir = Path("temp_downloads")
        if temp_dir.exists():
            # Check if any files remain in temp_downloads or its subdirectories
            remaining_files = list(temp_dir.glob("**/*"))
            if not remaining_files:
                shutil.rmtree(temp_dir)
                logger.info("Removed empty temp_downloads directory and its subdirectories")
            else:
                logger.warning(f"temp_downloads directory not empty, contains {len(remaining_files)} files, skipping removal")
    except Exception as e:
        logger.error(f"Error removing temp_downloads directory: {e}", exc_info=True)

def verify_downloads(downloads_dir, downloaded_files):
    """Verify that files were correctly downloaded and moved"""
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
            files = list(year_path.glob("**/*.pdf"))  # Include files in month subdirectories
            file_count = len(files)
            total_files += file_count
            logger.info(f"Found {file_count} PDF files in {year} directory")
            
            # List months and file counts per month
            months = set(f.parent.name for f in files)
            for month in sorted(months):
                month_files = [f for f in files if f.parent.name == month]
                logger.info(f"  - Month {month}: {len(month_files)} files")
    
    logger.info(f"Total PDFs across all years: {total_files}")
    
    # Check for specific files that should have been moved
    successful_moves = 0
    for temp_file_path in downloaded_files:
        temp_file_path = Path(temp_file_path)
        year = temp_file_path.parent.parent.name
        month = temp_file_path.parent.name
        filename = temp_file_path.name
        
        final_path = Path(downloads_dir) / year / month / filename
        
        if final_path.exists():
            successful_moves += 1
            logger.debug(f"Verified file exists in downloads: {final_path}")
        else:
            logger.warning(f"File not found in downloads: {final_path}")
    
    logger.info(f"Verified {successful_moves} out of {len(downloaded_files)} files were moved correctly")

if __name__ == "__main__":
    logger.info("SBI GitHub Repository Downloader Started")
    logger.info(f"Downloading files up to {CUTOFF_DATE.strftime('%Y-%m-%d')}")
    logger.info(f"Processing year directories: {', '.join(YEARS_TO_PROCESS)}")
    
    # Check if the repository path is valid
    logger.info(f"Testing repository access to {REPO_API_URL}")
    
    # Get authentication token from environment if available
    auth_token = os.environ.get('GITHUB_TOKEN')
    headers = {'Authorization': f'token {auth_token}'} if auth_token else {}
    
    try:
        test_response = requests.get(REPO_API_URL, headers=headers)
        if test_response.status_code == 200:
            logger.info("Repository access successful")
            repo_contents = json.loads(test_response.text)
            years_found = [item['name'] for item in repo_contents if item['type'] == 'dir']
            logger.info(f"Available years in repository: {years_found}")
        else:
            logger.error(f"Repository access failed with status code {test_response.status_code}")
            logger.debug(f"Response: {test_response.text[:200]}...")
    except Exception as e:
        logger.error(f"Exception when testing repository access: {e}", exc_info=True)
    
    # Run the main download function
    result = download_from_github_repo()
    logger.info(f"SBI Repository Downloader execution completed with result: {'Success' if result else 'Failure'}")
