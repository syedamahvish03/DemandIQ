from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from data_loader import load_sales_csv
from eda import daily_sales, store_sales, summarize_sales_data, top_products, weekday_sales
from forecasting import (
    chronological_baseline_backtest,
    evaluate_random_forest,
    forecast_future_demand,
    recursive_multi_horizon_backtest,
)
from inventory import (
    build_illustrative_inventory_inputs,
    build_inventory_template,
    calculate_inventory_recommendations,
)

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
    "Explore validated sales history, evaluate models on a chronological historical holdout, "
    "generate future 7-, 15- or 30-day demand forecasts, and use forecasted demand in inventory "
    "planning. Inventory outputs still use illustrative assumptions unless verified retailer stock "
    "and supplier inputs are uploaded."
)

uploaded = st.sidebar.file_uploader("Upload sales CSV", type=["csv"])
raw_data_dir = Path(__file__).resolve().parent / "data" / "raw"
local_dataset_candidates = [
    raw_data_dir / "train.csv",
    raw_data_dir / "train.csv" / "train.csv",
]
local_dataset = next((path for path in local_dataset_candidates if path.is_file()), None)

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
    elif local_dataset is not None:
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
sales_data_signature = str(pd.util.hash_pandas_object(df, index=True).sum())
st.caption(
    "Forecast metrics below describe historical holdout performance, not predictions of future sales."
)

dashboard_tab, forecast_tab, inventory_tab = st.tabs(
    ["Sales dashboard", "Forecast evaluation", "Inventory planning"]
)

with dashboard_tab:
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
        "Exploratory statistics describe the selected dataset. Forecasting below is a historical "
        "backtest, while inventory planning uses separately supplied or explicitly illustrative inputs."
    )


