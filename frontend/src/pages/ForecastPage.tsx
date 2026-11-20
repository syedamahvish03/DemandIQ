import { useState } from "react";
import type { FormEvent } from "react";
import { ArrowLeft, BarChart3, Download, FileSpreadsheet, LoaderCircle, UploadCloud } from "lucide-react";
import { Link } from "react-router-dom";
import { generateForecast } from "../lib/api";
import { downloadCsv } from "../lib/csv";
import ForecastTrend from "../components/ForecastTrend";
import type { ForecastResult } from "../lib/api";
import { saveForecastAnalysis } from "../lib/analysisRuns";
import { getWorkspaceSalesFile } from "../lib/workspaceSales";

export default function ForecastPage() {
  const [file, setFile] = useState<File | null>(null);
  const [horizon, setHorizon] = useState<7 | 15 | 30>(7);
  const [result, setResult] = useState<ForecastResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [workspaceLoading, setWorkspaceLoading] = useState(false);

  async function handleWorkspaceSalesLoad() {
    setWorkspaceLoading(true);
    setError("");
    setResult(null);
    try {
      const source = await getWorkspaceSalesFile();
      setFile(source.file);
      setSaveMessage("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Workspace sales data could not be loaded.");
    } finally {
      setWorkspaceLoading(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Choose a sales CSV file before generating a forecast.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("The selected file exceeds the 10 MB upload limit.");
      return;
    }

    setLoading(true);
    setError("");
    setSaveMessage("");
    setResult(null);
    try {
      const forecast = await generateForecast(file, horizon);
      setResult(forecast);
      try {
        await saveForecastAnalysis(forecast, file.name);
        setSaveMessage("This forecast has been saved to your private workspace.");
      } catch (saveError) {
        setSaveMessage(saveError instanceof Error
          ? `Forecast generated, but cloud saving failed: ${saveError.message}`
          : "Forecast generated, but it could not be saved to your cloud workspace.");
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The forecast could not be generated. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="forecast-page">
      <div className="forecast-container">
        <div className="forecast-page-links"><Link to="/workspace" className="forecast-back"><ArrowLeft size={16} /> Back to DemandIQ</Link><Link to="/workspace/inventory" className="forecast-back">Open inventory planning →</Link></div>
        <div className="forecast-heading">
          <span className="forecast-eyebrow"><BarChart3 size={15} /> DEMAND PLANNING</span>
          <h1>Generate a demand forecast</h1>
          <p>Use sales already imported into your private workspace, or upload a separate CSV. DemandIQ validates the data and uses its forecasting model to estimate future demand.</p>
        </div>

        <section className="forecast-card">
          <form onSubmit={handleSubmit}>
            <label className="forecast-field-label" htmlFor="sales-file">Historical sales data</label>
            <button type="button" className="button button-quiet button-small" onClick={handleWorkspaceSalesLoad} disabled={workspaceLoading || loading}>
              {workspaceLoading ? <><LoaderCircle className="forecast-spinner" size={15}/> Loading workspace sales…</> : "Use imported workspace sales"}
            </button>
            <label className="forecast-upload" htmlFor="sales-file">
              <UploadCloud size={25} />
              <strong>{file ? file.name : "Choose a CSV file"}</strong>
              <span>{file ? `${(file.size / 1024).toFixed(1)} KB · Select another file to replace` : "Maximum 10 MB · CSV format only"}</span>
              <input
                id="sales-file"
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null);
                  setResult(null);
                  setError("");
                }}
              />
            </label>

            <div className="forecast-field">
              <label className="forecast-field-label" htmlFor="forecast-horizon">Forecast period</label>
              <select
                id="forecast-horizon"
                value={horizon}
                onChange={(event) => setHorizon(Number(event.target.value) as 7 | 15 | 30)}
              >
                <option value={7}>Next 7 days</option>
                <option value={15}>Next 15 days</option>
                <option value={30}>Next 30 days</option>
              </select>
            </div>

            <div className="forecast-format-note">
              <FileSpreadsheet size={17} />
              <span>Required columns: <b>date, store, item, sales</b>. Each store-item series must have at least 15 consecutive daily observations, with no duplicate dates.</span>
            </div>

            {error && <div className="forecast-error" role="alert">{error}</div>}

            <button className="button button-primary forecast-submit" type="submit" disabled={loading || !file}>
              {loading ? <><LoaderCircle className="forecast-spinner" size={17}/> Generating forecast…</> : "Generate forecast"}
            </button>
          </form>
        </section>

        {result && (
          <section className="forecast-results" aria-live="polite">
            {saveMessage && <div className={saveMessage.startsWith("This forecast") ? "analysis-save-notice" : "analysis-save-warning"} role="status">{saveMessage}</div>}
            <div className="forecast-result-heading">
              <div><span className="forecast-eyebrow">MODEL RESULTS</span><h2>Your demand forecast is ready</h2></div>
              <div className="forecast-result-actions">
                <span className="forecast-success">Forecast generated</span>
                <button
                  type="button"
                  className="button data-export-button"
                  onClick={() => downloadCsv(
                    "demandiq_demand_forecast.csv",
                    ["date", "store", "item", "forecast_sales", "forecast_step"],
                    result.forecast.map((row) => [
                      row.date, row.store, row.item, row.forecast_sales, row.forecast_step,
                    ]),
                  )}
                >
                  <Download size={15} /> Export full forecast
                </button>
              </div>
            </div>
            <div className="forecast-stats">
              <div><small>FORECAST PERIOD</small><strong>{result.metadata.horizon_days} days</strong></div>
              <div><small>PRODUCT SERIES</small><strong>{result.metadata.series_count.toLocaleString()}</strong></div>
              <div><small>FORECAST ROWS</small><strong>{result.metadata.forecast_rows.toLocaleString()}</strong></div>
              <div><small>HISTORY THROUGH</small><strong>{result.metadata.history_end}</strong></div>
            </div>
            <ForecastTrend rows={result.forecast} />
            <div className="forecast-quality">
              <b>Data validation</b>
              <span>{result.quality_report.rows_valid.toLocaleString()} of {result.quality_report.rows_received.toLocaleString()} rows accepted · {(result.quality_report.rows_received - result.quality_report.rows_valid).toLocaleString()} excluded</span>
              {result.quality_report.warnings.map((warning) => <p key={warning}>{warning}</p>)}
              {result.quality_report.errors.map((message) => <p key={message}>{message}</p>)}
            </div>
            <div className="forecast-table-wrap">
              <div className="forecast-table-title"><b>Forecast detail</b><span>Showing up to 100 rows</span></div>
              <table className="forecast-table">
                <thead><tr><th>Date</th><th>Store</th><th>Item</th><th>Forecast units</th></tr></thead>
                <tbody>
                  {result.forecast.slice(0, 100).map((row, index) => (
                    <tr key={`${row.date}-${row.store}-${row.item}-${index}`}>
                      <td>{row.date}</td><td>{row.store}</td><td>{row.item}</td><td>{row.forecast_sales.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.forecast.length > 100 && <p className="forecast-table-note">The API returned {result.forecast.length.toLocaleString()} forecast rows. This view displays the first 100.</p>}
            </div>
            <p className="forecast-disclaimer">These are model estimates based on the uploaded sales history, not guaranteed sales. Forecast accuracy depends on the quality and coverage of your data.</p>
          </section>
        )}
      </div>
    </main>
  );
}
