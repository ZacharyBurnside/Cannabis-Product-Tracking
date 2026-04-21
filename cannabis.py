import dash
from dash import dcc, html, dash_table, Input, Output
import pandas as pd
import plotly.express as px
import dash_bootstrap_components as dbc
import sqlite3
import folium
from folium.features import CustomIcon

# Database connection path
db_path_A = '/home/zburnside/leafly_products.db'

def generate_card(title, value, color, tooltip=None):
    body = [
        html.H4(title, className="card-title"),
        html.P(value, className="card-text")
    ]
    if tooltip:
        body.append(html.P(tooltip, className="text-muted small"))
    return dbc.Card(dbc.CardBody(body), color=color, inverse=True)

def load_data(db_path_A):
    try:
        connection = sqlite3.connect(db_path_A)
        query = "SELECT * FROM leafly_products;"
        df_A = pd.read_sql_query(query, connection)
        connection.close()
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

    # Convert timestamp column to datetime
    df_A['timestamp'] = pd.to_datetime(df_A['timestamp'], errors='coerce')
    df_A = df_A.dropna(subset=['timestamp'])
    df_A['date'] = df_A['timestamp'].dt.date

    # Convert quantity and price to numeric
    df_A['quantity'] = pd.to_numeric(df_A['quantity'], errors='coerce').fillna(0)
    df_A['price'] = pd.to_numeric(df_A['price'], errors='coerce').fillna(0)

    # ✅ Count total rows BEFORE any grouping
    total_products = len(df_A) # This should be ~1M rows

    # ✅ Count unique products from the ORIGINAL DataFrame
    unique_products = df_A['product_id'].nunique()

    # Sort by product and time for correct stock tracking
    df_A = df_A.sort_values(by=['product_name', 'timestamp'])

    # ✅ Calculate stock change (difference in quantity over time)
    df_A['stock_change'] = df_A.groupby('product_name')['quantity'].diff().fillna(0) * -1  # Negative means sold

    # ✅ Ignore restocks (positive stock changes)
    df_A.loc[df_A['stock_change'] < 0, 'stock_change'] = 0

    # ✅ Compute revenue correctly (only valid sales)
    df_A['revenue'] = df_A['stock_change'] * df_A['price']

    # ✅ Ensure no negative revenue values
    df_A['revenue'] = df_A['revenue'].clip(lower=0)

    # ✅ Filter only rows where stock actually decreased (i.e., sales)
    df_sales = df_A[df_A['stock_change'] > 0].copy()

    # Recalculate stock metrics with valid sales
    stock_by_product = df_sales.groupby('product_name').agg(
        total_sales_volume=('stock_change', 'sum'),
        restock_frequency=('stock_change', lambda x: (x > 0).sum()),
        average_inventory=('quantity', 'mean')
    ).reset_index()

    # Add turnover rate
    stock_by_product['turnover_rate'] = (stock_by_product['total_sales_volume'] /
                                         stock_by_product['average_inventory']).fillna(0)

    # ✅ Aggregate daily revenue & stock changes
    daily_data = df_A.groupby('date', as_index=False).agg(
        daily_revenue=('revenue', 'sum'),
        daily_stock_change=('stock_change', 'sum'),
        total_products_sold=('stock_change', 'sum')  # ✅ Only count valid stock changes
    )

    # ✅ Convert stock changes to absolute values
    daily_data['daily_stock_change'] = daily_data['daily_stock_change'].abs()

    # ✅ Compute cumulative revenue and stock change
    daily_data['cumulative_revenue'] = daily_data['daily_revenue'].cumsum()
    daily_data['cumulative_stock_change'] = daily_data['daily_stock_change'].cumsum()

    # Additional Metrics
    max_date = daily_data['date'].max()
    total_revenue = round(daily_data['daily_revenue'].sum())
    daily_revenue = round(daily_data.loc[daily_data['date'] == max_date, 'daily_revenue'].sum())
    overall_stock_change = round(daily_data['daily_stock_change'].sum())
    average_stock_change = round(daily_data['daily_stock_change'].mean())
    average_revenue = round(daily_data['daily_revenue'].mean())
    highest_revenue_day = daily_data.loc[daily_data['daily_revenue'].idxmax()]
    lowest_revenue_day = daily_data.loc[daily_data['daily_revenue'].idxmin()]
    total_products_sold = abs(daily_data['daily_stock_change'].sum())  # Total units sold
    best_selling_product = df_sales.groupby('product_name')['revenue'].sum().idxmax()
    num_retailers = len(df_A['retailer_name'].unique()) if 'retailer_name' in df_A.columns else 0

    all_discounts = pd.DataFrame(columns=['discount_percent', 'timestamp', 'product_name'])  # ✅ Fix: Include required columns
    all_discounts['date'] = pd.to_datetime(all_discounts['timestamp']).dt.date

    return (df_A, df_sales, daily_data, total_revenue, daily_revenue, average_revenue,
        highest_revenue_day, lowest_revenue_day, best_selling_product,
        total_products_sold, overall_stock_change,
        average_stock_change, all_discounts, num_retailers, total_products)  # ✅ Add total_products


(df_A, df_sales, daily_data, total_revenue, daily_revenue, average_revenue, highest_revenue_day,
 lowest_revenue_day, best_selling_product, total_products_sold,
 overall_stock_change, average_stock_change, all_discounts, num_retailers, total_products) = load_data(db_path_A)

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])

app.title = "Cannabis Analyzer"