with forecast_tab:
    st.subheader("Future demand forecast — 7, 15 or 30 days")
    st.write(
        "Train a forecasting model on the available sales history and generate recursive daily "
        "predictions for every store-item series. Future values are model estimates, not actual sales."
    )
    horizon_days = st.selectbox(
        "Forecast horizon",
        [7, 15, 30],
        index=0,
        format_func=lambda days: f"{days} days",
        key="future_forecast_horizon",
    )
    if st.button("Generate future demand forecast", key="generate_future_forecast"):
        try:
            with st.spinner("Training the model and generating future predictions..."):
                future_forecast, future_metadata = forecast_future_demand(
                    df, horizon_days=int(horizon_days)
                )
            st.session_state["future_forecast_result"] = future_forecast
            st.session_state["future_forecast_metadata"] = future_metadata
            st.session_state["future_forecast_source"] = data_source
        except (ValueError, ImportError) as exc:
            st.session_state.pop("future_forecast_result", None)
            st.session_state.pop("future_forecast_metadata", None)
            st.error(f"Future forecasting is not available: {exc}")

    if "future_forecast_result" in st.session_state:
        future_forecast = st.session_state["future_forecast_result"]
        future_metadata = st.session_state["future_forecast_metadata"]
        f1, f2, f3 = st.columns(3)
        f1.metric("Forecast period", f"{future_metadata['forecast_start']} to {future_metadata['forecast_end']}")
        f2.metric("Store-item series", f"{future_metadata['series_count']:,}")
        f3.metric("Predicted units", f"{future_forecast['forecast_sales'].sum():,.0f}")
        st.caption(
            f"History ends {future_metadata['history_end']}. Model trained on "
            f"{future_metadata['training_rows_used']:,} historical feature rows. "
            "Forecasts are recursively generated: earlier predictions become later lag inputs."
        )
        future_daily = future_forecast.groupby("date", as_index=False)["forecast_sales"].sum()
        st.plotly_chart(
            px.line(
                future_daily, x="date", y="forecast_sales", markers=True,
                title="Predicted daily demand — all stores and products",
            ),
            width="stretch",
        )
        with st.expander("Explore forecast by store and product", expanded=False):
            st.dataframe(
                future_forecast.style.format({"forecast_sales": "{:,.2f}"}),
                width="stretch",
                hide_index=True,
            )
        st.download_button(
            "Download future demand forecast (CSV)",
            data=future_forecast.to_csv(index=False).encode("utf-8"),
            file_name=f"demandiq_{future_metadata['horizon_days']}_day_forecast.csv",
            mime="text/csv",
            key="download_future_forecast",
        )
        st.warning(
            "Forecasts are estimates based on historical sales patterns. They do not account for "
            "promotions, holidays, price changes, stockouts or future events unless those signals "
            "are added to the data and model."
        )

    st.divider()
    st.subheader("Forecast evaluation — Simple baselines")
    st.write(
        "DemandIQ creates historical lag and rolling-average features separately for each store-item "
        "series. The first benchmark compares two simple forecasting approaches before any machine-learning model."
    )

    @st.cache_data(show_spinner="Building time-series features and running chronological backtest...")
    def run_baseline(data: pd.DataFrame):
        return chronological_baseline_backtest(data, holdout_days=28)

    baseline_metrics = None
    try:
        baseline_metrics, baseline_predictions, baseline_metadata = run_baseline(df)
        m1, m2, m3 = st.columns(3)
        m1.metric("Backtest window", f"{baseline_metadata['holdout_start']} to {baseline_metadata['holdout_end']}")
        m2.metric("Evaluation records", f"{baseline_metadata['test_rows']:,}")
        m3.metric("Store-item series", f"{baseline_metadata['series_count']:,}")
        st.caption(
            "Evaluation method: chronological 28-day holdout with rolling one-step-ahead predictions. "
            "Each prediction uses only earlier observed sales."
        )
        st.dataframe(
            baseline_metrics.style.format({
                "MAE": "{:,.2f}", "RMSE": "{:,.2f}",
                "WAPE (%)": "{:.2f}", "Bias (%)": "{:.2f}",
            }),
            width="stretch", hide_index=True,
        )
        best_model = baseline_metrics.iloc[0]["model"]
        st.success(f"Best simple baseline by WAPE on this holdout: {best_model}")
        daily_comparison = (
            baseline_predictions.groupby("date", as_index=False)[
                ["actual", "seasonal_naive_7", "moving_average_7"]
            ].sum()
        )
        st.plotly_chart(
            px.line(
                daily_comparison, x="date",
                y=["actual", "seasonal_naive_7", "moving_average_7"],
                title="Actual vs baseline forecasts — daily total",
            ),
            width="stretch",
        )
        st.caption(
            "These are benchmark results, not a claim of future accuracy. This section uses "
            "rolling one-step-ahead evaluation; the recursive multi-horizon section below evaluates "
            "the production-style 7-, 15- and 30-day forecasting task."
        )
    except ValueError as exc:
        st.warning(f"Baseline evaluation is not available for this dataset: {exc}")


    st.divider()
    st.subheader("Forecast evaluation — Random Forest model")
    st.write(
        "A Random Forest model is now evaluated against the same final 28-day chronological "
        "holdout used by the simple baselines. Training uses only dates before the holdout."
    )

    @st.cache_data(show_spinner="Training and evaluating the Random Forest model...")
    def run_random_forest(data: pd.DataFrame):
        return evaluate_random_forest(data, holdout_days=28)

    try:
        rf_metrics, rf_predictions, rf_metadata = run_random_forest(df)
        r1, r2, r3 = st.columns(3)
        r1.metric("Training records used", f"{rf_metadata['train_rows_used']:,}")
        r2.metric("Evaluation records", f"{rf_metadata['test_rows']:,}")
        r3.metric("Holdout period", f"{rf_metadata['holdout_start']} to {rf_metadata['holdout_end']}")

        comparison = (
            pd.concat([baseline_metrics, rf_metrics], ignore_index=True)
            if baseline_metrics is not None
            else rf_metrics.copy()
        )
        comparison = comparison.sort_values("WAPE (%)").reset_index(drop=True)
        st.subheader("Model comparison")
        st.dataframe(
            comparison.style.format({
                "MAE": "{:,.2f}", "RMSE": "{:,.2f}",
                "WAPE (%)": "{:.2f}", "Bias (%)": "{:.2f}",
            }),
            width="stretch", hide_index=True,
        )
        st.download_button(
            "Download model comparison (CSV)",
            data=comparison.to_csv(index=False).encode("utf-8"),
            file_name="demandiq_model_comparison.csv",
            mime="text/csv",
            key="download_model_comparison",
        )
        best_model = comparison.iloc[0]["model"]
        st.success(f"Best evaluated model by WAPE on this holdout: {best_model}")

        rf_daily = rf_predictions.groupby("date", as_index=False)[
            ["actual", "random_forest"]
        ].sum()
        st.plotly_chart(
            px.line(
                rf_daily, x="date", y=["actual", "random_forest"],
                title="Actual vs Random Forest — daily total",
            ),
            width="stretch",
        )
        st.caption(
            "The Random Forest uses a deterministic sample of at most 200,000 historical training "
            "rows to keep execution practical. Results describe this dataset and holdout only; "
            "they do not guarantee future forecast accuracy."
        )
    except (ValueError, ImportError) as exc:
        st.warning(f"Random Forest evaluation is not available: {exc}")

    st.divider()
    st.subheader("Recursive multi-horizon evaluation — 7, 15 and 30 days")
    st.write(
        "This is the production-aligned comparison. Each model forecasts the complete "
        "30-day holdout recursively: predictions from earlier holdout days become inputs "
        "for later days. Actual holdout sales are never fed back into a model."
    )

    @st.cache_data(show_spinner="Running recursive 7-, 15- and 30-day model evaluation...")
    def run_multi_horizon_backtest(data: pd.DataFrame):
        return recursive_multi_horizon_backtest(data)

    try:
        multi_metrics, multi_predictions, multi_metadata = run_multi_horizon_backtest(df)
        h1, h2, h3 = st.columns(3)
        h1.metric("Holdout period", f"{multi_metadata['holdout_start']} to {multi_metadata['holdout_end']}")
        h2.metric("Store-item series", f"{multi_metadata['series_count']:,}")
        h3.metric("Training rows", f"{multi_metadata['training_rows_used']:,}")

        st.dataframe(
            multi_metrics.style.format({
                "MAE": "{:,.2f}", "RMSE": "{:,.2f}",
                "WAPE (%)": "{:.2f}", "Bias (%)": "{:.2f}",
            }),
            width="stretch",
            hide_index=True,
        )
        st.plotly_chart(
            px.line(
                multi_metrics,
                x="horizon_days",
                y="WAPE (%)",
                color="model",
                markers=True,
                title="WAPE by forecast horizon — lower is better",
            ),
            width="stretch",
        )
        st.download_button(
            "Download recursive multi-horizon metrics (CSV)",
            data=multi_metrics.to_csv(index=False).encode("utf-8"),
            file_name="demandiq_recursive_multi_horizon_metrics.csv",
            mime="text/csv",
            key="download_multi_horizon_metrics",
        )
        st.caption(
            "The 7-, 15- and 30-day scores are cumulative from the same holdout origin. "
            "This is one final holdout, not a multi-origin rolling backtest; results describe "
            "this dataset and evaluation window only."
        )
    except (ValueError, ImportError) as exc:
        st.warning(f"Recursive multi-horizon evaluation is not available: {exc}")

