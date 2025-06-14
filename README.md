# SBI Forex Rates Downloader

A Python script to download forex rates from State Bank of India (SBI).

## Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

### Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/rahulmohamw/sbi-forex-rates-downloader.git
   cd sbi-forex-rates-downloader
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the script:**
   ```bash
   python sbi_forex_downloader.py
   ```

## Dependencies

This project requires the following Python packages:
- python-dateutil: For date parsing and manipulation
- requests: For HTTP requests
- beautifulsoup4: For web scraping
- pandas: For data manipulation
- lxml: For XML/HTML parsing

## Troubleshooting

If you encounter `ModuleNotFoundError`, ensure all dependencies are installed:
```bash
pip install python-dateutil requests beautifulsoup4 pandas lxml
```
