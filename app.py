import pandas as pd
import plotly.express as px
import streamlit as st

from data_validation import validate_sales_data

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
    "Day 1 foundation: upload retail sales data, validate its quality, and explore the dashboard. "
    "Forecasting models will be added after data exploration."
)

uploaded = st.sidebar.file_uploader("Upload sales CSV", type=["csv"])
df = load_demo_data()
data_source = "Built-in synthetic demo data"
quality_report = None

if uploaded is not None:
    try:
        uploaded_df = pd.read_csv(uploaded)
        cleaned_df, quality_report = validate_sales_data(uploaded_df)
        if quality_report["errors"]:
            for error in quality_report["errors"]:
                st.sidebar.error(error)
            st.warning("The uploaded file could not be used. Showing built-in demo data instead.")
        elif cleaned_df.empty:
            st.warning("No usable records were found. Showing built-in demo data instead.")
        else:
            df = cleaned_df
            data_source = f"Uploaded file: {uploaded.name}"
            st.sidebar.success("CSV loaded. Review the data-quality report below.")
    except Exception as exc:
        st.sidebar.error(f"Could not read this CSV: {exc}")
        st.warning("Showing built-in demo data instead.")
else:
    st.sidebar.caption("Using built-in demo data.")

st.caption(f"**Data source:** {data_source}")

if quality_report is not None:
    st.subheader("Data quality report")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Rows received", quality_report["rows_received"])
    q2.metric("Usable rows", quality_report["rows_valid"])
    q3.metric("Duplicate rows", quality_report["duplicate_rows"])
    excluded = quality_report["rows_received"] - quality_report["rows_valid"]
    q4.metric("Rows excluded", excluded)
    with st.expander("Validation details", expanded=True):
        if quality_report["errors"]:
            for message in quality_report["errors"]:
                st.error(message)
        if quality_report["warnings"]:
            for message in quality_report["warnings"]:
                st.warning(message)
        if not quality_report["errors"] and not quality_report["warnings"]:
            st.success("All uploaded rows passed the current validation checks.")
        st.caption("Duplicate rows are flagged but retained because automatically deleting them could remove legitimate repeated transactions.")

total_sales = int(df["sales"].sum()) if not df.empty else 0
daily_average = round(df.groupby("date")["sales"].sum().mean(), 1) if not df.empty else 0
product_count = df["item"].nunique() if not df.empty else 0
store_count = df["store"].nunique() if not df.empty else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Units sold", f"{total_sales:,}")
c2.metric("Avg. daily units", daily_average)
c3.metric("Products", product_count)
c4.metric("Stores", store_count)

st.subheader("Sales over time")
daily = df.groupby("date", as_index=False)["sales"].sum().sort_values("date")
if not daily.empty:
    st.plotly_chart(px.line(daily, x="date", y="sales", markers=True, title="Daily units sold"), use_container_width=True)
else:
    st.info("No sales records are available to chart.")

left, right = st.columns(2)
with left:
    st.subheader("Top products")
    top_items = df.groupby("item", as_index=False)["sales"].sum().nlargest(10, "sales")
    st.plotly_chart(px.bar(top_items, x="item", y="sales", title="Top products by units sold"), use_container_width=True)
with right:
    st.subheader("Recent sales records")
    st.dataframe(df.sort_values("date", ascending=False).head(12), use_container_width=True, hide_index=True)

st.subheader("Next development milestones")
st.markdown(
    "- Day 2: exploratory data analysis and product/store trends\n"
    "- Day 3: time-series features and a simple baseline\n"
    "- Day 4: train and evaluate forecasting models\n"
    "- Day 5: convert forecasts into inventory recommendations"
)
st.caption(
    "Demo figures are illustrative. No machine-learning forecast or inventory recommendation is being presented yet."
)