with inventory_tab:
    st.subheader("Inventory planning — Reorder analysis")
    st.write(
        "Explore replenishment calculations using either clearly labelled illustrative assumptions "
        "or verified stock and supplier data supplied by a retailer."
    )
    st.warning(
        "The Kaggle dataset contains sales history only. It does not contain actual stock, purchase "
        "orders, backorders or supplier lead times. Illustrative scenario results below are simulated "
        "for demonstration and must not be treated as real stock records or purchase advice."
    )

    try:
        inventory_template = build_inventory_template(df)
        template_csv = inventory_template.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download blank inventory input template (for future real data)",
            data=template_csv,
            file_name="demandiq_inventory_inputs.csv",
            mime="text/csv",
            key="download_inventory_template",
        )

        inventory_mode = st.radio(
            "Choose inventory data mode",
            ["Illustrative demo scenario", "Upload verified inventory data"],
            horizontal=True,
            key="inventory_mode",
        )

        if inventory_mode == "Illustrative demo scenario":
            st.info(
                "DEMO ONLY — DemandIQ estimates a demonstration stock level from recent average sales. "
                "Incoming orders and backorders are assumed to be zero. Lead time and review period are "
                "scenario settings, not Kaggle data."
            )
            a1, a2, a3 = st.columns(3)
            with a1:
                stock_cover_days = st.number_input(
                    "Assumed starting stock cover (days)", min_value=1, max_value=60,
                    value=7, step=1, key="demo_stock_cover",
                )
            with a2:
                demo_lead_time = st.number_input(
                    "Assumed supplier lead time (days)", min_value=1, max_value=60,
                    value=7, step=1, key="demo_lead_time",
                )
            with a3:
                demo_review_period = st.number_input(
                    "Assumed review period (days)", min_value=1, max_value=60,
                    value=7, step=1, key="demo_review_period",
                )
            inventory_inputs = build_illustrative_inventory_inputs(
                df,
                stock_cover_days=int(stock_cover_days),
                lead_time_days=int(demo_lead_time),
                review_period_days=int(demo_review_period),
            )
            st.caption(
                "Assumption details: on-hand stock = recent 28-day average daily sales × "
                f"{int(stock_cover_days)} days (rounded up); on-order = 0; backorders = 0; "
                f"lead time = {int(demo_lead_time)} days; review period = {int(demo_review_period)} days."
            )
        else:
            inventory_upload = st.file_uploader(
                "Upload completed inventory inputs (CSV)",
                type=["csv"],
                key="inventory_csv_upload",
                help="Use verified retailer stock and supplier values. Do not upload the blank template.",
            )
            if inventory_upload is not None:
                inventory_inputs = pd.read_csv(inventory_upload)
                st.caption("Using retailer-supplied inventory inputs. These values are not part of Kaggle.")
            else:
                inventory_inputs = pd.DataFrame(columns=list(inventory_template.columns))
                st.info("Upload a completed inventory CSV to calculate recommendations.")

        st.divider()
        st.subheader("Connect the demand forecast")
        st.write(
            "Generate a future forecast and use its predicted units for lead-time demand "
            "and target stock. Historical sales variability is still used for safety stock."
        )
        inventory_forecast_horizon = st.selectbox(
            "Forecast horizon for inventory planning",
            [7, 15, 30],
            index=2,
            format_func=lambda days: f"{days} days",
            key="inventory_forecast_horizon",
        )
        st.caption(
            "The forecast must cover at least lead time + review period. "
            "For example, 7 lead-time days + 7 review days requires at least a 14-day forecast."
        )
        if st.button("Generate demand forecast for inventory", key="generate_inventory_forecast"):
            try:
                with st.spinner("Training the model and generating the inventory demand forecast..."):
                    generated_forecast, generated_metadata = forecast_future_demand(
                        df, horizon_days=int(inventory_forecast_horizon)
                    )
                st.session_state["inventory_forecast_result"] = generated_forecast
                st.session_state["inventory_forecast_metadata"] = generated_metadata
                st.session_state["inventory_forecast_signature"] = sales_data_signature
                st.success(
                    f"Generated {generated_metadata['horizon_days']}-day forecast "
                    f"for {generated_metadata['series_count']:,} store-item series."
                )
            except (ValueError, ImportError) as exc:
                st.session_state.pop("inventory_forecast_result", None)
                st.session_state.pop("inventory_forecast_metadata", None)
                st.session_state.pop("inventory_forecast_signature", None)
                st.error(f"Could not generate the inventory demand forecast: {exc}")

        inventory_forecast = None
        if (
            "inventory_forecast_result" in st.session_state
            and st.session_state.get("inventory_forecast_signature") == sales_data_signature
        ):
            inventory_forecast = st.session_state["inventory_forecast_result"]
            forecast_metadata = st.session_state["inventory_forecast_metadata"]
            st.success(
                f"Inventory forecast ready: {forecast_metadata['forecast_start']} to "
                f"{forecast_metadata['forecast_end']} "
                f"({forecast_metadata['horizon_days']} days)."
            )
        else:
            st.info(
                "Generate an inventory demand forecast above before calculating "
                "forecast-driven replenishment recommendations."
            )

        if st.button("Calculate inventory recommendations", key="calculate_inventory"):
            try:
                if inventory_forecast is None:
                    st.warning(
                        "Generate a demand forecast for the currently selected sales dataset first."
                    )
                else:
                    recommendations, inventory_metadata = calculate_inventory_recommendations(
                        df, inventory_inputs, lookback_days=28, service_level_z=1.65,
                        demand_forecast=inventory_forecast,
                    )
                    if recommendations.empty:
                        st.warning(
                            "No complete inventory recommendations are available. Select the illustrative "
                            "scenario or upload verified stock and supplier inputs."
                        )
                    else:
                        if inventory_mode == "Illustrative demo scenario":
                            st.warning("SIMULATED OUTPUT — these recommendations use assumptions, not actual inventory.")
                        else:
                            st.success("Recommendations calculated from the uploaded inventory inputs.")
                        i1, i2, i3 = st.columns(3)
                        i1.metric("Items evaluated", f"{len(recommendations):,}")
                        i2.metric(
                            "Items at/below reorder point",
                            f"{int(recommendations['reorder_required'].sum()):,}",
                        )
                        i3.metric(
                            "Total suggested units", f"{int(recommendations['recommended_order_qty'].sum()):,}"
                        )
                        display_columns = [
                            "store", "item", "avg_daily_demand", "forecast_lead_demand",
                            "forecast_protection_demand", "on_hand", "on_order", "backorders",
                            "lead_time_days", "safety_stock", "reorder_point",
                            "inventory_position", "target_stock", "recommended_order_qty",
                            "reorder_required",
                        ]
                        st.dataframe(
                            recommendations[display_columns].style.format({
                                "avg_daily_demand": "{:,.2f}",
                                "forecast_lead_demand": "{:,.1f}",
                                "forecast_protection_demand": "{:,.1f}",
                                "safety_stock": "{:,.1f}",
                                "reorder_point": "{:,.1f}",
                                "inventory_position": "{:,.1f}",
                                "target_stock": "{:,.1f}",
                            }),
                            width="stretch",
                            hide_index=True,
                        )
                        result_csv = recommendations.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "Download inventory scenario results",
                            data=result_csv,
                            file_name="demandiq_inventory_recommendations.csv",
                            mime="text/csv",
                            key="download_inventory_recommendations",
                        )
                        st.caption(
                            f"Historical variability window: {inventory_metadata['demand_window_start']} to "
                            f"{inventory_metadata['demand_window_end']}. Reorder point and target stock use "
                            "the generated future forecast; safety stock uses historical demand variability. "
                            "These are planning calculations, not purchase orders."
                        )
            except (ValueError, KeyError) as exc:
                st.error(f"Could not calculate inventory recommendations: {exc}")
    except (ValueError, KeyError) as exc:
        st.warning(f"Inventory tools are not available for this dataset: {exc}")
