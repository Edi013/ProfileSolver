import re

DB_CONFIG = {
    'dbname': 'CompaniesDataDb',  # os.getenv('DB_NAME', 'ScraperDb'),
    'user': 'postgres',     # os.getenv('DB_USER', 'postgres'),
    'password': '1234',     # os.getenv('DB_PASSWORD', '1234'),
    'host': 'localhost',    # os.getenv('DB_HOST', 'localhost'),
    'port': '5432',         # os.getenv('DB_PORT', '5432'),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

# optional + at start,  7–20 groups of digit + optional separator, must end with digit
# PHONE_REGEX = re.compile(r"^\+?(?:\d[\s\-().]?){7,20}\d$")

PHONE_REGEX = re.compile(
    r"""
    (?<!\w)
    (?:\+?\d{1,3}[\s\-\.()]*)?
    (?:\(?\d{2,4}\)?[\s\-\.()]*){2,5}
    \d{2,4}
    (?!\w)
    """,
    re.VERBOSE
)



ADDRESS_KEYWORDS = [
    'address', 'add', 'adr', 'street', 'number', 'st', 'ave', 'avenue', 'road', 'boulevard', 'blvd',
    'unit', 'block', 'floor', 'building','drive', 'zip', 'postcode', 'postal code', 'suite', 'apt',
    'no', 'house'
]

LOCATION_KEYWORDS = [
    'city', 'country', 'province', 'region', 'sector',
    'district', 'territory', 'municipality', 'area', 'village',
    'metropolitan', 'county', 'island', 'state',
]

TIMEOUT = 3  # seconds for HTTP requests

# Database table names as a list: 0 - companies, 1 - company_details, 2 - urls
TABLE_NAMES = ['companies', 'company_details', 'urls']

# Columns in company_details table
COMPANY_DETAILS_COLUMNS = ['phone', 'address', 'location']

# default CSV file for initial URLs / social domains
INITIAL_URLS_CSV_PATH = 'sample-websites.csv'

MAX_DEPTH_PER_DOMAIN = 5

ARCHIVE_EXTENSIONS = ('.zip', '.tar.gz', '.tar', '.gz', '.rar', '.7z')

