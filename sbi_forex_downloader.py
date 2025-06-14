import csv
import glob
import io
import logging
import os
import sys
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional
import base64
import json

# Check for required dependencies
required_packages = [
    'dateutil',
    'anthropic', 
    'magic',
    'PyPDF2',
    'requests',
    'fp.fp',
    'pdf2image',
    'requests_html',
    'urllib3'
]

missing_packages = []
for package in required_packages:
    try:
        if package == 'dateutil':
            from dateutil import parser
        elif package == 'anthropic':
            import anthropic
        elif package == 'magic':
            import magic
        elif package == 'PyPDF2':
            import PyPDF2
        elif package == 'requests':
            import requests
        elif package == 'fp.fp':
            from fp.fp import FreeProxy
        elif package == 'pdf2image':
            from pdf2image import convert_from_bytes
        elif package == 'requests_html':
            from requests_html import HTMLSession
        elif package == 'urllib3':
            from urllib3.util.retry import Retry
    except ImportError:
        missing_packages.append(package)

if missing_packages:
    print(f"ERROR: Missing required packages: {', '.join(missing_packages)}")
    print("Please install them using:")
    print("pip install -r requirements.txt")
    print("\nOr install individually:")
    package_map = {
        'dateutil': 'python-dateutil',
        'magic': 'python-magic',
        'fp.fp': 'free-proxy'
    }
    for pkg in missing_packages:
        install_name = package_map.get(pkg, pkg)
        print(f"pip install {install_name}")
    sys.exit(1)

# Now import everything after checking
from dateutil import parser
import anthropic
import magic
import PyPDF2
import requests
from fp.fp import FreeProxy
from requests.adapters import HTTPAdapter
from pdf2image import convert_from_bytes
from requests_html import HTMLSession
from urllib3.util.retry import Retry

# Constants
SBI_DAILY_RATES_URL = (
    "https://www.sbi.co.in/documents/16012/1400784/FOREX_CARD_RATES.pdf"
)
SBI_DAILY_RATES_URL_FALLBACK = (
    "https://bank.sbi/documents/16012/1400784/FOREX_CARD_RATES.pdf"
)
FILE_NAME_FORMAT = "%Y-%m-%d"
FILE_NAME_WITH_TIME_FORMAT = f"{FILE_NAME_FORMAT} %H:%M"
TABLE_COLUMNS = [
    "TT BUY",
    "TT SELL",
    "BILL BUY",
    "BILL SELL",
    "FOREX TRAVEL CARD BUY",
    "FOREX TRAVEL CARD SELL",
    "CN BUY",
    "CN SELL",
]
HEADERS = ["DATE", "PDF FILE"] + TABLE_COLUMNS

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)
file_handler = logging.FileHandler("logs/log.txt")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

# Add console handler for better visibility
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


