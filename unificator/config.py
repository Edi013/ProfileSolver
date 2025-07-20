DB_CONFIG = {
    'dbname': 'CompaniesDataDb',  # os.getenv('DB_NAME', 'ScraperDb'),
    'user': 'postgres',     # os.getenv('DB_USER', 'postgres'),
    'password': '1234',     # os.getenv('DB_PASSWORD', '1234'),
    'host': 'localhost',    # os.getenv('DB_HOST', 'localhost'),
    'port': '5432',         # os.getenv('DB_PORT', '5432'),
}

CSV_PATH = 'sample-websites-company-names.csv'
COMPANIES_TABLE = 'companies'
DETAILS_TABLE = 'company_details'

DETAIL_COLUMNS = [
    'company_commercial_name',
    'company_legal_name',
    'company_all_available_names',
]