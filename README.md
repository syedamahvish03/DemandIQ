# DemandIQ

**AI-Powered Retail Demand Forecasting & Inventory Intelligence**

DemandIQ is a portfolio MVP that explores retail sales, forecasts product demand, and translates forecasts into practical replenishment guidance for small and medium retailers.

## Current status

Core portfolio MVP stages include validated sales-data upload, exploratory analysis, chronological baseline and Random Forest evaluation, and inventory planning. Inventory results can run in an explicitly labelled illustrative scenario or from verified retailer-supplied stock data.

## Planned capabilities

- Retail sales data upload and validation
- Exploratory analysis of products, stores, and sales trends
- Time-series feature engineering and baseline forecasting
- Machine-learning model training with chronological evaluation
- 7-, 15-, and 30-day demand forecasts
- Future forecast-driven lead-time demand, reorder-point and suggested-order calculations
- Downloadable outputs

## Technology

Python, Streamlit, Pandas, NumPy, Plotly, Scikit-learn, and Statsmodels.

## Run locally (Windows PowerShell)

1. Install Python 3.11 or newer.
2. Clone this repository and open its folder in VS Code.
3. Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

4. Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5. Start the app:

```powershell
streamlit run app.py
```

## CSV format

Required columns: date, store, item, sales.

- date: valid date
- store: store identifier
- item: product identifier
- sales: non-negative units sold

Example:

```csv
date,store,item,sales
2025-01-01,1,101,24
2025-01-02,1,101,19
2025-01-01,1,102,13
```

## Data and modelling integrity

Demo data is synthetic and labelled as such. Model performance will be reported only after chronological validation against a baseline. Inventory inputs such as on-hand stock and supplier lead time will be configurable or explicitly illustrative unless supplied by a dataset.

See docs/PROJECT_PLAN.md and data/README.md.


## Inventory planning inputs

The inventory section uses recent observed sales to estimate average daily demand and variability. It requires a separate inventory-input CSV with these columns:

- `store`, `item`: identifiers matching the sales CSV
- `on_hand`: current physical stock
- `on_order`: units already ordered and expected
- `backorders`: units owed to customers
- `lead_time_days`: supplier lead time in days
- `review_period_days`: days until the next planned stock review

Use the app's **Illustrative demo scenario** to demonstrate the calculation workflow without claiming to have real stock data. Its starting stock is derived from recent average sales multiplied by a user-selected stock-cover assumption; incoming orders and backorders are assumed to be zero, and lead time/review period are scenario settings. Alternatively, select **Upload verified inventory data** and provide actual retailer values. The blank template is only for future use with verified inventory records. The calculation uses a 28-day observed-sales window and a 1.65 service-level z factor:

- Safety stock = 1.65 × daily demand standard deviation × √(lead time)
- Reorder point = average daily demand × lead time + safety stock
- Inventory position = on-hand + on-order − backorders
- Target stock = average daily demand × (lead time + review period) + safety stock
- Suggested order quantity = max(0, target stock − inventory position), rounded up

These are planning estimates, not purchase orders. In illustrative mode, every stock and supplier value is an assumption and results are simulated for demonstration only. Validate stock counts, supplier constraints, pack sizes, promotions and the appropriateness of the service-level assumption before acting. The starter Kaggle sales dataset does not contain stock-on-hand, purchase orders, backorders or supplier lead-time fields.


## Forecast-driven inventory planning

In the Inventory planning tab, generate a 7-, 15- or 30-day future demand forecast before calculating recommendations. The selected forecast must cover at least the supplier lead time plus review period for each inventory row.

- Forecast lead-time demand = sum of predicted daily demand over the lead-time window
- Forecast protection-period demand = sum of predicted daily demand over lead time + review period
- Safety stock = 1.65 × historical daily demand standard deviation × √(lead time)
- Reorder point = forecast lead-time demand + safety stock
- Target stock = forecast protection-period demand + safety stock
- Suggested order quantity = max(0, target stock − inventory position), rounded up

The historical demand window is still used to estimate variability for safety stock. In illustrative mode, starting stock, zero incoming orders, zero backorders, lead time and review period remain assumptions. Forecasts and resulting inventory quantities are planning demonstrations, not verified stock records or purchase advice.
