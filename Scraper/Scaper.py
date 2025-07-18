import csv
import requests
from bs4 import BeautifulSoup
import psycopg2
from config import (
    DB_CONFIG, USER_AGENT, PHONE_REGEX,
    ADDRESS_KEYWORDS, LOCATION_KEYWORDS, SOCIAL_DOMAINS,
    TIMEOUT, TABLE_NAMES, SEARCH_RESULT_COUNT,
    COMPANY_DETAILS_COLUMNS,
    INITIAL_URLS_CSV_PATH
)

# Indices for TABLE_NAMES
COMPANIES_TBL = TABLE_NAMES[0]
DETAILS_TBL = TABLE_NAMES[1]
URLS_TBL = TABLE_NAMES[2]

# Indices for COMPANY_DETAILS_COLUMNS
PHONE_CL = COMPANY_DETAILS_COLUMNS[0]
ADDRESS_CL = COMPANY_DETAILS_COLUMNS[1]
LOCATION_CL = COMPANY_DETAILS_COLUMNS[2]

def connect_db():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    return conn, conn.cursor()

def init_schema(cursor):
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS {COMPANIES_TBL} (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    );
    CREATE TABLE IF NOT EXISTS {DETAILS_TBL} (
        id SERIAL PRIMARY KEY,
        company_id INT NOT NULL REFERENCES {COMPANIES_TBL}(id) ON DELETE CASCADE,
        detail_type TEXT NOT NULL,
        detail_value TEXT NOT NULL,
        UNIQUE(company_id, detail_type, detail_value)
    );
    CREATE TABLE IF NOT EXISTS {URLS_TBL} (
        id SERIAL PRIMARY KEY,
        company_id INT NOT NULL REFERENCES {COMPANIES_TBL}(id) ON DELETE CASCADE,
        url TEXT NOT NULL,
        reached BOOLEAN NOT NULL DEFAULT FALSE,
        UNIQUE(company_id, url)
    );
    """)

def load_initial_urls():
    domains = []
    try:
        with open(INITIAL_URLS_CSV_PATH, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                dom = row.get('domain')
                if dom:
                    domains.append(dom.strip())
    except FileNotFoundError:
        print(f"Warning: CSV not found at {INITIAL_URLS_CSV_PATH}, using default list.")
    return domains

def save_company(cursor, name):
    cursor.execute(
        f"INSERT INTO {COMPANIES_TBL} (name) VALUES (%s) "
        "ON CONFLICT (name) DO NOTHING RETURNING id;",
        (name,)
    )
    res = cursor.fetchone()
    if res:
        return res[0]
    cursor.execute(f"SELECT id FROM {COMPANIES_TBL} WHERE name=%s", (name,))
    return cursor.fetchone()[0]

def save_detail(cursor, company_id, detail_type, detail_value):
    cursor.execute(
        f"INSERT INTO {DETAILS_TBL} (company_id, detail_type, detail_value) VALUES (%s, %s, %s) "
        "ON CONFLICT (company_id, detail_type, detail_value) DO NOTHING;",
        (company_id, detail_type, detail_value)
    )

def save_link(cursor, company_id, url, reached=False):
    cursor.execute(
        f"INSERT INTO {URLS_TBL} (company_id, url, reached) VALUES (%s, %s, %s) "
        "ON CONFLICT (company_id, url) DO UPDATE SET reached = EXCLUDED.reached;",
        (company_id, url, reached)
    )

def fetch_search_results(query, num=SEARCH_RESULT_COUNT):
    headers = {'User-Agent': USER_AGENT}
    params = {'q': query, 'count': num}
    r = requests.get('https://www.bing.com/search', headers=headers, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'lxml')
    return [a['href'] for a in soup.select('li.b_algo h2 a[href]')]

def extract_phone(soup):
    text = soup.get_text(separator=' ')
    return set(PHONE_REGEX.findall(text))

def extract_social(soup, domains):
    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if any(dom in href for dom in domains):
            links.add(href)
    return links

def extract_address(soup):
    results = set()
    for tag in soup.find_all(['address', 'p', 'div', 'span']):
        txt = tag.get_text(separator=' ').strip()
        if any(word in txt.lower() for word in ADDRESS_KEYWORDS) and len(txt) > 20:
            results.add(txt)
    return results

def extract_location(soup):
    results = set()
    for tag in soup.find_all(['p', 'div', 'span']):
        txt = tag.get_text(separator=' ').strip()
        if any(word in txt.lower() for word in LOCATION_KEYWORDS) and 5 < len(txt) < 100:
            results.add(txt)
    return results

def scrape_company(name):
    domains = load_initial_urls() or SOCIAL_DOMAINS
    conn, cursor = connect_db()
    reached_url = False
    try:
        reached_url = False
        init_schema(cursor)
        company_id = save_company(cursor, name)
        urls = fetch_search_results(f"{name} official site")

        for url in urls:
            save_link(cursor, company_id, url, reached=reached_url)
            try:
                r = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=TIMEOUT)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, 'lxml')
                reached_url = True
                save_link(cursor, company_id, url, reached=reached_url)

                for p in extract_phone(soup):
                    save_detail(cursor, company_id, PHONE_CL, p)
                for s in extract_social(soup, domains):
                    save_link(cursor, company_id, s)
                for a in extract_address(soup):
                    save_detail(cursor, company_id, ADDRESS_CL, a)
                for loc in extract_location(soup):
                    save_detail(cursor, company_id, LOCATION_CL, loc)

            except requests.RequestException as e:
                print(f"HTTP error scraping {url}: {e}")
            except Exception as e:
                print(f"Error processing {url}: {e}")
    finally:
        cursor.close()
        conn.close()
        print(f"Scraping for '{name}' completed, reached: '{reached_url}'.")

if __name__ == '__main__':
    company = input('Enter company name: ').strip()
    if company:
        scrape_company(company)
    else:
        print('No company name provided.')
