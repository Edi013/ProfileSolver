import csv
import psycopg2
from psycopg2.extras import execute_values
from config import DB_CONFIG

from config import(
    CSV_PATH, COMPANIES_TABLE, DETAILS_TABLE, DETAIL_COLUMNS
)

def connect_db():
    """
    Establish and return a new database connection and cursor.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    return conn, conn.cursor()

already_exists_contor = 0
def merge_row(cursor, domain, details):
    global already_exists_contor
    """
    For a given domain and detail dict, find or create the company,
    then insert each detail into the details table using LIKE matching for domain.

    :param cursor: psycopg2 cursor
    :param domain: string domain to match against companies.names
    :param details: dict mapping detail_type to detail_value
    :return: None
    """
    # Prepare pattern for LIKE search (match domain substring)
    pattern = f"%{domain}%"

    # 1) Look up existing company by domain in names array using LIKE
    cursor.execute(
        f"""
        SELECT id FROM {COMPANIES_TABLE}
        WHERE EXISTS (
            SELECT 1 FROM unnest(names) AS nm
            WHERE nm LIKE %s
        )
        LIMIT 1;
        """,
        (pattern,)
    )
    already_exists = False
    row = cursor.fetchone()
    if row:
        already_exists = True
        already_exists_contor +=1
        company_id = row[0]
    else:
        # 2) Insert new company with names = [domain]
        cursor.execute(
            f"INSERT INTO {COMPANIES_TABLE}(names) VALUES (ARRAY[%s]) RETURNING id;",
            (domain,)
        )
        company_id = cursor.fetchone()[0]
    print(f"Already exists {already_exists}")
    # 3) Upsert each detail
    ## use this to append it to names array in company table
    for d_type, d_value in details.items():
        if not d_value:
            continue
        # Only append if value not already present
        cursor.execute(
            f"""
                UPDATE {COMPANIES_TABLE}
                SET names = array_append(names, %s)
                WHERE id = %s
                  AND NOT (%s = ANY(names));
                """,
            (d_value, company_id, d_value)
        )

    ## use this if you want to append it to the company_details as a detail_type, detail_value pair
    # for d_type, d_value in details.items():
    #     if not d_value:
    #         continue
    #     sql = (
    #         f"INSERT INTO {DETAILS_TABLE}"
    #         "(company_id, detail_type, detail_value) "
    #         "VALUES (%s, %s, %s) "
    #         "ON CONFLICT (company_id, detail_type, detail_value) DO NOTHING;"
    #     )
    #     cursor.execute(sql, (company_id, d_type, d_value))


def main():
    conn, cur = connect_db()
    try:
        with open(CSV_PATH, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                domain = row.get('domain', '').strip()
                print(f"Merging domain {domain}")
                if not domain:
                    continue
                details = {col: row.get(col, '').strip() for col in DETAIL_COLUMNS}
                merge_row(cur, domain, details)
        conn.commit()
        print("CSV merge completed successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Error during merge: {e}")
    finally:
        print(f"END - Matched {already_exists_contor} companies")
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
