# DemandIQ

**AI-Powered Retail Demand Forecasting & Inventory Intelligence**

DemandIQ is a portfolio MVP that explores retail sales, forecasts product demand, and translates forecasts into practical replenishment guidance for small and medium retailers.

## Current status

Day 1 foundation is in progress. The Streamlit dashboard includes illustrative demo data, basic CSV upload validation, summary metrics, and sales charts. It does not yet train a forecasting model or produce inventory recommendations.

## Planned capabilities

- Retail sales data upload and validation
- Exploratory analysis of products, stores, and sales trends
- Time-series feature engineering and baseline forecasting
- Machine-learning model training with chronological evaluation
- 7-, 15-, and 30-day demand forecasts
- Reorder-point and suggested-order calculations using explicit assumptions
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

Download the template from the app, fill it with verified values, and upload it. Blank rows are excluded rather than filled with invented stock assumptions. The calculation uses a 28-day observed-sales window and a 1.65 service-level z factor:

- Safety stock = 1.65 × daily demand standard deviation × √(lead time)
- Reorder point = average daily demand × lead time + safety stock
- Inventory position = on-hand + on-order − backorders
- Target stock = average daily demand × (lead time + review period) + safety stock
- Suggested order quantity = max(0, target stock − inventory position), rounded up

These are planning estimates, not purchase orders. Validate stock counts, supplier constraints, pack sizes, promotions and the appropriateness of the service-level assumption before acting. The starter sales dataset does not contain stock-on-hand or supplier lead-time fields.
