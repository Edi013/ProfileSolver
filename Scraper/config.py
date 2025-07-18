import re

DB_CONFIG = {
    'dbname': 'CompaniesDataDb',  # os.getenv('DB_NAME', 'ScraperDb'),
    'user': 'postgres',     # os.getenv('DB_USER', 'postgres'),
    'password': '1234',     # os.getenv('DB_PASSWORD', '1234'),
    'host': 'localhost',    # os.getenv('DB_HOST', 'localhost'),
    'port': '5432',         # os.getenv('DB_PORT', '5432'),
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
)

PHONE_REGEX = re.compile(r"(?:\+\d{1,3}[\s-]?)?(?:\(\d+\)[\s-]?)?\d[\d\s-]{7,}\d")

ADDRESS_KEYWORDS = ['street', 'st.', 'ave', 'road', 'rd.', 'zip', 'city', 'state', 'postcode', 'hood', 'home']

LOCATION_KEYWORDS = [
    'city', 'country', 'state', 'province', 'region', 'sector',
    'district', 'territory', 'municipality', 'area', 'village'
]

TIMEOUT = 5  # seconds for HTTP requests

# Database table names as a list: 0 - companies, 1 - company_details, 2 - urls
TABLE_NAMES = ['companies', 'company_details', 'urls']

# Columns in company_details table
COMPANY_DETAILS_COLUMNS = ['phone', 'address', 'location']

# Number of search results to fetch
SEARCH_RESULT_COUNT = 5

# default CSV file for initial URLs / social domains
INITIAL_URLS_CSV_PATH = 'sample-websites.csv'

MAX_DEPTH_PER_DOMAIN = 25