sidebar = html.Div(style={
        'width': '250px',
        'position': 'fixed',
        'top': 0,
        'left': 0,
        'height': '100%',
        'backgroundColor': '#343a40',
        'color': '#fff',
        'padding': '20px',
        'display': 'flex',
        'flexDirection': 'column',
        'justifyContent': 'space-between',
    },
    children=[
        html.Div([
            html.H2("Dashboard", style={'color': '#fff', 'textAlign': 'center'}),
            html.Hr(),
            dbc.Nav(
                [
                    dbc.NavLink("Overview", href="/overview", active=True, id="overview-link"),
                    dbc.NavLink("Revenue Insights", href="/revenue", id="revenue-link"),
                    dbc.NavLink("Stock Analysis", href="/stock", id="stock-link"),
                    dbc.NavLink("Pricing Analysis", href="/pricing", id="pricing-link"),
                    dbc.NavLink("Discount Insights", href="/discounts", id="discounts-link"),
                ],
                vertical=True,
                pills=True,
            ),
        ]),
        html.Div([
            html.A(
                "\u2615 Buy Me a Coffee",
                href="https://www.buymeacoffee.com/zburn",
                target="_blank",
                style={
                    'textDecoration': 'none',
                    'color': '#fff',
                    'fontSize': '14px',
                    'textAlign': 'center',
                }
            )
        ])
    ]
)

content = html.Div(id='page-content', style={'marginLeft': '270px', 'padding': '20px'})
app.layout = html.Div([sidebar, content])


def fetch_data_from_db(db_file, table_name="leafly_stores", query=None):
    conn = sqlite3.connect(db_file)
    try:
        if query is None:
            # Default query to fetch all rows
            query = f"SELECT * FROM {table_name}"

        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()  # Ensure the connection is closed

    return df

# Function to generate the dispensary map
def generate_dispensary_map(df, map_file="dispensary_map.html"):
    # Center map
    center_lat = df['latitude'].mean()
    center_lon = df['longitude'].mean()
    dispensary_map = folium.Map(location=[center_lat, center_lon], zoom_start=6)

    # Add dispensaries to the map
    for _, store in df.iterrows():
        if store['logo']:
            icon = CustomIcon(
                icon_image=store['logo'],
                icon_size=(50, 50)
            )
            folium.Marker(
                location=[store['latitude'], store['longitude']],
                popup=f"<strong>{store['name']}</strong><br>{store['address1']}, {store['city']}, {store['state']}",
                icon=icon
            ).add_to(dispensary_map)
        else:
            folium.Marker(
                location=[store['latitude'], store['longitude']],
                popup=f"<strong>{store['name']}</strong><br>{store['address1']}, {store['city']}, {store['state']}"
            ).add_to(dispensary_map)

    # Save the map
    dispensary_map.save(map_file)

# Callbacks for navigation
@app.callback(
    Output('product-price-trends', 'figure'),
    [Input('product-selector', 'value')]
)
def update_product_price_trends(selected_products):
    # Calculate price trends
    price_trends = df_A.groupby(['date', 'product_name']).agg(
        avg_price=('price', 'mean')
    ).reset_index()

    if not selected_products:
        return px.line(title="No Products Selected")

    # Filter data for selected products
    filtered_data = price_trends[price_trends['product_name'].isin(selected_products)]

    # Create the line chart
    return px.line(
        filtered_data,
        x='date',
        y='avg_price',
        color='product_name',
        title="Price Trends for Selected Products",
        markers=True,
        template="plotly_white"
    ).update_layout(
        yaxis_title="Average Price",
        xaxis_title="Date"
    )