def setup_session() -> HTMLSession:
    """Set up an HTMLSession with retries"""
    session = HTMLSession()
    retries = Retry(total=5, backoff_factor=3, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


class DateTimeExtractionError(Exception):
    pass


def extract_date_time(
    text: str, file_creation_date: Optional[datetime] = None
) -> datetime:
    """
    Extract date and time from the given text.
    Use file creation date to disambiguate if provided.
    """
    date_line = next(
        (line for line in text.split("\n") if line.strip().lower().startswith("date")),
        None,
    )
    time_line = next(
        (line for line in text.split("\n") if line.strip().lower().startswith("time")),
        None,
    )

    if not date_line or not time_line:
        raise DateTimeExtractionError("Date or time not found in the text")

    parsed_date = parse_date(date_line, file_creation_date)
    parsed_time = parse_time(time_line)

    return datetime.combine(parsed_date, parsed_time)


def parse_date(date_line: str, file_creation_date: Optional[datetime] = None) -> date:
    """
    Parse the date from a given line, handling different formats.
    Use file creation date to disambiguate if provided.
    """
    try:
        parsed_date = parser.parse(date_line, fuzzy=True, dayfirst=True).date()
        parsed_date_us_style = parser.parse(date_line, fuzzy=True).date()

        if parsed_date != parsed_date_us_style:
            logger.warning(
                f"Ambiguous date found: {date_line}. Using file creation date as tie-breaker."
            )
            if file_creation_date and file_creation_date.date() in (
                parsed_date,
                parsed_date_us_style,
            ):
                return file_creation_date.date()
            raise DateTimeExtractionError("Unable to parse date with confidence.")

        return parsed_date
    except Exception as e:
        raise ValueError(f"Failed to parse date from '{date_line}': {e}")


def parse_time(time_line: str) -> datetime.time:
    """
    Parse the time from a given line.
    """
    try:
        return parser.parse(time_line, fuzzy=True).time()
    except ValueError as e:
        raise ValueError(f"Failed to parse time from '{time_line}': {e}")


def extract_currency_rates(text: str) -> List[Dict[str, List[str]]]:
    """Extract currency rates from the given text."""
    import re

    # Sometimes the spacing in the parsed text is incorrect.
    # There may be no space between the currency code and the rates.
    # \s* takes care of such cases.
    currency_line_regex = re.compile(r"([A-Z]{3})\/INR\s*((?:\d+(?:\.\d+)?\s?)+)")

    rates = []

    for line in text.split("\n"):
        match = re.search(currency_line_regex, line)
        if match:
            currency, rates_string = match.groups()
            rates.append(
                {"currency_code": currency, "rates": rates_string.strip().split()}
            )

    return rates


def save_to_csv(
    rates_data: List[Dict[str, List[str]]],
    date_time: datetime,
    output_dir: Optional[str] = None,
) -> None:
    """Save the rates data to the corresponding CSV files."""
    pdf_name = date_time.strftime(FILE_NAME_FORMAT) + ".pdf"
    pdf_file_link = f"https://github.com/rahulmohamw/sbi-forex-rates-downloader/blob/main/pdf_files/{date_time.year}/{date_time.month}/{pdf_name}"
    formatted_date_time = date_time.strftime(FILE_NAME_WITH_TIME_FORMAT)

    output_dir = output_dir or "csv_files"
    os.makedirs(output_dir, exist_ok=True)

    for row in rates_data:
        currency = row["currency_code"]
        new_data = dict(
            zip(HEADERS, [formatted_date_time, pdf_file_link] + row["rates"])
        )

        csv_file_path = os.path.join(output_dir, f"SBI_REFERENCE_RATES_{currency}.csv")
        csv_rows = []

        if os.path.exists(csv_file_path):
            with open(csv_file_path, "r", encoding="UTF8") as f_in:
                reader = csv.DictReader(f_in)
                csv_rows = list(reader)

        csv_rows.append(new_data)
        rows_uniq = list({v["DATE"]: v for v in csv_rows}.values())
        rows_uniq.sort(
            key=lambda x: datetime.strptime(x["DATE"], FILE_NAME_WITH_TIME_FORMAT)
        )

        with open(csv_file_path, "w", encoding="UTF8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(rows_uniq)

        logger.info(f"Saved rates for {currency} to {csv_file_path}")


def save_pdf_file(
    file_content: io.BytesIO, date_time: datetime, output_dir: Optional[str] = None
) -> None:
    """Save the PDF file to the appropriate directory."""
    dir_path = os.path.join(
        output_dir or "pdf_files", str(date_time.year), str(date_time.month)
    )
    os.makedirs(dir_path, exist_ok=True)

    pdf_name = date_time.strftime(FILE_NAME_FORMAT) + ".pdf"
    file_path = os.path.join(dir_path, pdf_name)

    with open(file_path, "wb") as f:
        file_content.seek(0)
        f.write(file_content.getbuffer())
    
    logger.info(f"Saved PDF file to {file_path}")


def download_pdf(
    url: str, session: HTMLSession, use_proxy: bool = False
) -> requests.Response:
    """Download the PDF from the given URL, optionally using a proxy."""
    if use_proxy:
        try:
            proxy = FreeProxy(timeout=1, rand=True, elite=True, https=True).get()
            proxies = {"http": proxy, "https": proxy}
            logger.info(f"Using proxy: {proxy}")
            return session.get(url, timeout=10, proxies=proxies)
        except Exception as e:
            logger.warning(f"Failed to get proxy: {e}")
            return session.get(url, timeout=10)
    return session.get(url, timeout=10)


def get_latest_pdf_from_sbi() -> io.BytesIO:
    """Attempt to download a valid PDF, using fallback URL and proxies if necessary."""
    session = setup_session()

    urls = [SBI_DAILY_RATES_URL, SBI_DAILY_RATES_URL_FALLBACK]
    for url in urls:
        try:
            logger.info(f"Attempting to download PDF from {url}")
            response = download_pdf(url, session)
            response.raise_for_status()
            if magic.from_buffer(response.content[:128]).startswith("PDF document"):
                logger.info("Successfully downloaded PDF")
                return io.BytesIO(response.content)
        except requests.RequestException as e:
            logger.exception(f"Failed to download PDF from {url}: {e}")

    # If we're here, we couldn't get a valid PDF from the main URLs. Try with proxies.
    for attempt in range(5):
        logger.info(f"Failed to download PDFs directly. Attempting with proxies (attempt {attempt + 1}/5)...")

        try:
            response = download_pdf(SBI_DAILY_RATES_URL, session, use_proxy=True)
            response.raise_for_status()
            if magic.from_buffer(response.content[:128]).startswith("PDF document"):
                logger.info("Successfully downloaded PDF using proxy")
                return io.BytesIO(response.content)
        except requests.RequestException as e:
            logger.info(f"Failed to download PDF using proxy (attempt {attempt + 1}): {e}")

    raise Exception("Unable to retrieve a valid PDF after all attempts")


def process_as_image(
    file_content: io.BytesIO,
) -> Tuple[datetime, List[Dict[str, List[str]]]]:
    """Process the PDF as an image when text extraction fails."""
    logger.info("Processing PDF as images using Anthropic Claude API")
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set in environment variables.")
    
    try:
        pages_images = convert_from_bytes(file_content.getvalue(), dpi=500, size=2000)
        client = anthropic.Anthropic(api_key=api_key)

        for page_num, page in enumerate(pages_images):
            logger.info(f"Processing page {page_num + 1}/{len(pages_images)}")
            buffered = io.BytesIO()
            page.save(buffered, format="JPEG")
            image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": 'Analyze this image. Check whether it contains the text "be used as reference rates". Parse out the 3-letter ISO currency code from the second column. For instance `USD` from `USD/INR`. Provide a JSON response like the following structure:{"has_reference_rates": true or false, "headers": [<list of column headers>], "date": "<date as DD-MM-YYYY>", "time": "<time of publishing in HH:MM AM/PM format>", "forex_rates": [{"currency_code": "<currency short code>","rates": [83.57, 84.42, 83.50, 84.59, 83.50, 84.59, 82.55, 84.90]}]}',
                        },
                    ],
                }
            ]

            response = client.messages.create(
                model="claude-3-haiku-20240307", max_tokens=4096, messages=messages
            )

            try:
                response_json = json.loads(response.content[0].text)
                if response_json.get("has_reference_rates"):
                    if response_json.get("headers")[1:] == TABLE_COLUMNS:
                        date_str = response_json["date"]
                        time_str = response_json["time"]

                        date_time_str = f"Date: {date_str}\nTime: {time_str}"
                        extracted_date_time = extract_date_time(date_time_str)

                        logger.info(f"Successfully extracted data from image: {extracted_date_time}")
                        return extracted_date_time, response_json["forex_rates"]
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse Claude response for page {page_num + 1}: {e}")
                continue

    except Exception as e:
        logger.error(f"Error in image processing: {e}")
        raise

    raise ValueError("Unable to extract reference rates from images")


