import psycopg2
from elasticsearch import Elasticsearch, helpers

DB_CONFIG = {
    'dbname': 'CompaniesDataDb',  # os.getenv('DB_NAME', 'ScraperDb'),
    'user': 'postgres',     # os.getenv('DB_USER', 'postgres'),
    'password': '1234',     # os.getenv('DB_PASSWORD', '1234'),
    'host': 'localhost',
    'port': '5432',
}

# Elasticsearch settings
ES_HOST = "http://localhost:9200"
ES_INDEX = "companies"


def fetch_companies_with_details_and_urls(cursor):
    # Query to join companies, details and urls
    cursor.execute("""
                   SELECT c.id as company_id,
                          c.names,
                          d.detail_type,
                          d.detail_value,
                          u.url,
                          u.reached
                   FROM companies c
                            LEFT JOIN company_details d ON d.company_id = c.id
                            LEFT JOIN urls u ON u.company_id = c.id
                   ORDER BY c.id;
                   """)

    rows = cursor.fetchall()
    return rows


def transform_data(rows):
    companies = {}
    for row in rows:
        company_id = row[0]
        names = row[1]
        detail_type = row[2]
        detail_value = row[3]
        url = row[4]
        reached = row[5]

        if company_id not in companies:
            companies[company_id] = {
                'company_id': company_id,
                'names': names,
                'email': None,
                'phone': None,
                'website': None,
                'facebook_profile': None,
                'urls': []
            }

        # Map details to fields
        if detail_type and detail_value:
            if detail_type == 'email':
                companies[company_id]['email'] = detail_value
            elif detail_type == 'phone':
                companies[company_id]['phone'] = detail_value
            elif detail_type == 'website':
                companies[company_id]['website'] = detail_value
            elif detail_type == 'facebook_profile':
                companies[company_id]['facebook_profile'] = detail_value

        # Add urls (exclude reached = false if you want)
        if url and reached:
            companies[company_id]['urls'].append({
                'url': url,
                'reached': reached
            })

    return list(companies.values())


def index_to_elasticsearch(es_client, companies):
    actions = [
        {
            "_index": ES_INDEX,
            "_id": c['company_id'],
            "_source": c
        }
        for c in companies
    ]

    helpers.bulk(es_client, actions)
    print(f"Indexed {len(companies)} companies to Elasticsearch.")


def main():
    # Connect to Postgres
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Fetch data
    print(f"Fetch data started---")
    rows = fetch_companies_with_details_and_urls(cursor)
    print(f"Fetch data ended------")

    # Transform data
    print(f"Transform data started---")
    companies = transform_data(rows)
    print(f"Fetch data ended------")

    # Connect to Elasticsearch
    print("Connect to ES started---")
    es = Elasticsearch(ES_HOST)
    print("Connect to ES ended-----")

    # Index data
    print("Index started---")
    index_to_elasticsearch(es, companies)
    print("Index ended-----")

    # Cleanup
    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
