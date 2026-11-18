import { useState } from "react";
import type { FormEvent } from "react";
import { ArrowLeft, Boxes, Download, FileSpreadsheet, LoaderCircle, PackageCheck, UploadCloud } from "lucide-react";
import { Link } from "react-router-dom";
import { downloadInventoryTemplate, generateInventoryRecommendations } from "../lib/api";
import type { InventoryResult } from "../lib/api";

export default function InventoryPage() {
  const [salesFile, setSalesFile] = useState<File | null>(null);
  const [inventoryFile, setInventoryFile] = useState<File | null>(null);
  const [result, setResult] = useState<InventoryResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [templateLoading, setTemplateLoading] = useState(false);

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
    setResult(null);
    try {
      setResult(await generateInventoryRecommendations(salesFile, inventoryFile));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Inventory recommendations could not be calculated.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="forecast-page">
      <div className="forecast-container">
        <div className="forecast-page-links"><Link to="/" className="forecast-back"><ArrowLeft size={16} /> Back to DemandIQ</Link><Link to="/workspace/forecasts" className="forecast-back">Open demand forecasts →</Link></div>
        <div className="forecast-heading">
          <span className="forecast-eyebrow"><Boxes size={15} /> INVENTORY PLANNING</span>
          <h1>Plan your replenishment</h1>
          <p>Combine historical sales with your actual stock and supplier lead-time inputs to calculate reorder guidance.</p>
        </div>

        <section className="forecast-card">
          <form onSubmit={handleSubmit}>
            <label className="forecast-field-label" htmlFor="inventory-sales-file">1. Historical sales CSV</label>
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

            <div className="forecast-format-note">
              <FileSpreadsheet size={17}/>
              <span>Required inventory columns: <b>store, item, on_hand, on_order, backorders, lead_time_days, review_period_days</b>. Stock and time values must be non-negative; lead time and review period must be greater than zero.</span>
            </div>
            {error && <div className="forecast-error" role="alert">{error}</div>}
            <button className="button button-primary forecast-submit" type="submit" disabled={loading || !salesFile || !inventoryFile}>
              {loading ? <><LoaderCircle className="forecast-spinner" size={17}/> Calculating…</> : "Calculate inventory recommendations"}
            </button>
          </form>
        </section>

        {result && <section className="forecast-results" aria-live="polite">
          <div className="forecast-result-heading">
            <div><span className="forecast-eyebrow">INVENTORY RESULTS</span><h2>Replenishment analysis</h2></div>
            <span className="forecast-success">Calculation complete</span>
          </div>
          <div className="forecast-stats">
            <div><small>PRODUCT SERIES</small><strong>{result.metadata.complete_recommendations}</strong></div>
            <div><small>REORDER REQUIRED</small><strong>{result.recommendations.filter(row => row.reorder_required).length}</strong></div>
            <div><small>INPUT ROWS EXCLUDED</small><strong>{result.metadata.excluded_input_rows}</strong></div>
            <div><small>DEMAND BASIS</small><strong>28-day average</strong></div>
          </div>
          {result.recommendations.length === 0 ? <p className="inventory-empty">No complete recommendations yet. Check that the inventory CSV contains stock and lead-time values for products with matching sales history.</p> :
            <div className="forecast-table-wrap">
              <div className="forecast-table-title"><b>Recommended stock levels</b><span>Sorted by suggested order quantity</span></div>
              <table className="forecast-table inventory-table">
                <thead><tr><th>Store</th><th>Product</th><th>On hand</th><th>Reorder point</th><th>Target stock</th><th>Suggested order</th><th>Status</th></tr></thead>
                <tbody>{result.recommendations.map((row, index) => <tr key={`${row.store}-${row.item}-${index}`}>
                  <td>{row.store}</td><td>{row.item}</td><td>{row.on_hand}</td><td>{row.reorder_point.toFixed(1)}</td><td>{row.target_stock.toFixed(1)}</td><td><b>{row.recommended_order_qty}</b></td>
                  <td><span className={row.reorder_required ? "inventory-status inventory-status-alert" : "inventory-status"}>{row.reorder_required ? "Reorder" : "On track"}</span></td>
                </tr>)}</tbody>
              </table>
            </div>
          }
          <p className="forecast-disclaimer">Recommendations use the latest 28 days of historical sales and the stock, incoming-order, backorder and supplier timing values you supplied. They are planning estimates, not purchase orders. No inventory values are inferred or saved.</p>
        </section>}
      </div>
    </main>
  );
}