@app.callback(
    Output('page-content', 'children'),
    [Input('overview-link', 'n_clicks'),
     Input('revenue-link', 'n_clicks'),
     Input('stock-link', 'n_clicks'),
     Input('discounts-link', 'n_clicks'),
     Input('pricing-link', 'n_clicks')]  # Add this input
)
def display_page(n1, n2, n3, n4, n5):  # Add n5 for pricing link
    ctx = dash.callback_context
    if not ctx.triggered:
        return html.Div("Select a tab from the sidebar.", style={'textAlign': 'center', 'marginTop': '50px'})
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        # Main Overview Tab Logic
    if button_id == 'overview-link':
        # Fetch data from SQLite database
        db_file = "/home/zburnside/leafly_stores.db"
        df_stores = fetch_data_from_db(db_file)

        # Generate and save the map
        map_file = "dispensary_map.html"
        generate_dispensary_map(df_stores, map_file)

        # Prepare other data and stats
        cumulative_revenue = daily_data.copy()
        cumulative_revenue['cumulative_revenue'] = cumulative_revenue['daily_revenue'].cumsum()

        unique_products = df_A['product_id'].nunique()
        total_products = len(df_A)
        price_min = df_A['price'].min()
        price_max = df_A['price'].max()
        price_range = f"${price_min:,.2f} - ${price_max:,.2f}"
        days_collected = (df_A['date'].max() - df_A['date'].min()).days

        if 'original_price' in df_A.columns and 'current_price' in df_A.columns:
            df_A['price_change'] = (df_A['current_price'] - df_A['original_price']).fillna(0)
            df_A['price_change_percent'] = (
                df_A['price_change'] / df_A['original_price'].replace(0, float('nan'))
            ) * 100
            df_A['price_change_percent'] = df_A['price_change_percent'].fillna(0)
        else:
            avg_price_change_percent = 0

        return html.Div([
            # Hero Section
            html.Div([
                html.H1(
                    "Cannabis Market Dashboard",
                    style={
                        'textAlign': 'center',
                        'marginBottom': '20px',
                        'color': '#2E8B57',
                        'fontSize': '40px',
                        'fontWeight': 'bold'
                    }
                ),
                html.P(
                    "Your essential tool for uncovering market insights, trends, and opportunities in the cannabis industry.",
                    style={
                        'textAlign': 'center',
                        'fontSize': '20px',
                        'color': '#444',
                        'marginBottom': '40px'
                    }
                )
            ], style={
                'padding': '20px',
                'background': 'linear-gradient(90deg, #e8f5e9, #c8e6c9)',
                'borderRadius': '10px',
                'marginBottom': '30px'
            }),

            # Highlights Section
            html.Div([
                html.Div([
                    html.H3("Highlights", style={
                        'color': '#2E8B57',
                        'textAlign': 'center',
                        'fontWeight': 'bold',
                        'marginBottom': '20px'
                    }),
                    html.Ul([
                        html.Li(f"🌿 Number of Dispensaries: {len(df_stores)}", style={'marginBottom': '10px'}),
                        html.Li("⏰ Hourly Updates for Real-Time Insights", style={'marginBottom': '10px'}),
                        html.Li("📊 Metrics: Revenue, Stock, Pricing", style={'marginBottom': '10px'}),
                        html.Li("📅 Data Coverage Since: January 16, 2025", style={'marginBottom': '10px'})
                    ], style={
                        'lineHeight': '1.8',
                        'paddingLeft': '20px'
                    })
                ], style={
                    'width': '45%',
                    'padding': '20px'
                }),

                html.Div([
                    html.H3("Key Statistics", style={
                        'color': '#2E8B57',
                        'textAlign': 'center',
                        'fontWeight': 'bold',
                        'marginBottom': '20px'
                    }),
                    html.Ul([
                        html.Li(f"📦 Unique Products: {unique_products:,}", style={'marginBottom': '10px'}),
                        html.Li(f"📦 Total Products: {total_products:,}", style={'marginBottom': '10px'}),
                        html.Li(f"💲 Price Range: {price_range}", style={'marginBottom': '10px'}),
                        html.Li(f"📆 Days Collected: {days_collected} days", style={'marginBottom': '10px'}),
                        html.Li(f"📉 Avg. Price Change: {avg_price_change_percent:.2f}%", style={'marginBottom': '10px'})
                    ], style={
                        'lineHeight': '1.8',
                        'paddingLeft': '20px'
                    })
                ], style={
                    'width': '45%',
                    'padding': '20px'
                })
            ], style={
                'display': 'flex',
                'justifyContent': 'space-between',
                'backgroundColor': '#F9F9F9',
                'padding': '20px',
                'borderRadius': '10px',
                'boxShadow': '0px 4px 6px rgba(0, 0, 0, 0.1)',
                'marginBottom': '30px'
            }),

            # Map Section
            html.Div([
                html.H3("Dispensary Locations", style={
                    'color': '#2E8B57',
                    'textAlign': 'center',
                    'fontWeight': 'bold',
                    'marginBottom': '20px'
                }),
                html.Iframe(
                    id='dispensary-map',
                    srcDoc=open(map_file, "r").read(),
                    width='100%',
                    height='600px',
                    style={
                        'border': 'none',
                        'borderRadius': '10px',
                        'boxShadow': '0px 4px 6px rgba(0, 0, 0, 0.1)'
                    }
                )
            ], style={
                'marginBottom': '30px',
                'padding': '20px',
                'backgroundColor': '#F9F9F9',
                'borderRadius': '10px',
                'boxShadow': '0px 4px 6px rgba(0, 0, 0, 0.1)'
            })
        ])


    elif button_id == 'revenue-link':
        if daily_data.empty:
            return html.Div([
                html.H1("Revenue Insights", style={'textAlign': 'center'}),
                html.P("No revenue data available", style={'textAlign': 'center', 'color': 'red'})
            ])

        # Compute cumulative revenue in case it isn't calculated earlier
        cumulative_revenue = daily_data.copy()
        cumulative_revenue['cumulative_revenue'] = cumulative_revenue['daily_revenue'].cumsum()

        # Ensure revenue values exist
        latest_date = daily_data['date'].max()
        daily_revenue = round(daily_data.loc[daily_data['date'] == latest_date, 'daily_revenue'].sum(), 2)
        overall_revenue = round(daily_data['daily_revenue'].sum(), 2)
        avg_revenue = round(daily_data['daily_revenue'].mean(), 2)

        if not daily_data.empty:
            highest_revenue_day = daily_data.loc[daily_data['daily_revenue'].idxmax()]
            lowest_revenue_day = daily_data.loc[daily_data['daily_revenue'].idxmin()]
        else:
            highest_revenue_day = {'date': 'N/A', 'daily_revenue': 0}
            lowest_revenue_day = {'date': 'N/A', 'daily_revenue': 0}

        # Layout
        return html.Div([
            html.H1("Revenue Insights", style={'textAlign': 'center', 'marginBottom': '20px', 'color': '#2E8B57', 'fontSize': '32px', 'fontWeight': 'bold'}),

            # Key Metrics Section
            html.Div([
                html.H3("Key Metrics", style={'textAlign': 'center', 'marginBottom': '20px', 'fontSize': '26px', 'fontWeight': 'bold', 'color': '#2E8B57'}),
                dbc.Row([
                    dbc.Col(html.Div([
                        html.Span("📅 Daily Revenue: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#007BFF'}),
                        html.Span(f"${daily_revenue:,}", style={'fontSize': '22px', 'color': '#0056b3'})
                    ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                    dbc.Col(html.Div([
                        html.Span("💰 Overall Revenue: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#28A745'}),
                        html.Span(f"${overall_revenue:,}", style={'fontSize': '22px', 'color': '#1e7e34'})
                    ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                    dbc.Col(html.Div([
                        html.Span("📊 Average Revenue: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#FFC107'}),
                        html.Span(f"${avg_revenue:,}", style={'fontSize': '22px', 'color': '#e0a800'})
                    ], style={'textAlign': 'center', 'padding': '20px'}), width=4)
                ], justify='center'),

                dbc.Row([
                    dbc.Col(html.Div([
                        html.Span("📈 Highest Revenue Day: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#17A2B8'}),
                        html.Span(f"{highest_revenue_day['date']}: ${highest_revenue_day['daily_revenue']:,}", style={'fontSize': '22px', 'color': '#117a8b'})
                    ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                    dbc.Col(html.Div([
                        html.Span("📉 Lowest Revenue Day: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#DC3545'}),
                        html.Span(f"{lowest_revenue_day['date']}: ${lowest_revenue_day['daily_revenue']:,}", style={'fontSize': '22px', 'color': '#c82333'})
                    ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                    dbc.Col(html.Div([
                        html.Span("📅 Revenue Updated On: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#6C757D'}),
                        html.Span(str(latest_date), style={'fontSize': '22px', 'color': '#495057'})
                    ], style={'textAlign': 'center', 'padding': '20px'}), width=4)
                ], justify='center')
            ], style={
                'padding': '30px',
                'backgroundColor': '#f8f9fa',
                'borderRadius': '12px',
                'boxShadow': '0px 4px 6px rgba(0, 0, 0, 0.1)',
                'marginBottom': '30px'
            }),

            # Chart Section
            html.Div([
                html.Div([
                    html.Label(
                        "View Mode:", style={'fontWeight': 'bold', 'marginRight': '10px', 'fontSize': '16px'}
                    ),
                    dcc.RadioItems(
                        id='revenue-toggle',
                        options=[
                            {'label': 'Daily Revenue', 'value': 'daily'},
                            {'label': 'Cumulative Revenue', 'value': 'cumulative'}
                        ],
                        value='cumulative',
                        inline=True,
                        style={'fontSize': '16px'}
                    ),
                    dcc.Graph(id='revenue-chart')
                ], style={'width': '100%', 'marginBottom': '20px'}),
            ], style={'marginBottom': '20px'}),

            # Store for Data
            dcc.Store(id='revenue-data', data={
                'daily': daily_data.to_dict('records'),
                'cumulative': cumulative_revenue.to_dict('records')
            })
        ], style={'padding': '20px', 'maxWidth': '1200px', 'margin': '0 auto'})

    elif button_id == 'stock-link':
        # Calculate cumulative stock change over time
        cumulative_stock = daily_data.copy()
        cumulative_stock['cumulative_stock_change'] = cumulative_stock['daily_stock_change'].cumsum()

        # Turnover rate calculation
        data_duration_days = (df_A['timestamp'].max() - df_A['timestamp'].min()).days
        annualization_factor = 365 / data_duration_days if data_duration_days > 0 else 1

        stock_by_product = df_A.groupby('product_name').agg(
            total_stock_change=('stock_change', 'sum'),
            total_sales_volume=('stock_change', lambda x: -x[x < 0].sum()),  # Only sales (negative stock changes)
            restock_frequency=('stock_change', lambda x: (x > 0).sum()),  # Count restocks
            average_inventory=('quantity', 'mean')  # Average inventory
        ).reset_index()

        stock_by_product['turnover_rate'] = (stock_by_product['total_sales_volume'] /
                                             stock_by_product['average_inventory']) * annualization_factor

        # Overall stock metrics
        current_turnover_rate = (stock_by_product['total_sales_volume'].sum() /
                                 stock_by_product['average_inventory'].sum()) * annualization_factor
        average_turnover_rate = stock_by_product['turnover_rate'].mean()
        total_units_sold = stock_by_product['total_sales_volume'].sum()
        avg_units_sold_per_product = stock_by_product['total_sales_volume'].mean()
        avg_units_sold_per_product_per_day = (stock_by_product['total_sales_volume'].sum() /
                                              (data_duration_days * len(stock_by_product)))
        units_sold_today = daily_data[daily_data['date'] == daily_data['date'].max()]['total_products_sold'].sum()

        # Popular time for restocking

        df_A['timestamp'] = pd.to_datetime(df_A['timestamp'], errors='coerce')
        df_A['hour'] = df_A['timestamp'].dt.hour
        # Filter for restocking events
        restock_events = df_A[df_A['stock_change'] > 0]

        if restock_events.empty:
            print("❌ No restocks found! Setting popular_restock_hour to None.")
            popular_restock_hour = None  # Set a default value to avoid the error
        else:
            # Group by hour and find the most common restocking hour
            popular_restock_hour = restock_events.groupby('hour').size().idxmax()


        # Store daily and cumulative stock data for toggling
        stock_data = {
            'daily': daily_data.to_dict('records'),
            'cumulative': cumulative_stock.to_dict('records')
        }

        # Layout for Stock Analysis with Key Metrics at the Top
        return html.Div([
            # Header Section
            html.H1(
                "Stock Analysis",
                style={
                    'textAlign': 'center',
                    'marginBottom': '20px',
                    'color': '#2E8B57',  # Grass green color
                    'fontSize': '34px',
                    'fontWeight': 'bold'
                }
            ),

            # Key Metrics Section (Stock)
            html.Div([
                html.H3(
                    "Key Stock Metrics",
                    style={
                        'textAlign': 'center',
                        'marginBottom': '20px',
                        'fontSize': '26px',
                        'fontWeight': 'bold',
                        'color': '#2E8B57'  # Grass green
                    }
                ),
                dbc.Row([
                    dbc.Col(html.Div([
                        html.Span("🔄 Inventory Turnover (times/year): ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#007BFF'}),
                        html.Span(f"{current_turnover_rate:.2f}", style={'fontSize': '22px', 'color': '#0056b3'})
                    ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                    dbc.Col(html.Div([
                        html.Span("📈 Average Turnover Rate: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#28A745'}),
                        html.Span(f"{average_turnover_rate:.2f}", style={'fontSize': '22px', 'color': '#1e7e34'})
                    ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                    dbc.Col(html.Div([
                        html.Span("📦 Total Units Sold: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#FFC107'}),
                        html.Span(f"{total_units_sold:,} units", style={'fontSize': '22px', 'color': '#e0a800'})
                    ], style={'textAlign': 'center', 'padding': '20px'}), width=4)
                ], justify='center'),
                dbc.Row([
                    dbc.Col(html.Div([
                        html.Span("📊 Avg Units Sold/Product: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#17A2B8'}),
                        html.Span(f"{avg_units_sold_per_product:.0f}", style={'fontSize': '22px', 'color': '#117a8b'})
                    ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                    dbc.Col(html.Div([
                        html.Span("📊 Avg Units Sold/Product/Day: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#17A2B8'}),
                        html.Span(f"{avg_units_sold_per_product_per_day:.2f}", style={'fontSize': '22px', 'color': '#117a8b'})
                    ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                    dbc.Col(html.Div([
                        html.Span("🕒 Popular Restock Hour: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#DC3545'}),
                        html.Span(f"{popular_restock_hour}:00", style={'fontSize': '22px', 'color': '#c82333'})
                    ], style={'textAlign': 'center', 'padding': '20px'}), width=4)
                ], justify='center'),
                dbc.Row([
                    dbc.Col(html.Div([
                        html.Span("🛒 Units Sold Today: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#6C757D'}),
                        html.Span(f"{units_sold_today:,} units", style={'fontSize': '22px', 'color': '#495057'})
                    ], style={'textAlign': 'center', 'padding': '20px'}), width=4)
                ], justify='center')
            ], style={
                'padding': '30px',
                'backgroundColor': '#f8f9fa',
                'borderRadius': '12px',
                'boxShadow': '0px 4px 6px rgba(0, 0, 0, 0.1)',
                'margin': '30px auto',
                'width': '90%'  # Adjust width for better alignment
            }),


            # Toggle for Daily vs. Cumulative Stock Change
            html.Div([
                html.Label(
                    "View Mode:", style={'fontWeight': 'bold', 'marginRight': '10px', 'fontSize': '16px'}
                ),
                dcc.RadioItems(
                    id='stock-toggle',
                    options=[
                        {'label': 'Daily Stock Change', 'value': 'daily'},
                        {'label': 'Cumulative Stock Change', 'value': 'cumulative'}
                    ],
                    value='cumulative',
                    inline=True,
                    style={'marginBottom': '15px', 'fontSize': '14px'}
                )
            ], style={'textAlign': 'center', 'marginBottom': '20px'}),

            # Bar Chart for Stock Sold
            html.Div([
                dcc.Graph(id='stock-chart')
            ], style={'width': '75%', 'margin': '0 auto', 'marginBottom': '30px'}),

            # Store Stock Data
            dcc.Store(id='stock-data', data=stock_data)
        ])


    elif button_id == 'pricing-link':
        # Average price over time
        avg_price_over_time = df_A.groupby(['date', 'category']).agg(
            avg_price=('price', 'mean')
        ).reset_index()

        # Products with the largest price changes
        price_change = df_A.groupby('product_name').agg(
            initial_price=('price', 'first'),
            final_price=('price', 'last')
        ).reset_index()
        price_change['price_change'] = price_change['final_price'] - price_change['initial_price']
        price_change['percent_change'] = (price_change['price_change'] / price_change['initial_price'].replace(0, 1)) * 100

        # Add the `image` column to `price_change`
        price_change = price_change.merge(
            df_A[['product_name', 'image_url']].drop_duplicates('product_name'), on='product_name', how='left'
        )

        # Largest increases and decreases
        largest_increase = price_change.nlargest(5, 'percent_change')
        largest_decrease = price_change.nsmallest(5, 'percent_change')

        q1 = df_A['price'].quantile(0.25)  # First quartile (25th percentile)
        q3 = df_A['price'].quantile(0.75)  # Third quartile (75th percentile)
        iqr = q3 - q1  # Interquartile range

        # Define the lower and upper bounds
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        # Filter the prices within bounds
        filtered_prices = df_A[(df_A['price'] >= lower_bound) & (df_A['price'] <= upper_bound)]

        # Calculate the highest and lowest prices within the filtered range
        highest_price = filtered_prices['price'].max()
        lowest_price = filtered_prices['price'].min()
        # Calculate meaningful pricing statistics
        avg_price = df_A['price'].mean()
        median_price = df_A['price'].median()
        std_dev_price = df_A['price'].std()
        percent_products_changed = (
            price_change[price_change['price_change'] != 0].shape[0] / df_A['product_name'].nunique()
        ) * 100

        # Layout
        return html.Div([
            # Header Section
            html.H1(
                "Pricing Analysis",
                style={
                    'textAlign': 'center',
                    'marginBottom': '20px',
                    'color': '#2E8B57',  # Grass green color
                    'fontSize': '36px',
                    'fontWeight': 'bold'
                }
            ),

            # Top Statistics Section
            html.Div([
                html.H3(
                    "Key Metrics",
                    style={
                        'textAlign': 'center',
                        'marginBottom': '20px',
                        'fontSize': '28px',
                        'fontWeight': 'bold',
                        'color': '#2E8B57'
                    }
                ),
                html.Div([
                    dbc.Row([
                        dbc.Col(html.Div([
                            html.Span("💲 Average Price: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#007BFF'}),
                            html.Span(f"${avg_price:,.2f}", style={'fontSize': '22px', 'color': '#0056b3'})
                        ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                        dbc.Col(html.Div([
                            html.Span("🔢 Median Price: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#28A745'}),
                            html.Span(f"${median_price:,.2f}", style={'fontSize': '22px', 'color': '#1e7e34'})
                        ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                        dbc.Col(html.Div([
                            html.Span("📉 Std. Deviation: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#FFC107'}),
                            html.Span(f"${std_dev_price:,.2f}", style={'fontSize': '22px', 'color': '#e0a800'})
                        ], style={'textAlign': 'center', 'padding': '20px'}), width=4)
                    ], justify='center'),
                    dbc.Row([
                        dbc.Col(html.Div([
                            html.Span("📊 % Products Changed: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#DC3545'}),
                            html.Span(f"{percent_products_changed:.2f}%", style={'fontSize': '22px', 'color': '#c82333'})
                        ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                        dbc.Col(html.Div([
                            html.Span("📈 Highest Price (IQR): ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#17A2B8'}),
                            html.Span(f"${highest_price:,.2f}", style={'fontSize': '22px', 'color': '#117a8b'})
                        ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                        dbc.Col(html.Div([
                            html.Span("📉 Lowest Price (IQR): ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#6C757D'}),
                            html.Span(f"${lowest_price:,.2f}", style={'fontSize': '22px', 'color': '#495057'})
                        ], style={'textAlign': 'center', 'padding': '20px'}), width=4)
                    ], justify='center')
                ], style={
                    'backgroundColor': '#f8f9fa',
                    'padding': '20px',
                    'border': '2px solid #ddd',
                    'borderRadius': '12px',
                    'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.1)',
                    'lineHeight': '2',
                    'textAlign': 'center',
                    'marginBottom': '30px',
                    'width': '80%',
                    'margin': '0 auto'
                })
            ]),

            # Description Section
            html.Div([
                html.P(
                    "Analyze pricing trends, significant changes, and product-specific patterns. "
                    "This dashboard provides insights into the cannabis market to support data-driven decisions.",
                    style={
                        'textAlign': 'center',
                        'fontSize': '18px',
                        'lineHeight': '1.8',
                        'color': '#444',
                        'marginBottom': '30px'
                    }
                )
            ]),

            # Average Price Trends Section
            html.Div([
                html.H4("Average Price Trends by Category", style={'textAlign': 'center', 'marginBottom': '10px'}),
                dcc.Graph(
                    id='price-trends-by-type',
                    figure=px.line(
                        avg_price_over_time,
                        x='date',
                        y='avg_price',
                        color='category',
                        title="Average Price Trends by Category",
                        markers=True,
                        template="plotly_white"
                    ).update_layout(
                        yaxis_title="Average Price ($)",
                        xaxis_title="Date",
                        hovermode="x unified",
                        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
                    ) if not avg_price_over_time.empty else {}  # Ensure the figure is generated only if data is available
                )
            ], style={'width': '70%', 'margin': '0 auto', 'padding': '20px'}),

            # Price Comparison Tool Section
            html.Div([
                html.H4(
                    "Compare Product Prices Over Time",
                    style={
                        'textAlign': 'center',
                        'marginBottom': '20px',
                        'fontSize': '28px',
                        'fontWeight': 'bold',
                        'color': '#2E8B57'
                    }
                ),
                html.Div([
                    # Dropdown with custom styling
                    html.Div([
                        dcc.Dropdown(
                            id='product-selector',
                            options=[
                                {'label': product, 'value': product}
                                for product in df_A['product_name'].unique()
                            ] if 'product_name' in df_A.columns else [],
                            value=[df_A['product_name'].unique()[0]] if not df_A.empty else None,
                            multi=True,
                            placeholder="Select products to compare",
                            style={
                                'width': '80%',
                                'margin': '10px auto',
                                'borderRadius': '12px',
                                'padding': '10px',
                                'border': '1px solid #ddd',
                                'boxShadow': '0px 4px 6px rgba(0, 0, 0, 0.1)'
                            }
                        ),
                        html.Div([
                            dbc.Button("Clear All", id='clear-all', color="danger", size="sm")
                        ], style={'textAlign': 'center', 'marginBottom': '15px'}),
                    ], style={
                        'padding': '20px',
                        'backgroundColor': '#f8f9fa',
                        'border': '2px solid #ddd',
                        'borderRadius': '12px',
                        'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.1)',
                        'marginBottom': '20px'
                    }),

                    # Graph with a gradient card design
                    html.Div([
                        dcc.Graph(
                            id='product-price-trends',
                            config={"displayModeBar": True}
                        ),
                        html.Div(
                            "Hover over the graph to see detailed price trends",
                            style={
                                'textAlign': 'center',
                                'fontSize': '14px',
                                'color': '#6c757d',
                                'marginTop': '10px'
                            }
                        )
                    ], style={
                        'background': 'linear-gradient(90deg, #e8f5e9, #c8e6c9)',
                        'borderRadius': '12px',
                        'padding': '20px',
                        'boxShadow': '0px 4px 8px rgba(0, 0, 0, 0.15)',
                        'marginBottom': '30px'
                    })
                ])
            ], style={
                'width': '80%',
                'margin': '0 auto',
                'padding': '20px',
                'backgroundColor': '#ffffff',
                'borderRadius': '12px',
                'boxShadow': '0px 4px 8px rgba(0, 0, 0, 0.15)'
            }),

            # Products with Largest Price Changes Section
            html.Div([
                html.H4("Products with the Largest Price Increases", style={'textAlign': 'center', 'marginBottom': '10px'}),
                html.Div(
                    style={
                        'display': 'flex',
                        'flexWrap': 'wrap',
                        'justifyContent': 'center',
                        'gap': '20px',
                        'marginBottom': '20px',
                    },
                    children=[
                        dbc.Card(
                            [
                                html.Div(
                                    html.Img(
                                        src=row['image_url'],
                                        style={
                                            'height': '150px',
                                            'width': '150px',
                                            'objectFit': 'contain',
                                            'margin': '0 auto'
                                        }
                                    ),
                                    style={'textAlign': 'center'}
                                ),
                                dbc.CardBody([
                                    html.H5(row['product_name'], className="card-title", style={'textAlign': 'center'}),
                                    html.P(f"Initial Price: ${row['initial_price']:,.2f}", className="card-text"),
                                    html.P(f"Final Price: ${row['final_price']:,.2f}", className="card-text"),
                                    html.P(
                                        f"Price Increase: {row['percent_change']:.2f}%",
                                        className="card-text",
                                        style={'color': 'green', 'fontWeight': 'bold'}
                                    ),
                                ]),
                            ],
                            style={
                                'width': '250px',
                                'border': '1px solid #ddd',
                                'boxShadow': '0px 4px 6px rgba(0, 0, 0, 0.1)'
                            }
                        )
                        for _, row in largest_increase.iterrows()
                    ]
                ),

                html.H4("Products with the Largest Price Decreases", style={'textAlign': 'center', 'marginBottom': '10px'}),
                html.Div(
                    style={
                        'display': 'flex',
                        'flexWrap': 'wrap',
                        'justifyContent': 'center',
                        'gap': '20px',
                        'marginBottom': '40px',
                    },
                    children=[
                        dbc.Card(
                            [
                                html.Div(
                                    html.Img(
                                        src=row['image_url'],
                                        style={
                                            'height': '150px',
                                            'width': '150px',
                                            'objectFit': 'contain',
                                            'margin': '0 auto'
                                        }
                                    ),
                                    style={'textAlign': 'center'}
                                ),
                                dbc.CardBody([
                                    html.H5(row['product_name'], className="card-title", style={'textAlign': 'center'}),
                                    html.P(f"Initial Price: ${row['initial_price']:,.2f}", className="card-text"),
                                    html.P(f"Final Price: ${row['final_price']:,.2f}", className="card-text"),
                                    html.P(
                                        f"Price Decrease: {row['percent_change']:.2f}%",
                                        className="card-text",
                                        style={'color': 'red', 'fontWeight': 'bold'}
                                    ),
                                ]),
                            ],
                            style={
                                'width': '250px',
                                'border': '1px solid #ddd',
                                'boxShadow': '0px 4px 6px rgba(0, 0, 0, 0.1)'
                            }
                        )
                        for _, row in largest_decrease.iterrows()
                    ]
                ),
            ])
        ])


    elif button_id == 'discounts-link':
        if 'timestamp' in all_discounts.columns:
    # Convert 'timestamp' to 'date' and find the latest update
            all_discounts['date'] = pd.to_datetime(all_discounts['timestamp']).dt.date
            latest_update = all_discounts['date'].max()
        else:
            # Handle missing 'timestamp' column
            print("Warning: 'timestamp' column not found. Using default dates.")
            all_discounts['date'] = pd.Timestamp.now().date()  # Set today's date as a placeholder
            latest_update = pd.Timestamp.now()  # Use the current timestamp as the fallback


        # Calculate Discount Statistics
        avg_discount = all_discounts['discount_percent'].mean()
        max_discount = all_discounts['discount_percent'].max()
        total_discounted_products = len(all_discounts)
        if all_discounts.empty or all_discounts['discount_percent'].isna().all():
            highest_discount_product = {'product_name': 'N/A', 'discount_percent': 0}
        else:
            highest_discount_product = all_discounts.loc[all_discounts['discount_percent'].idxmax()]

        # Discount Bins for Analysis
        all_discounts['discount_bin'] = pd.cut(
            all_discounts['discount_percent'], bins=[0, 10, 20, 30, 50, 100],
            labels=["0-10%", "10-20%", "20-30%", "30-50%", "50%+"]
        )
        discount_bins = all_discounts['discount_bin'].value_counts().sort_index()
        all_discounts['date'] = pd.to_datetime(all_discounts['date']).dt.date

        # Popular Discount Ranges
        most_common_discount_bin = discount_bins.idxmax()

        return html.Div([
            # Header Section
            html.H1(
                "Discount Insights",
                style={
                    'textAlign': 'center',
                    'marginBottom': '20px',
                    'color': '#2E8B57',
                    'fontSize': '36px',
                    'fontWeight': 'bold'
                }
            ),

            # Key Metrics Section
            html.Div([
                html.H3("Key Discount Metrics", style={'textAlign': 'center', 'marginBottom': '20px', 'fontSize': '28px'}),
                html.Div([
                    dbc.Row([
                        dbc.Col(html.Div([
                            html.Span("📉 Average Discount: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#007BFF'}),
                            html.Span(f"{avg_discount:.2f}%", style={'fontSize': '22px', 'color': '#0056b3'})
                        ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                        dbc.Col(html.Div([
                            html.Span("💰 Maximum Discount: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#28A745'}),
                            html.Span(f"{max_discount:.2f}%", style={'fontSize': '22px', 'color': '#1e7e34'})
                        ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                        dbc.Col(html.Div([
                            html.Span("📦 Total Discounted Products: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#FFC107'}),
                            html.Span(f"{total_discounted_products:,}", style={'fontSize': '22px', 'color': '#e0a800'})
                        ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                    ]),
                    dbc.Row([
                        dbc.Col(html.Div([
                            html.Span("🌟 Highest Discount Product: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#17A2B8'}),
                            html.Span(highest_discount_product['product_name'], style={'fontSize': '22px', 'color': '#117a8b'})
                        ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                        dbc.Col(html.Div([
                            html.Span("📊 Most Common Discount Range: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#DC3545'}),
                            html.Span(f"{most_common_discount_bin}", style={'fontSize': '22px', 'color': '#c82333'})
                        ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                        dbc.Col(html.Div([
                            html.Span("📅 Discounts Updated On: ", style={'fontWeight': 'bold', 'fontSize': '20px', 'color': '#6C757D'}),
                            html.Span(latest_update.strftime('%Y-%m-%d'), style={'fontSize': '22px', 'color': '#495057'})
                        ], style={'textAlign': 'center', 'padding': '20px'}), width=4),
                    ])
                ], style={
                    'backgroundColor': '#f8f9fa',
                    'padding': '20px',
                    'border': '2px solid #ddd',
                    'borderRadius': '12px',
                    'boxShadow': '0 6px 8px rgba(0, 0, 0, 0.1)',
                    'lineHeight': '2',
                    'marginBottom': '30px'
                }),
            ]),


            # Description Section
            html.Div([
                html.P(
                    "Analyze discounts, promotional trends, and top deals in the cannabis market. "
                    "Discover savings opportunities and refine your promotional strategies with detailed analytics.",
                    style={
                        'textAlign': 'center',
                        'fontSize': '18px',
                        'lineHeight': '1.8',
                        'color': '#444',
                        'marginBottom': '30px'
                    }
                )
            ]),

            # Discount Ranges Section
            html.Div([
                html.H4("Discount Ranges Distribution", style={'textAlign': 'center', 'marginBottom': '10px'}),
                dcc.Graph(
                    id='discount-ranges',
                    figure=px.bar(
                        discount_bins,
                        x=discount_bins.index,
                        y=discount_bins.values,
                        title="Products by Discount Ranges",
                        labels={"x": "Discount Range", "y": "Number of Products"},
                        template="plotly_white"
                    )
                )
            ], style={'width': '70%', 'margin': '0 auto', 'padding': '20px', 'marginBottom': '40px'}),

            # Discount Cards Section
            html.Div([
                html.H4("All Discounted Products", style={'textAlign': 'center', 'marginBottom': '20px'}),
                html.Div(
                    style={
                        'display': 'flex',
                        'flexWrap': 'wrap',
                        'justifyContent': 'center',
                        'gap': '20px',
                    },
                    children=[
                        dbc.Card(
                            [
                                html.Div(
                                    html.Img(
                                        src=row['image_url'],
                                        style={
                                            'height': '150px',
                                            'width': '150px',
                                            'objectFit': 'contain',
                                            'margin': '0 auto'
                                        }
                                    ),
                                    style={'textAlign': 'center'}
                                ),
                                dbc.CardBody([
                                    html.H5(row['product_name'], className="card-title", style={'textAlign': 'center'}),
                                    html.P(f"Original Price: ${row['original_price']:,.2f}", className="card-text", style={'textAlign': 'center'}),
                                    html.P(f"Current Price: ${row['current_price']:,.2f}", className="card-text", style={'textAlign': 'center'}),
                                    html.P(
                                        f"Discount: {row['discount_percent']}%",
                                        className="card-text",
                                        style={
                                            'textAlign': 'center',
                                            'color': 'red',
                                            'fontWeight': 'bold'
                                        }
                                    ),
                                ]),
                            ],
                            style={
                                'width': '250px',
                                'border': '1px solid #ddd',
                                'boxShadow': '0px 4px 6px rgba(0, 0, 0, 0.1)',
                                'padding': '10px',
                            }
                        )
                        for _, row in all_discounts.iterrows()
                    ]
                )
            ])
        ])

@app.callback(
    Output('product-selector', 'value'),
    [Input('clear-all', 'n_clicks')],
    prevent_initial_call=True
)
def clear_product_selector(clear_all_clicks):
    # Check if the button is clicked
    if not clear_all_clicks:
        raise dash.exceptions.PreventUpdate

    # Return an empty list to clear all selections
    return []

@app.callback(
    Output('stock-chart', 'figure'),
    [Input('stock-toggle', 'value'),
     Input('stock-data', 'data')]
)
def update_stock_chart(toggle_value, stock_data):
    if stock_data is None or len(stock_data) == 0:
        return px.bar(title="No Data Available")

    df = pd.DataFrame(stock_data['daily'])

    if df.empty or df['daily_stock_change'].sum() == 0:
        return px.bar(title="No Stock Data Available")

    if toggle_value == 'daily':
        df['daily_stock_change'] = df['daily_stock_change'].abs()  # Ensure positive values
        y_column = 'daily_stock_change'
        title = "Daily Stock Sold Over Time"
    else:
        df = pd.DataFrame(stock_data['cumulative'])
        df['cumulative_stock_change'] = df['daily_stock_change'].abs().cumsum()
        y_column = 'cumulative_stock_change'
        title = "Cumulative Stock Sold Over Time"

    fig = px.bar(
        df,
        x='date',
        y=y_column,
        title=title,
        color_discrete_sequence=["#2E004B"]
    )
    fig.update_layout(
        yaxis=dict(title="Stock Sold", gridcolor="lightgray"),
        xaxis=dict(title="Date", gridcolor="lightgray"),
        hovermode="x unified",
        title_font=dict(size=20),
        margin=dict(l=40, r=40, t=40, b=40),
        plot_bgcolor="#f8f9fa",
        paper_bgcolor="#f8f9fa"
    )
    return fig

@app.callback(
    Output('revenue-chart', 'figure'),
    [Input('revenue-toggle', 'value'),
     Input('revenue-data', 'data')]
)
def update_revenue_chart(toggle_value, revenue_data):
    if toggle_value == 'daily':
        df = pd.DataFrame(revenue_data['daily'])
        y_column = 'daily_revenue'
        title = "Daily Revenue Over Time"
    else:
        df = pd.DataFrame(revenue_data['cumulative'])
        y_column = 'cumulative_revenue'
        title = "Cumulative Revenue Over Time"

    fig = px.line(
        df,
        x='date',
        y=y_column,
        title=title,
        markers=True,
        color_discrete_sequence=px.colors.sequential.Plasma
    )
    fig.update_layout(
        yaxis=dict(title="Revenue ($)", gridcolor="lightgray"),
        xaxis=dict(title="Date", gridcolor="lightgray"),
        hovermode="x unified",
        title_font=dict(size=20),
        margin=dict(l=40, r=40, t=40, b=40),
        plot_bgcolor="#f8f9fa",
        paper_bgcolor="#f8f9fa"
    )
    return fig

if __name__ == "__main__":
    app.run_server(debug=False)