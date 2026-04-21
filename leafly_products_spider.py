import requests
import pandas as pd
import sqlite3
from datetime import datetime
import time

# SQLite Database file
db_file = "leafly_products.db"

# URL for fetching dispensary data
url = 'https://finder-service.leafly.com/v3/dispensaries?filter[]=dispensary&geo_query_type=bounding-box&promote_new_stores=true&lat=40.7830603&limit=50&lon=-73.9712488&page=1&return_facets=true&sort=default&sort_version=default&bounding_box=-74.02703040758556,40.694155396782236,-73.9386247984547,40.81197036940975'

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
}

# Session to maintain cookies
session = requests.Session()

# Fetch data from Leafly API
def fetch_dispensary_data():
    response = session.get(url, headers=headers)
    return response.json()

def save_to_sqlite(df, db_file, table_name="leafly_products"):
    """Save product data to SQLite, allowing duplicates."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Create table if it doesn't exist (no UNIQUE constraint on product_id)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            product_id TEXT,
            product_name TEXT,
            category TEXT,
            subcategory TEXT,
            brand TEXT,
            thc_percentage REAL,
            price REAL,
            quantity INTEGER,
            product_updated_at TEXT,
            description TEXT,
            image_url TEXT,
            retailer_name TEXT
        )
    """)

    # Insert data without deduplication
    for _, row in df.iterrows():
        cursor.execute(f"""
            INSERT INTO {table_name} (
                timestamp, product_id, product_name, category, subcategory, brand,
                thc_percentage, price, quantity, product_updated_at, description,
                image_url, retailer_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["timestamp"], row["product_id"], row["product_name"], row["category"],
            row["subcategory"], row["brand"], row["thc_percentage"], row["price"],
            row["quantity"], row["product_updated_at"], row["description"],
            row["image_url"], row["retailer_name"]
        ))

    conn.commit()
    conn.close()


# Main logic to fetch and save products
def fetch_and_save_products():
    results = fetch_dispensary_data()

    # Extract data for all stores
    store_data_list = []
    for store in results['stores']:
        store_data = {
            "name": store.get("name"),
            "slug": store.get("slug"),
        }
        store_data_list.append(store_data)

    store_df = pd.DataFrame(store_data_list)

    all_products = []
    timestamp = datetime.utcnow().strftime('%Y-%m-%d-%H')  # Timestamp with hour

    # Function to handle retries with exponential backoff
    def fetch_with_retries(url, max_retries=5):
        retry_count = 0
        while retry_count < max_retries:
            response = session.get(url, headers=headers, timeout=10)
            if response.status_code == 429:
                retry_count += 1
                delay = min(2 ** retry_count, 60)
                print(f"Rate limit hit. Retrying after {delay} seconds...")
                time.sleep(delay)
            else:
                return response
        print(f"Failed after {max_retries} retries.")
        return None

    # Loop through each store slug
    for slug in store_df['slug']:
        print(f"Fetching products for slug: {slug}")
        skip = 0
        take = 18

        while True:
            menu_url = f'https://consumer-api.leafly.com/api/dispensaries/v1/{slug}/menu_items?enableNewFilters=true&skip={skip}&take={take}'
            response = fetch_with_retries(menu_url)

            if not response or response.status_code != 200:
                print(f"Failed to fetch menu items for slug {slug}.")
                break

            menu_results = response.json()
            menu_items = menu_results.get('data', [])

            if not menu_items:
                break

            for item in menu_items:
                brand_data = item.get("brand")  # Fetch brand data first
                brand_name = brand_data.get("name", "Unknown") if brand_data else "Unknown"  # Check for None

                all_products.append({
                    "timestamp": timestamp,
                    "product_id": item.get("id"),
                    "product_name": item.get("name"),
                    "category": item.get("productCategory"),  # Corrected to top-level
                    "subcategory": item.get("subCategory", "N/A"),  # Default to "N/A" if not found
                    "brand": brand_name,
                    "thc_percentage": item.get("thcContent"),
                    "price": item.get("price"),
                    "quantity": item.get("stockQuantity"),
                    "product_updated_at": item.get("updatedAt", "N/A"),
                    "description": item.get("description"),
                    "image_url": item.get("imageUrl"),
                    "retailer_name": item.get("dispensary", {}).get("name", "Unknown"),
                })

            skip += take
            total_count = menu_results.get('metadata', {}).get('totalCount', 0)
            if skip >= total_count:
                break

    # Convert to DataFrame and save to SQLite
    product_df = pd.DataFrame(all_products)
    save_to_sqlite(product_df, db_file)
    print(f"Saved {len(product_df)} products to {db_file}")

if __name__ == "__main__":
    fetch_and_save_products()
