# DemandIQ — User Guide

## 1. What the app does

DemandIQ is a portfolio MVP for exploring retail sales history, evaluating forecasting models, generating future demand estimates, and demonstrating inventory replenishment calculations. It is not a live stock-management system and does not place purchase orders.

## 2. Start the application (Windows PowerShell)

Run these commands from the repository folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit, normally http://localhost:8501.

Run the automated tests with:

```powershell
python -m pytest -q
```

## 3. Prepare sales data

The app accepts a CSV with these required columns:

| Column | Meaning | Example |
|---|---|---|
| date | Daily sales date | 2013-01-01 |
| store | Store identifier | 1 |
| item | Product identifier | 1 |
| sales | Units sold; must be non-negative | 13 |

The Kaggle Store Item Demand Forecasting Challenge training file uses this schema. Place the extracted `train.csv` at `data/raw/train.csv`, or upload a CSV through the sidebar.

The app validates dates, numeric sales, non-negative sales and store/item identifiers. Invalid rows are excluded and reported. Duplicate records are flagged but retained; review the source before deciding whether they are true duplicates or legitimate repeated transactions.

## 4. Explore the sales dashboard

The Sales dashboard tab presents total units and average daily sales, product and store summaries, daily sales trends, weekday patterns, data-quality observations and recent records.

The built-in fallback data is synthetic and labelled as demo data. Check the displayed data source before interpreting results.

## 5. Evaluate and generate forecasts

The Forecast evaluation tab compares a seasonal-naive-7 baseline, a seven-day moving-average baseline and a Random Forest regression model.

Evaluation uses a chronological historical holdout, not a random split. MAE and RMSE measure average error magnitude; WAPE expresses total absolute error relative to actual demand; bias indicates systematic over- or under-forecasting.

The future forecast action supports 7-, 15- and 30-day horizons. Recursive predictions use earlier predictions as lag inputs. Downloaded forecast files contain model estimates, not actual future sales.

## 6. Inventory planning

The Inventory planning tab requires a future forecast before calculating forecast-driven replenishment recommendations.

Two input modes are available:
- **Illustrative demo scenario:** starting stock is estimated from recent average sales multiplied by the selected stock-cover days. Incoming orders and backorders are assumed to be zero. Lead time and review period are user-selected assumptions.
- **Upload verified inventory data:** upload retailer-supplied values for store, item, on-hand stock, on-order units, backorders, lead time and review period.

The Kaggle sales dataset contains no stock-on-hand, purchase-order, backorder or supplier lead-time information. Never describe illustrative results as actual inventory or purchase advice.

The blank inventory template can be downloaded and completed later using verified retailer records. Forecast horizon must cover each row's lead time plus review period.

## 7. Downloadable outputs

Depending on the selected tab and completed actions, the app provides CSV downloads for future demand forecasts, historical model comparison, a blank inventory input template and inventory recommendation results.

Keep downloaded files with their source dataset and note whether inventory inputs were verified or illustrative.

## 8. Important limitations

- Forecasts use historical sales patterns and do not know future promotions, price changes, holidays, stockouts or supplier disruptions.
- Zero recorded sales may represent a stockout rather than zero customer demand.
- Model evaluation describes the selected dataset and holdout period; it does not guarantee future accuracy.
- Inventory recommendations depend on the quality of retailer-provided stock and supplier inputs, or on clearly labelled demo assumptions.
- This project is a demonstrable portfolio MVP, not a production system with authentication, multi-user data isolation or live commerce integrations.
