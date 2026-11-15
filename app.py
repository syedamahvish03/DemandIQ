from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="DemandIQ", page_icon="📦", layout="wide")
REQUIRED_COLUMNS = {"date", "store", "item", "sales"}

def load_demo_data():
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=90, freq="D")
    rows = []
    for store in [1, 2]:
        for item in [101, 102, 103]:
            for i, date in enumerate(dates):
                sales = max(0, round(18 + item % 7 + 5 * (i % 7 == 5) + 3 * (i % 7 == 6) + ((i * item + store) % 9 - 4)))
                rows.append({"date": date, "store": store, "item": item, "sales": sales})
    return pd.DataFrame(rows)

def validate_sales_data(data):
    errors = []
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        return False, ["Missing required columns: " + ", ".join(sorted(missing))]
    if data.empty:
        errors.append("The uploaded file contains no rows.")
    if data["date"].isna().any():
        errors.append("Some date values could not be read.")
    sales = pd.to_numeric(data["sales"], errors="coerce")
    if sales.isna().any():
        errors.append("Sales must contain numeric values.")
    elif (sales < 0).any():
        errors.append("Sales cannot be negative.")
    return not errors, errors

st.title("📦 DemandIQ")
st.caption("AI-powered retail demand forecasting and inventory intelligence")
st.info("Day 1 foundation: this dashboard currently uses clearly labelled demo data. Forecasting models will be added after data exploration and validation.")

uploaded = st.sidebar.file_uploader("Upload sales CSV", type=["csv"])
if uploaded:
    try:
        sales_df = pd.read_csv(uploaded, parse_dates=["date"])
        valid, errors = validate_sales_data(sales_df)
        if valid:
            st.sidebar.success("CSV structure validated.")
            df = sales_df.copy()
        else:
            for error in errors:
                st.sidebar.error(error)
            df = load_demo_data()
            st.warning("Showing demo data because the uploaded file did not pass validation.")
    except Exception as exc:
        st.sidebar.error(f"Could not read this CSV: {exc}")
        df = load_demo_data()
else:
    df = load_demo_data()
    st.sidebar.caption("Using built-in demo data.")

df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
df = df.dropna(subset=["date", "sales"])
total_sales = int(df["sales"].sum()) if not df.empty else 0
daily_average = round(df.groupby("date")["sales"].sum().mean(), 1) if not df.empty else 0
product_count = df["item"].nunique() if "item" in df.columns else 0
store_count = df["store"].nunique() if "store" in df.columns else 0
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
    st.warning("No valid sales rows are available to chart.")

left, right = st.columns(2)
with left:
    st.subheader("Top products")
    if "item" in df.columns:
        top_items = df.groupby("item", as_index=False)["sales"].sum().nlargest(10, "sales")
        st.plotly_chart(px.bar(top_items, x="item", y="sales", title="Top products by units sold"), use_container_width=True)
with right:
    st.subheader("Recent sales records")
    st.dataframe(df.sort_values("date", ascending=False).head(12), use_container_width=True, hide_index=True)

st.subheader("Next development milestones")
st.markdown("- Day 2: exploratory data analysis and data-quality checks\n- Day 3: time-series features and a simple baseline\n- Day 4: train and evaluate forecasting models\n- Day 5: convert forecasts into inventory recommendations")
st.caption("Demo figures are illustrative. No machine-learning forecast or inventory recommendation is being presented yet.")
