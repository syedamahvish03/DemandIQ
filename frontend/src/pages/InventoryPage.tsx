import { useState } from "react";
import type { FormEvent } from "react";
import { ArrowLeft, Boxes, Download, FileSpreadsheet, LoaderCircle, UploadCloud } from "lucide-react";
import { Link } from "react-router-dom";
import { downloadInventoryTemplate, generateInventoryRecommendations } from "../lib/api";
import { downloadCsv } from "../lib/csv";
import type { InventoryResult } from "../lib/api";
import { saveInventoryAnalysis } from "../lib/analysisRuns";
import { getWorkspaceSalesFile } from "../lib/workspaceSales";

type ForecastHorizon = 7 | 15 | 30;

export default function InventoryPage() {
  const [salesFile, setSalesFile] = useState<File | null>(null);
  const [inventoryFile, setInventoryFile] = useState<File | null>(null);
  const [forecastHorizon, setForecastHorizon] = useState<ForecastHorizon>(15);
  const [result, setResult] = useState<InventoryResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [templateLoading, setTemplateLoading] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [workspaceLoading, setWorkspaceLoading] = useState(false);

  async function handleWorkspaceSalesLoad() {
    setWorkspaceLoading(true);
    setError("");
    setResult(null);
    try {
      const source = await getWorkspaceSalesFile();
      setSalesFile(source.file);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Workspace sales data could not be loaded.");
    } finally {
      setWorkspaceLoading(false);
    }
  }

  async function handleTemplateDownload() {
    if (!salesFile) {
      setError("Choose your historical sales CSV first.");
      return;
    }
    setTemplateLoading(true);
    setError("");
    try {
      const blob = await downloadInventoryTemplate(salesFile);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "demandiq_inventory_template.csv";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The template could not be created.");
    } finally {
      setTemplateLoading(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!salesFile || !inventoryFile) {
      setError("Choose both the historical sales CSV and completed inventory CSV.");
      return;
    }
    setLoading(true);
    setError("");
    setSaveMessage("");
    setResult(null);
    try {
      const inventoryResult = await generateInventoryRecommendations(salesFile, inventoryFile, forecastHorizon);
      setResult(inventoryResult);
      try {
        await saveInventoryAnalysis(inventoryResult, salesFile.name, inventoryFile.name);
        setSaveMessage("These inventory recommendations have been saved to your private workspace.");
      } catch (saveError) {
        setSaveMessage(saveError instanceof Error
          ? `Recommendations generated, but cloud saving failed: ${saveError.message}`
          : "Recommendations generated, but they could not be saved to your cloud workspace.");
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Inventory recommendations could not be calculated.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="forecast-page">
      <div className="forecast-container">
        <div className="forecast-page-links"><Link to="/workspace" className="forecast-back"><ArrowLeft size={16} /> Back to DemandIQ</Link><Link to="/workspace/forecasts" className="forecast-back">Open demand forecasts →</Link></div>
        <div className="forecast-heading">
          <span className="forecast-eyebrow"><Boxes size={15} /> INVENTORY PLANNING</span>
          <h1>Plan your replenishment</h1>
          <p>Use sales already imported into your private workspace, then add actual stock and supplier lead-time inputs to calculate replenishment guidance.</p>
        </div>

        <section className="forecast-card">
          <form onSubmit={handleSubmit}>
            <label className="forecast-field-label" htmlFor="inventory-sales-file">1. Historical sales data</label>
            <button type="button" className="button button-quiet button-small" onClick={handleWorkspaceSalesLoad} disabled={workspaceLoading || loading}>
              {workspaceLoading ? <><LoaderCircle className="forecast-spinner" size={15}/> Loading workspace sales…</> : "Use imported workspace sales"}
            </button>
            <label className="forecast-upload inventory-upload" htmlFor="inventory-sales-file">
              <UploadCloud size={24} />
              <strong>{salesFile ? salesFile.name : "Choose your sales CSV"}</strong>
              <span>{salesFile ? `${(salesFile.size / 1024).toFixed(1)} KB` : "Required columns: date, store, item, sales"}</span>
              <input id="inventory-sales-file" type="file" accept=".csv,text/csv" onChange={e => { setSalesFile(e.target.files?.[0] ?? null); setResult(null); setError(""); }} />
            </label>

            <div className="inventory-template-row">
              <div><b>Need an inventory input sheet?</b><span>Generate a blank template using the store and product pairs in your sales file.</span></div>
              <button type="button" className="button button-quiet button-small" onClick={handleTemplateDownload} disabled={!salesFile || templateLoading}>
                {templateLoading ? <LoaderCircle className="forecast-spinner" size={15}/> : <Download size={15}/>}
                Download template
              </button>
            </div>

            <label className="forecast-field-label inventory-second-label" htmlFor="inventory-stock-file">2. Completed inventory CSV</label>
            <label className="forecast-upload inventory-upload" htmlFor="inventory-stock-file">
              <FileSpreadsheet size={24} />
              <strong>{inventoryFile ? inventoryFile.name : "Choose your completed inventory CSV"}</strong>
              <span>{inventoryFile ? `${(inventoryFile.size / 1024).toFixed(1)} KB` : "Fill in actual stock and supplier values in the template"}</span>
              <input id="inventory-stock-file" type="file" accept=".csv,text/csv" onChange={e => { setInventoryFile(e.target.files?.[0] ?? null); setResult(null); setError(""); }} />
            </label>

            <label className="forecast-field-label inventory-second-label" htmlFor="inventory-forecast-horizon">3. Demand forecast horizon</label>
            <select
              id="inventory-forecast-horizon"
              className="forecast-select"
              value={forecastHorizon}
              onChange={event => { setForecastHorizon(Number(event.target.value) as ForecastHorizon); setResult(null); }}
            >
              <option value={7}>7 days</option>
              <option value={15}>15 days (recommended starting point)</option>
              <option value={30}>30 days</option>
            </select>
            <p className="inventory-horizon-help">Choose a horizon long enough to cover each product's supplier lead time plus review period. For example, 3 lead-time days + 7 review days requires at least 10 forecast days, so choose 15.</p>

            <div className="forecast-format-note">
              <FileSpreadsheet size={17}/>
              <span>Required inventory columns: <b>store, item, on_hand, on_order, backorders, lead_time_days, review_period_days</b>. Stock and time values must be non-negative; lead time and review period must be greater than zero.</span>
            </div>
            {error && <div className="forecast-error" role="alert">{error}</div>}
            <button className="button button-primary forecast-submit" type="submit" disabled={loading || !salesFile || !inventoryFile}>
              {loading ? <><LoaderCircle className="forecast-spinner" size={17}/> Calculating…</> : "Generate forecast-driven recommendations"}
            </button>
          </form>
        </section>

        {result && <section className="forecast-results" aria-live="polite">
          {saveMessage && <div className={saveMessage.startsWith("These inventory") ? "analysis-save-notice" : "analysis-save-warning"} role="status">{saveMessage}</div>}
          <div className="forecast-result-heading">
            <div><span className="forecast-eyebrow">INVENTORY RESULTS</span><h2>Forecast-driven replenishment</h2></div>
            <span className="forecast-success">Calculation complete</span>
          </div>
          <div className="forecast-stats">
            <div><small>PRODUCT SERIES</small><strong>{result.metadata.complete_recommendations}</strong></div>
            <div><small>REORDER REQUIRED</small><strong>{result.recommendations.filter(row => row.reorder_required).length}</strong></div>
            <div><small>FORECAST HORIZON</small><strong>{result.metadata.forecast_horizon_days} days</strong></div>
            <div><small>DEMAND BASIS</small><strong>ML forecast</strong></div>
          </div>
          {(result.metadata.excluded_forecast_rows ?? 0) > 0 && (
            <div className="forecast-quality" role="status">
              <b>Forecast coverage notice</b>
              <span>{result.metadata.excluded_forecast_rows} completed inventory row(s) were not recommended because their sales series did not reach the shared history cutoff. Recommendations below use only products with an eligible forecast.</span>
            </div>
          )}
          <section className="inventory-insights" aria-label="Inventory decision insights">
            <div className="inventory-insights-heading"><div><span className="forecast-eyebrow">DECISION SUPPORT</span><h3>What needs your attention?</h3><p>Alerts are generated from the stock and forecast values in this plan.</p></div>
              <span className={result.recommendations.some(row => row.reorder_required) ? "inventory-alert-count has-alerts" : "inventory-alert-count"}>{result.recommendations.filter(row => row.reorder_required).length} reorder alerts</span>
            </div>
            <div className="inventory-alert-list">
              {result.recommendations.filter(row => row.reorder_required).slice(0, 6).map(row => (
                <article className="inventory-alert-item" key={`${row.store}-${row.item}`}>
                  <span className="inventory-alert-symbol"><Boxes size={16}/></span>
                  <div><b>Replenishment recommended · {row.item}</b><p>Store {row.store} has an inventory position of {row.inventory_position.toFixed(1)}, at or below its reorder point of {row.reorder_point.toFixed(1)}.</p></div>
                  <strong>Order {row.recommended_order_qty}</strong>
                </article>
              ))}
              {!result.recommendations.some(row => row.reorder_required) && <div className="inventory-all-clear">No reorder alerts were triggered by the current inputs. Continue monitoring stock and refresh the plan when sales or inventory changes.</div>}
            </div>
            <div className="inventory-explanation-grid">
              <div><b>Reorder point</b><span>Forecast demand during supplier lead time + safety stock.</span></div>
              <div><b>Target stock</b><span>Forecast demand across lead time and review period + safety stock.</span></div>
              <div><b>Inventory position</b><span>On-hand stock + incoming orders − backorders.</span></div>
              <div><b>Suggested order</b><span>Ceiling of the positive gap between target stock and inventory position.</span></div>
            </div>
          </section>
          {result.recommendations.length === 0 ? <p className="inventory-empty">No complete recommendations yet. Check that the inventory CSV contains stock and lead-time values for products with matching sales history.</p> :
            <div className="forecast-table-wrap">
              <div className="forecast-table-title">
                <div><b>Recommended stock levels</b><span>Demand totals come from the generated forecast</span></div>
                <button
                  type="button"
                  className="button data-export-button"
                  onClick={() => downloadCsv(
                    "demandiq_inventory_recommendations.csv",
                    [
                      "store", "item", "on_hand", "on_order", "backorders",
                      "lead_time_days", "review_period_days", "avg_daily_demand",
                      "daily_demand_std", "demand_records", "safety_stock",
                      "demand_basis", "forecast_lead_demand",
                      "forecast_protection_demand", "reorder_point", "target_stock",
                      "inventory_position", "recommended_order_qty", "reorder_required",
                    ],
                    result.recommendations.map((row) => [
                      row.store, row.item, row.on_hand, row.on_order, row.backorders,
                      row.lead_time_days, row.review_period_days, row.avg_daily_demand,
                      row.daily_demand_std, row.demand_records, row.safety_stock,
                      row.demand_basis, row.forecast_lead_demand,
                      row.forecast_protection_demand, row.reorder_point, row.target_stock,
                      row.inventory_position, row.recommended_order_qty, row.reorder_required,
                    ]),
                  )}
                >
                  <Download size={15} /> Export recommendations
                </button>
              </div>
              <table className="forecast-table inventory-table">
                <thead><tr><th>Store</th><th>Product</th><th>On hand</th><th>Forecast lead demand</th><th>Forecast cover demand</th><th>Reorder point</th><th>Target stock</th><th>Suggested order</th><th>Status</th></tr></thead>
                <tbody>{result.recommendations.map((row, index) => <tr key={`${row.store}-${row.item}-${index}`}>
                  <td>{row.store}</td><td>{row.item}</td><td>{row.on_hand}</td><td>{row.forecast_lead_demand.toFixed(1)}</td><td>{row.forecast_protection_demand.toFixed(1)}</td><td>{row.reorder_point.toFixed(1)}</td><td>{row.target_stock.toFixed(1)}</td><td><b>{row.recommended_order_qty}</b></td>
                  <td><span className={row.reorder_required ? "inventory-status inventory-status-alert" : "inventory-status"}>{row.reorder_required ? "Reorder" : "On track"}</span></td>
                </tr>)}</tbody>
              </table>
            </div>
          }
          <p className="forecast-disclaimer">Demand totals are calculated from the Random Forest forecast for the selected horizon. Reorder point uses forecast demand during supplier lead time plus historical demand variability for safety stock. Target stock covers lead time plus review period, with incoming orders and backorders included in inventory position. These are planning estimates, not purchase orders. No inventory values are inferred or saved.</p>
        </section>}
      </div>
    </main>
  );
}
