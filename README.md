# Cannabis Market Analyzer

A Plotly Dash analytics dashboard for the cannabis retail market, built on scraped Leafly data. Tracks product inventory, revenue, pricing, discounts, and dispensary locations across NYC-area retailers — surfacing sales trends and market intelligence for the legal cannabis industry.

---

## What It Does

1. **Scrapes** dispensary listings and product menus from Leafly's API on a recurring schedule
2. **Infers sales** from inventory quantity changes between scrapes — when stock decreases, the difference is counted as units sold
3. **Renders** a multi-page interactive dashboard with revenue, stock, pricing, and discount analytics

---

## Data Pipeline

```
leafly_products_spider.py (run on schedule)
        ↓
Hits Leafly finder API → gets all dispensary slugs in NYC bounding box
        ↓
For each dispensary slug → hits menu API → gets all products with price + stock quantity
        ↓
Saves to leafly_products.db (SQLite) with timestamp — duplicates allowed for tracking
        ↓
cannabis.py dashboard
        ↓
Loads full history → calculates stock diffs → infers sales + revenue → renders charts
```

---

## Scraper — `leafly_products_spider.py`

Scrapes all dispensary product menus within a NYC bounding box.

**How it works:**
1. Calls Leafly's finder API to get all dispensary slugs in a geographic area
2. For each dispensary, paginates through the full menu (18 items per page)
3. Captures product name, category, brand, THC%, price, stock quantity, and image
4. Saves every scrape as a new row — no deduplication, so quantity changes are trackable over time
5. Includes exponential backoff retry logic for rate limiting (429 responses)

**Fields captured:**
- `product_id`, `product_name`, `category`, `subcategory`, `brand`
- `thc_percentage`, `price`, `quantity`, `retailer_name`
- `image_url`, `description`, `timestamp`

---

## Dashboard — `cannabis.py`

Five-section analytics dashboard built on the accumulated scrape history:

| Section | What It Shows |
|---|---|
| **Overview** | Total revenue, units sold, retailers tracked, best-selling product |
| **Revenue Insights** | Daily and cumulative revenue over time (toggle) |
| **Stock Analysis** | Units sold per day, turnover rate, restock frequency by product |
| **Pricing Analysis** | Price distribution across products and categories |
| **Discount Insights** | Discount ranges, most discounted products, promotional trends |

Also includes a **Folium dispensary map** with retailer logos as custom markers.

---

## Tech Stack

- **Python** — scraper and dashboard logic
- **Requests** — Leafly API calls with session management
- **Plotly Dash + Dash Bootstrap Components** — web dashboard
- **Pandas** — data processing and metric calculation
- **Folium** — interactive dispensary map
- **SQLite** — product history database

---

## Running the Scraper

```bash
pip install requests pandas

python leafly_products_spider.py
```

Run this on a schedule (e.g. hourly via cron) to build up enough inventory history to infer sales.

---

## Running the Dashboard

```bash
pip install dash dash-bootstrap-components plotly pandas folium

python cannabis.py
```

Open `http://localhost:8050`. Update `db_path_A` in `cannabis.py` to point to your local `leafly_products.db`.
