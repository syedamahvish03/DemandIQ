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
