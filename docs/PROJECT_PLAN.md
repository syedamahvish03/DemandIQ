# DemandIQ — Eight-Day MVP Plan

Time budget: approximately 2–3 hours per day. The goal is a working, demonstrable portfolio application, not a production-ready multi-tenant SaaS.

| Day | Focus | Deliverable |
|---|---|---|
| 1 | Foundation | Environment, dependencies, repository structure, first Streamlit dashboard |
| 2 | Exploratory data analysis | Data-quality report, product/store summaries, trends and charts |
| 3 | Features and baseline | Lag/rolling/date features and a time-series baseline |
| 4 | ML and evaluation | Train candidate model; chronological validation; MAE, RMSE, WAPE and bias |
| 5 | Inventory intelligence | Lead-time demand, safety stock, reorder point and suggested order quantity |
| 6 | User interface | Dashboard, data, forecast and inventory views |
| 7 | Integration | Upload-to-insight workflow, forecast horizons and downloadable reports |
| 8 | Testing and delivery | Edge-case tests, documentation, screenshots and deployment attempt if stable |

## Scope decisions

- Streamlit keeps the MVP achievable within the available time.
- CSV/local data is used initially; hosted database and authentication are deferred.
- Live commerce integrations, billing, multi-tenancy and advanced conversational AI are out of scope.
- Forecasts must be compared with a sensible baseline using chronological splits; random train/test splitting is inappropriate for this time-series task.
- Inventory recommendations must state their assumptions. The starter sales dataset does not provide true on-hand stock or supplier lead times.
- No accuracy claims are made before evaluation.

## Initial expected CSV schema

Required: date, store, item, sales.

Inventory fields may be added later as optional user-provided inputs.
