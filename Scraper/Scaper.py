import csv
from sqlite3 import IntegrityError

import requests
from bs4 import BeautifulSoup
import psycopg2
import time
from collections import deque
from config import (
    DB_CONFIG, HEADERS, PHONE_REGEX,
    ADDRESS_KEYWORDS, LOCATION_KEYWORDS,
    TIMEOUT, TABLE_NAMES,
    COMPANY_DETAILS_COLUMNS,
    INITIAL_URLS_CSV_PATH,
    MAX_DEPTH_PER_DOMAIN,
    ARCHIVE_EXTENSIONS
)


MAX_DEPTH_PER_COMPANY = MAX_DEPTH_PER_DOMAIN * 10

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
        f"INSERT INTO {COMPANIES_TBL} (names) VALUES (ARRAY[%s]) "
        "ON CONFLICT (names) DO NOTHING RETURNING id;",
        (initial_url,)
    )
    res = cursor.fetchone()
    if res:
        return res[0]
    cursor.execute(
        f"SELECT id FROM {COMPANIES_TBL} WHERE %s = ANY(names);",
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

def extract_phone(soup):
    text = soup.get_text(separator=' ')
    return set(PHONE_REGEX.findall(text))

def extract_links(soup, queue, seen):
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href not in seen:
            seen.add(href)
            if (href.startswith("http://") or href.startswith("https://") or href.startswith(
                    "www")) and '../' not in href \
                    and '..' not in href and (href.count('.com') < 1):
                queue.append(href)

def extract_address(soup):
    results = set()
    for tag in soup.find_all(['address', 'p', 'div', 'span']):
        txt = tag.get_text(separator=' ').strip()
        if any(word in txt.lower() for word in ADDRESS_KEYWORDS) and 10 < len(txt) < 50:
            results.add(txt)
    return results

def extract_location(soup):
    results = set()
    for tag in soup.find_all(['p', 'div', 'span']):
        txt = tag.get_text(separator=' ').strip()
        if any(word in txt.lower() for word in LOCATION_KEYWORDS) and 5 < len(txt) < 100:
            results.add(txt)
    return results

def extract_title(soup):
    results = set()
    for tag in soup.find_all(['title']):
        txt = tag.get_text(separator=' ').strip()
        if 2 < len(txt) < 60:
            results.add(txt)
    return results

def scrape_company(initial_url, cursor):
    try:
        new_name = initial_url.split('.')[0]
        company_id = save_company(cursor, new_name)
        if not (initial_url.startswith('http://') or initial_url.startswith('https://') or initial_url.startswith('www.')):
            initial_url = 'https://' + initial_url
        url = initial_url
        queue = deque([url])
        seen = {url}

        depth = 1
        while queue and depth < MAX_DEPTH_PER_DOMAIN:
            item = queue.popleft()
            print('Processing url: ' + item + '\n')
            process_url(cursor, company_id, item, queue, seen)
            depth = depth + 1
    except Exception as e:
        print(f"Unexpected error while scrape_company method was  running for initial_url: {initial_url}.'\n Error: {e}")
        return
    finally:
        print(f"Scraping for initial_url: '{initial_url}' completed.")

def process_url(cursor, company_id, url, queue, seen):
    reached_url = False
    try:
        if url.endswith(ARCHIVE_EXTENSIONS):
            print(f"Skipping archive file: {url}")
            return

        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if response.status_code == 200:
            reached_url = True
            content = response.content.decode('utf-8', errors='replace')

            content_type = response.headers.get('Content-Type', '').lower()
            if 'xml' in content_type or 'xhtml' in content_type or content.strip().startswith('<?xml'):
                soup = BeautifulSoup(content, features="xml")
            else:
                soup = BeautifulSoup(content, 'lxml')

            titles = set(extract_title(soup))
            for title in titles:
                print(f"Updated title for company_id: {company_id}; title: {title}")
                update_company_name(cursor, company_id, title)

            for p in extract_phone(soup):
                save_detail(cursor, company_id, PHONE_CL, p)
            for a in extract_address(soup):
                save_detail(cursor, company_id, ADDRESS_CL, a)
            for loc in extract_location(soup):
                save_detail(cursor, company_id, LOCATION_CL, loc)
            extract_links(soup, queue, seen)
        else:
            print(f"Failed to retrieve the webpage. Status code: {response.status_code}")
            return

    except requests.exceptions.ConnectionError:
        print(f"Error: Failed to connect to {url}. The site may be down.")
        return
    except requests.exceptions.Timeout:
        print(f"Error: Timeout occurred while trying to reach {url}.")
        return
    except requests.exceptions.RequestException as e:
        print(f"HTTP error scraping {url}: {e}")
        return
    except Exception as e:
        print(f"Unexpected error while processing {url}: {e}")
        return
    finally:
        save_link(cursor, company_id, url, reached=reached_url)
        print(f"Scraping for link: '{url}' completed, reached: '{reached_url}'.")



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



if __name__ == '__main__':
    initial_domains = load_initial_urls()
    conn, cursor = connect_db()
    sw = StopWatch()
    sw.start()
    try:
        if initial_domains:
            for domain in initial_domains:
                scrape_company(domain, cursor)
                print(f"Elapsed time since start: {sw.elapsed()}")
        else:
            print('No company urls provided.')
    except Exception as e:
        print(f"Unexpected error in main method, initial domains count = {initial_domains.__sizeof__()}.\n Error: {e}")
        print(f"Total elapsed time: {sw.elapsed()}. Script managed to close safely, even though it was terminated abruptly.")
    finally:
        cursor.close()
        conn.close()
    sw.stop()
    print(f"Total elapsed time: {sw.elapsed()}")

