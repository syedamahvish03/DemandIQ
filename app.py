from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from data_loader import load_sales_csv
from eda import daily_sales, store_sales, summarize_sales_data, top_products, weekday_sales

st.set_page_config(page_title="DemandIQ", page_icon="📦", layout="wide")


def load_demo_data():
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=90, freq="D")
    rows = []
    for store in [1, 2]:
        for item in [101, 102, 103]:
            for i, date in enumerate(dates):
                sales = max(0, round(18 + item % 7 + 5 * (i % 7 == 5) + 3 * (i % 7 == 6) + ((i * item + store) % 9 - 4)))
                rows.append({"date": date, "store": store, "item": item, "sales": sales})
    return pd.DataFrame(rows)


st.title("📦 DemandIQ")
st.caption("AI-powered retail demand forecasting and inventory intelligence")
st.info(
    "Exploratory analysis: review sales history, product and store performance, and weekday patterns. "
    "Forecasting models will be added only after the data has been explored and validated."
)

uploaded = st.sidebar.file_uploader("Upload sales CSV", type=["csv"])
local_dataset = Path(__file__).resolve().parent / "data" / "raw" / "train.csv"

@st.cache_data(show_spinner="Loading and validating the sales dataset...")
def load_local_dataset(path: str, modified_time_ns: int):
    # The modification timestamp invalidates the cache when the local CSV changes.
    return load_sales_csv(path)

df = load_demo_data()
data_source = "Built-in synthetic demo data"
quality_report = None

try:
    if uploaded is not None:
        cleaned_df, quality_report = load_sales_csv(uploaded)
        selected_source = f"Uploaded file: {uploaded.name}"
    elif local_dataset.is_file():
        cleaned_df, quality_report = load_local_dataset(
            str(local_dataset), local_dataset.stat().st_mtime_ns
        )
        selected_source = "Local Kaggle training dataset (data/raw/train.csv)"
    else:
        cleaned_df = None
        selected_source = None

    if cleaned_df is not None:
        if quality_report["errors"]:
            for error in quality_report["errors"]:
                st.sidebar.error(error)
            st.warning("The selected CSV could not be used. Showing built-in demo data instead.")
        elif cleaned_df.empty:
            st.warning("No usable records were found. Showing built-in demo data instead.")
        else:
            df = cleaned_df
            data_source = selected_source
            st.sidebar.success("CSV loaded and validated.")
    else:
        st.sidebar.caption("No local CSV found. Using built-in demo data.")
except Exception as exc:
    st.sidebar.error(f"Could not read the selected CSV: {exc}")
    st.warning("Showing built-in demo data instead.")

st.caption(f"**Data source:** {data_source}")

if quality_report is not None:
    st.subheader("Data quality report")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Rows received", quality_report["rows_received"])
    q2.metric("Usable rows", quality_report["rows_valid"])
    q3.metric("Duplicate rows", quality_report["duplicate_rows"])
    q4.metric("Rows excluded", quality_report["rows_received"] - quality_report["rows_valid"])
    with st.expander("Validation details", expanded=True):
        for message in quality_report["errors"]:
            st.error(message)
        for message in quality_report["warnings"]:
            st.warning(message)
        if not quality_report["errors"] and not quality_report["warnings"]:
            st.success("All uploaded rows passed the current validation checks.")
        st.caption(
            "Duplicate rows are flagged but retained because automatically deleting them "
            "could remove legitimate repeated transactions."
        )

summary = summarize_sales_data(df)
daily = daily_sales(df)
products = top_products(df, limit=10)
stores = store_sales(df)
weekdays = weekday_sales(df)

st.subheader("Sales overview")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Units sold", f"{summary['total_units']:,.0f}")
c2.metric("Average daily units", f"{summary['avg_daily_units']:,.1f}")
c3.metric("Products", summary["products"])
c4.metric("Stores", summary["stores"])

if summary["rows"]:
    st.caption(
        f"Records: {summary['rows']:,}  |  Date range: {summary['date_start']} to "
        f"{summary['date_end']}  |  Days represented: {summary['days_covered']:,}"
    )

st.subheader("Sales over time")
if not daily.empty:
    st.plotly_chart(
        px.line(daily, x="date", y="sales", markers=True, title="Daily units sold"),
        width="stretch",
    )
else:
    st.info("No sales records are available to chart.")

left, right = st.columns(2)
with left:
    st.subheader("Top products")
    st.plotly_chart(
        px.bar(products, x="item", y="sales", title="Top products by total units sold"),
        width="stretch",
    )
with right:
    st.subheader("Sales by store")
    st.plotly_chart(
        px.bar(stores, x="store", y="sales", title="Total units sold by store"),
        width="stretch",
    )

st.subheader("Average sales by weekday")
st.plotly_chart(
    px.bar(weekdays, x="weekday", y="sales", title="Average units sold per sales record by weekday"),
    width="stretch",
)

with st.expander("Explore the data", expanded=False):
    tab1, tab2, tab3 = st.tabs(["Top products", "Store summary", "Recent records"])
    with tab1:
        st.dataframe(products, width="stretch", hide_index=True)
    with tab2:
        st.dataframe(stores, width="stretch", hide_index=True)
    with tab3:
        st.dataframe(df.sort_values("date", ascending=False).head(20), width="stretch", hide_index=True)

st.subheader("Additional data observations")
o1, o2, o3 = st.columns(3)
o1.metric("Zero-sales records", f"{summary['zero_sales_rows']:,}")
o2.metric("Median daily units", f"{summary['median_daily_units']:,.1f}")
o3.metric("Average units per record", f"{(summary['total_units'] / summary['rows']):,.2f}" if summary["rows"] else "0")

st.caption(
    "Demo figures are synthetic and illustrative. Weekday averages describe the uploaded records; "
    "they are not forecasts. No machine-learning forecast or inventory recommendation is presented yet."
)
