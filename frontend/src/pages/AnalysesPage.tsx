import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Boxes, Clock3, FileDown, LineChart, LoaderCircle, RefreshCw, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { deleteSavedAnalysis, getSavedAnalyses } from "../lib/analysisRuns";
import type { SavedAnalysis } from "../lib/analysisRuns";
import { downloadCsv } from "../lib/csv";

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function exportSavedResult(analysis: SavedAnalysis) {
  if (analysis.analysis_type === "forecast") {
    const result = analysis.result as import("../lib/api").ForecastResult;
    downloadCsv(
      "demandiq_saved_forecast.csv",
      ["date", "store", "item", "forecast_sales", "forecast_step"],
      result.forecast.map((row) => [row.date, row.store, row.item, row.forecast_sales, row.forecast_step]),
    );
    return;
  }

  const result = analysis.result as import("../lib/api").InventoryResult;
  downloadCsv(
    "demandiq_saved_inventory_recommendations.csv",
    [
      "store", "item", "on_hand", "on_order", "backorders", "lead_time_days",
      "review_period_days", "avg_daily_demand", "daily_demand_std", "demand_records",
      "safety_stock", "demand_basis", "forecast_lead_demand",
      "forecast_protection_demand", "reorder_point", "target_stock",
      "inventory_position", "recommended_order_qty", "reorder_required",
    ],
    result.recommendations.map((row) => [
      row.store, row.item, row.on_hand, row.on_order, row.backorders,
      row.lead_time_days, row.review_period_days, row.avg_daily_demand,
      row.daily_demand_std, row.demand_records, row.safety_stock, row.demand_basis,
      row.forecast_lead_demand, row.forecast_protection_demand, row.reorder_point,
      row.target_stock, row.inventory_position, row.recommended_order_qty, row.reorder_required,
    ]),
  );
}

export default function AnalysesPage() {
  const [analyses, setAnalyses] = useState<SavedAnalysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState("");

  const loadAnalyses = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setAnalyses(await getSavedAnalyses());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Saved analyses could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAnalyses();
  }, [loadAnalyses]);

  async function handleDelete(id: string) {
    if (!window.confirm("Delete this saved analysis? This cannot be undone.")) return;
    setDeletingId(id);
    setError("");
    try {
      await deleteSavedAnalysis(id);
      setAnalyses((current) => current.filter((analysis) => analysis.id !== id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The analysis could not be deleted.");
    } finally {
      setDeletingId("");
    }
  }

  return (
    <main className="forecast-page">
      <div className="forecast-container">
        <div className="forecast-page-links">
          <Link to="/workspace" className="forecast-back"><ArrowLeft size={16} /> Back to DemandIQ</Link>
          <button type="button" className="button data-export-button" onClick={() => void loadAnalyses()} disabled={loading}>
            <RefreshCw size={14} /> Refresh history
          </button>
        </div>
        <div className="forecast-heading">
          <span className="forecast-eyebrow"><Clock3 size={15} /> WORKSPACE HISTORY</span>
          <h1>Saved analyses</h1>
          <p>Your forecast and inventory results, saved to your private DemandIQ workspace and available when you sign in again.</p>
        </div>

        {error && <div className="forecast-error" role="alert">{error}</div>}
        {loading ? (
          <section className="forecast-card analyses-empty"><LoaderCircle className="forecast-spinner" size={22} /> Loading your saved analyses…</section>
        ) : analyses.length === 0 ? (
          <section className="forecast-card analyses-empty">
            <Clock3 size={28} />
            <h2>No saved analyses yet</h2>
            <p>Generate a demand forecast or inventory plan. Successful results will appear here automatically.</p>
            <div className="analyses-empty-actions">
              <Link className="button button-primary button-small" to="/workspace/forecasts"><LineChart size={15}/> Generate forecast</Link>
              <Link className="button button-quiet analyses-secondary-button" to="/workspace/inventory"><Boxes size={15}/> Plan inventory</Link>
            </div>
          </section>
        ) : (
          <section className="analyses-list" aria-live="polite">
            <div className="analyses-list-heading"><b>{analyses.length} saved {analyses.length === 1 ? "analysis" : "analyses"}</b><span>Newest first</span></div>
            {analyses.map((analysis) => (
              <article className="analysis-card" key={analysis.id}>
                <div className="analysis-card-icon">{analysis.analysis_type === "forecast" ? <LineChart size={19}/> : <Boxes size={19}/>}</div>
                <div className="analysis-card-main">
                  <div className="analysis-card-title-row"><h2>{analysis.title}</h2><span className={analysis.analysis_type === "forecast" ? "analysis-type forecast-type" : "analysis-type inventory-type"}>{analysis.analysis_type}</span></div>
                  <p>{formatDate(analysis.created_at)} · {analysis.input_filename || "Uploaded data"}</p>
                  <div className="analysis-card-summary">
                    {Object.entries(analysis.summary ?? {}).map(([key, value]) => (
                      <span key={key}><b>{key.replaceAll("_", " ")}:</b> {String(value)}</span>
                    ))}
                  </div>
                  <details className="analysis-details">
                    <summary>View saved result data</summary>
                    <pre>{JSON.stringify(analysis.result, null, 2)}</pre>
                  </details>
                </div>
                <div className="analysis-card-actions">
                  <button type="button" className="button data-export-button" onClick={() => exportSavedResult(analysis)}><FileDown size={14}/> Export CSV</button>
                  <button type="button" className="button analysis-delete-button" onClick={() => void handleDelete(analysis.id)} disabled={deletingId === analysis.id}>
                    {deletingId === analysis.id ? <LoaderCircle className="forecast-spinner" size={14}/> : <Trash2 size={14}/>} Delete
                  </button>
                </div>
              </article>
            ))}
          </section>
        )}
      </div>
    </main>
  );
}