def process_content(
    file_content: io.BytesIO, save_file: bool = False, output_dir: Optional[str] = None
) -> None:
    """Process the content, extracting data and saving to CSV."""
    try:
        logger.info("Attempting to extract text from PDF")
        reader = PyPDF2.PdfReader(file_content, strict=False)
        text = reader.pages[0].extract_text()
        file_creation_date = reader.metadata.creation_date if reader.metadata else None
        extracted_date_time = extract_date_time(text, file_creation_date)
        reference_page = None
        for page in reader.pages[:2]:
            page_text = page.extract_text()
            if "to be used as reference rates" in page_text.lower():
                reference_page = page_text
                break

        if not reference_page:
            raise ValueError(
                "Text about reference rates not found on the first two pages."
            )

        rates_data = extract_currency_rates(reference_page)
        logger.info("Successfully extracted data using text parsing")
    except Exception as e:
        logger.warning(f"Failed to process PDF using text extraction: {e}. Attempting to process as image.")
        extracted_date_time, rates_data = process_as_image(file_content)

        if not rates_data:
            logger.error("No rates were parsed from either text or image processing.")
            raise ValueError("No rates were found.")

    logger.info(f"Successfully parsed date time {extracted_date_time} and {len(rates_data)} currency rates.")

    if save_file:
        save_pdf_file(file_content, extracted_date_time, output_dir)

    save_to_csv(rates_data, extracted_date_time, output_dir)


def parse_historical_data(
    directory: str, save_file: bool = True, output_dir: Optional[str] = None
) -> None:
    """Parse historical PDF files in the given directory."""
    all_pdfs = sorted(glob.glob(os.path.join(directory, "**/*.pdf"), recursive=True))
    logger.info(f"Found {len(all_pdfs)} PDF files to process")
    
    for file_path in all_pdfs:
        logger.info(f"Parsing {file_path}")
        with open(file_path, "rb") as f:
            file_content = io.BytesIO(f.read())
            try:
                process_content(file_content, save_file, output_dir)
            except Exception:
                logger.exception(f"Error processing {file_path}")


def main():
    """Main function to download and process the latest PDF"""
    logger.info("Starting SBI Forex Rates Downloader")
    try:
        file_content = get_latest_pdf_from_sbi()
        process_content(file_content, save_file=True)
        logger.info("Successfully completed forex rates download and processing")
    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
