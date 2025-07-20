import csv
from sqlite3 import IntegrityError
import asyncio
from functools import partial
import requests
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import execute_values
import time
from collections import deque
from config import (
    DB_CONFIG, HEADERS, PHONE_REGEX,
    ADDRESS_KEYWORDS, LOCATION_KEYWORDS,
    TIMEOUT, TABLE_NAMES,
    COMPANY_DETAILS_COLUMNS,
    INITIAL_URLS_CSV_PATH,
    MAX_DEPTH_PER_DOMAIN,
    FORBIDDEN_EXTENSIONS,
    HTTPS_URL, HTTP_URL,
    CHUNK_SIZE
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
        names TEXT[] UNIQUE NOT NULL
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

def save_company(cursor, initial_url):
    cursor.execute(
        f"SELECT id FROM {COMPANIES_TBL} WHERE %s = ANY(names);",
        (initial_url,)
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        f"INSERT INTO {COMPANIES_TBL} (names) VALUES (ARRAY[%s]) RETURNING id;",
        (initial_url,)
    )
    return cursor.fetchone()[0]

def update_company_name(cursor, company_id, title):
    try:
        cursor.execute(
            f"""
            UPDATE {COMPANIES_TBL}
            SET names = array_append(names, %s)
            WHERE id = %s
              AND NOT (%s = ANY(names))
            RETURNING names;
            """,
            (title, company_id, title)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except IntegrityError:
        return None

def update_company_names_bulk(cursor, company_id, titles):
    """
    Appends multiple titles to a company's names array in bulk,
    avoiding duplicates.
    """
    if not titles:
        return  # nothing to update

    try:
        sql = f"""
        UPDATE {COMPANIES_TBL}
        SET names = (
            SELECT array_agg(DISTINCT elem)
            FROM unnest(names || %s) AS elem
        )
        WHERE id = %s
        RETURNING names;
        """
        cursor.execute(sql, (list(titles), company_id))
        row = cursor.fetchone()
        if row:
            print(f"Updated titles for company_id {company_id}: {row[0]}")
            return row[0]
        return None
    except IntegrityError:
        return None

def save_detail(cursor, company_id, detail_type, detail_value):
    cursor.execute(
        f"INSERT INTO {DETAILS_TBL} (company_id, detail_type, detail_value) VALUES (%s, %s, %s) "
        "ON CONFLICT (company_id, detail_type, detail_value) DO NOTHING;",
        (company_id, detail_type, detail_value)
    )

def save_details_bulk(cursor, company_id, detail_type, detail_values):
    if not detail_values:
        return
    records = [(company_id, detail_type, val) for val in detail_values]
    sql = (
        f"INSERT INTO {DETAILS_TBL} (company_id, detail_type, detail_value) "
        "VALUES %s "
        "ON CONFLICT (company_id, detail_type, detail_value) DO NOTHING;"
    )
    execute_values(cursor, sql, records)

def save_link(cursor, company_id, url, reached=False):
    cursor.execute(
        f"INSERT INTO {URLS_TBL} (company_id, url, reached) VALUES (%s, %s, %s) "
        "ON CONFLICT (company_id, url) DO UPDATE SET reached = EXCLUDED.reached;",
        (company_id, url, reached)
    )

def discover_new_links(soup, queue, seen):
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href not in seen:
            seen.add(href)
            if (href.startswith("http")
                    and '../' not in href
                    and '..' not in href
                    and (href.count('.com') <= 1)):
                queue.append(href)

def clean_text(txt):
    txt = txt.replace('\n', ' ').replace('\r', ' ').strip()
    return ' '.join(txt.split())

def extract_phone(soup):
    text = soup.get_text(separator=' ')
    text = clean_text(text)
    candidates = set(PHONE_REGEX.findall(text))
    return [c for c in candidates if 9 <= sum(ch.isdigit() for ch in c) <= 15]

def extract_addresses_locations(soup):
    addresses = set()
    locations = set()
    tags = ['p', 'div', 'span']
    tags_found = soup.find_all(tags)
    if tags_found:
        for tag in tags_found:
            txt = clean_text(tag.get_text(separator=' '))
            if any(word in txt.lower() for word in ADDRESS_KEYWORDS) and 7 < len(txt) < 80:
                addresses.add(txt)
            if any(word in txt.lower() for word in LOCATION_KEYWORDS) and 2 < len(txt) < 40:
                locations.add(txt)
    return addresses, locations

def extract_title(soup):
    results = set()
    for tag in soup.find_all(['title']):
        txt = clean_text(tag.get_text(separator=' '))
        if 2 < len(txt) < 35:
            results.add(txt)
    return results

def scrape_company(initial_url, cursor):
    try:
        name = initial_url.split('.')[0]
        company_id = save_company(cursor, name)
        queue = deque([])
        seen = {initial_url}

        depth = 1
        reached = process_url(cursor, company_id, initial_url, queue, seen)
        if not reached:
            if initial_url.startswith(HTTPS_URL):
                http_initial_url = initial_url.replace(HTTPS_URL, HTTP_URL)
                reached_with_http = process_url(cursor, company_id, http_initial_url, queue, seen)
                if reached_with_http:
                    print(f"Failed to reach https, but http reached for url: '{http_initial_url}'.")
                else:
                    print(f"Failed to reach both https and http for url: '{initial_url}'.")
                    return
        while queue and depth <= MAX_DEPTH_PER_DOMAIN:
            depth += 1
            item = queue.popleft()
            _ = process_url(cursor, company_id, item, queue, seen)
    except Exception as e:
        print(f"Unexpected error while scrape_company method was  running for initial_url: {initial_url}.'\n Error: {e}")
        return
    finally:
        print(f"Completed scraping for initial_url: '{initial_url}'. \n")

def process_url(cursor, company_id, url, queue, seen) -> bool:
    reached_url = False
    try:
        print('Processing url: ' + url)

        if url.endswith(FORBIDDEN_EXTENSIONS):
            save_link(cursor, company_id, url, reached=reached_url)
            print(f"Skipping archive file: {url}")
            print(f"Scraping for link: '{url}' completed, reached: '{reached_url}'.")
            return reached_url

        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if response.status_code == 200:
            reached_url = True
            content = response.content.decode('utf-8', errors='replace')

            content_type = response.headers.get('Content-Type', '').lower()
            if 'xml' in content_type or 'xhtml' in content_type or content.strip().startswith('<?xml'):
                soup = BeautifulSoup(content, features="xml")
            else:
                soup = BeautifulSoup(content, 'lxml')

            titles = extract_title(soup)
            if titles:
                update_company_names_bulk(cursor, company_id, titles)

            phone_nrs = extract_phone(soup)
            if phone_nrs:
                save_details_bulk(cursor, company_id, PHONE_CL, phone_nrs)
            addresses, locations = extract_addresses_locations(soup)
            if addresses:
                save_details_bulk(cursor, company_id, ADDRESS_CL, addresses)
            if locations:
                save_details_bulk(cursor, company_id, LOCATION_CL, locations)

            discover_new_links(soup, queue, seen)
        else:
            print(f"Failed to retrieve webpage. Status code: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"Error: Failed to connect to {url}. The site may be down.")
    except requests.exceptions.Timeout:
        print(f"Error: Timeout occurred while trying to reach {url}.")
    except requests.exceptions.RequestException as e:
        print(f"HTTP error scraping {url}: {e}")
    except Exception as e:
        print(f"Unexpected error while processing {url}: {e}")

    save_link(cursor, company_id, url, reached=reached_url)
    print(f"Scraping for link: '{url}' completed, reached: '{reached_url}'.")
    return reached_url


class StopWatch:
    def __init__(self):
        self._start = None
        self._elapsed = 0

    def start(self):
        if self._start is None:
            self._start = time.perf_counter()
            print("Stopwatch started.")
        else:
            print("Stopwatch is already running.")

    def stop(self):
        if self._start is not None:
            self._elapsed += time.perf_counter() - self._start
            self._start = None
            print(f"Stopwatch stopped. Elapsed: {self.format_time(self._elapsed)}")
        else:
            print("Stopwatch is not running.")

    def reset(self):
        self._start = None
        self._elapsed = 0
        print("Stopwatch reset.")

    def elapsed(self):
        total_seconds = self._elapsed
        if self._start is not None:
            total_seconds += (time.perf_counter() - self._start)
        return self.format_time(total_seconds)

    @staticmethod
    def format_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"




async def process_domain(domain):
    if domain.startswith(HTTP_URL):
        domain = domain.replace(HTTP_URL, HTTPS_URL)
    elif not domain.startswith(HTTPS_URL):
        domain = HTTPS_URL + domain

    conn, cursor = connect_db()
    try:
        await asyncio.to_thread(scrape_company, domain, cursor)
    finally:
        cursor.close()
        conn.close()


async def main_async(initial_domains, db_config):
    sw = StopWatch()
    sw.start()
    try:
        total_domains = len(initial_domains)
        if total_domains == 0:
            print('No company urls provided.')
            return

        # Split domains into chunks
        for i in range(0, total_domains, CHUNK_SIZE):
            chunk = initial_domains[i:i+CHUNK_SIZE]
            print(f"Processing domains {i+1} to {i+len(chunk)} of {total_domains}")

            # Create coroutine tasks for this chunk
            tasks = [
                process_domain(domain, db_config)
                for domain in chunk
            ]

            # Run all coroutines in this chunk concurrently
            await asyncio.gather(*tasks)
            print(f"Elapsed time since start: {sw.elapsed()}")

    except Exception as e:
        print(f"Total elapsed time: {sw.elapsed()}. Script managed to close safely, even though it was terminated abruptly.")
        print(f"Exception: {e}")
    finally:
        sw.stop()
        print(f"Total elapsed time: {sw.elapsed()}")


if __name__ == '__main__':
    initial_domains = load_initial_urls()
    db_config = DB_CONFIG
    asyncio.run(main_async(initial_domains, db_config))


