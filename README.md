# SBI Forex Card Rates Downloader

This repository automatically downloads SBI Forex card rates PDFs at scheduled times (11 AM, 1 PM, 5 PM, and 6 PM IST) and saves them if they are new.

## How It Works

1. The Python script (`sbi_forex_downloader.py`) checks SBI's website for the latest forex card rates.
2. It compares the hash of the downloaded PDF with the previously saved hash to determine if it's a new file.
3. It also extracts the date and time from the PDF to ensure the content is new.
4. If a new PDF is detected, it saves it with a filename that includes the date and time.
5. GitHub Actions runs this script at the specified times automatically.

## Repository Structure

- `sbi_forex_downloader.py`: The main Python script that downloads the forex rates PDFs.
- `.github/workflows/github_workflow.yml`: The GitHub Actions workflow configuration file.
- `downloads/`: Directory where downloaded PDFs are stored.
- `data/`: Directory for storing metadata like the last file hash and date.
- `sbi_forex_downloader.log`: Log file capturing the script's execution details.

## Dependencies

- Python 3.6+
- Required Python packages:
  - requests
  - PyPDF2

## Manual Run

You can also manually trigger the workflow by going to the Actions tab in the GitHub repository and selecting "Run workflow".

## Setup Instructions

Refer to the detailed setup instructions below to create your own copy of this repository.
