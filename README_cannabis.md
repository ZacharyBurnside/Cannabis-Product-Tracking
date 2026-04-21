# Cannabis Market Analyzer

A Plotly Dash analytics dashboard for the cannabis retail market, built on Leafly data. Tracks product inventory, revenue, pricing, discounts, and dispensary locations across multiple retailers — surfacing sales trends and market intelligence for the legal cannabis industry.

---

## What It Does

Connects to a SQLite database of scraped Leafly product and store data and renders an interactive multi-page dashboard with five analysis sections:

| Section | What It Shows |
|---|---|
| **Overview** | Key metrics — total revenue, units sold, retailers tracked, best-selling product |
| **Revenue Insights** | Daily and cumulative revenue over time |
| **Stock Analysis** | Units sold per day, inventory turnover rate, restock frequency by product |
| **Pricing Analysis** | Price distribution across products and categories |
| **Discount Insights** | Discount ranges, most discounted products, promotional trends |

---

## Features

- **Dispensary map** — Folium map with custom retailer logos as markers, showing all tracked dispensary locations
- **Revenue tracking** — Infers sales from inventory quantity changes over time (stock decrease = sale)
- **Turnover rate** — Calculates inventory turnover per product to identify fast vs slow movers
- **Discount analysis** — Tracks original vs current price, discount percentage, and discount frequency
- **Daily/cumulative toggle** — All time-series charts switch between daily and cumulative views
- **Product selector** — Filter stock and revenue charts by specific products

---

## Tech Stack

- **Python** — data pipeline and app logic
- **Plotly Dash** — web dashboard framework
- **Dash Bootstrap Components** — UI layout and styling
- **Pandas** — data processing and metric calculation
- **Folium** — interactive dispensary map
- **SQLite** — Leafly product and store database

---

## Data

Data is sourced from Leafly via scraping and stored in SQLite:

| Table | Contents |
|---|---|
| `leafly_products` | Product name, price, quantity, retailer, timestamp — scraped over time |
| `leafly_stores` | Dispensary name, location, coordinates, logo URL |

Sales are inferred from inventory changes — when a product's quantity decreases between scrape timestamps, the difference is counted as units sold. Revenue is calculated as `units_sold × price`.

---

## Running the Dashboard

```bash
pip install dash dash-bootstrap-components plotly pandas folium

python cannabis.py
```

Then open `http://localhost:8050` in your browser.

The app expects a SQLite database at `/home/zburnside/leafly_products.db`. Update `db_path_A` in `cannabis.py` to point to your local database path.
