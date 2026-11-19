import { useEffect, useState } from "react";
import type { ChangeEvent } from "react";
import { BarChart3, Boxes, CheckCircle2, Clock3, FileSpreadsheet, FileUp, LoaderCircle, ShieldCheck, UploadCloud, XCircle } from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { validateSalesCsv } from "../lib/api";
import type { SalesValidationResult } from "../lib/api";
import { getProductCount, getSalesImports, importSalesCsv } from "../lib/salesImports";
import type { SalesImport } from "../lib/salesImports";
import { useAuth } from "../lib/AuthContext";

export default function SalesPage() {
  const { session, signOut } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [validation, setValidation] = useState<SalesValidationResult | null>(null);
  const [imports, setImports] = useState<SalesImport[]>([]);
  const [productCount, setProductCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function refreshHistory() {
    setLoadingHistory(true);
    try {
      const [history, products] = await Promise.all([getSalesImports(), getProductCount()]);
      setImports(history);
      setProductCount(products);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load workspace data.");
    } finally {
      setLoadingHistory(false);
    }
  }

  useEffect(() => {
    void refreshHistory();
  }, []);

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    setValidation(null);
    setError("");
    setNotice("");
  }

  async function handleValidate() {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Choose a .csv file. Other file formats are not supported.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("The selected file exceeds the 10 MB upload limit.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await validateSalesCsv(file);
      setValidation(result);
      if (result.can_import) {
        setNotice("Validation passed. Review the preview and import when ready.");
      }
    } catch (validationError) {
      setError(validationError instanceof Error ? validationError.message : "The CSV could not be validated.");
    } finally {
      setBusy(false);
    }
  }

  async function handleImport() {
    if (!file || !validation?.can_import) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await importSalesCsv(file, validation);
      setNotice("Sales data imported successfully. Your source CSV is stored privately in this workspace.");
      setFile(null);
      setValidation(null);
      const input = document.getElementById("workspace-sales-file") as HTMLInputElement | null;
      if (input) input.value = "";
      await refreshHistory();
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : "The sales data could not be imported.");
    } finally {
      setBusy(false);
    }
  }

  const firstName = session?.user.user_metadata?.full_name?.split(/\\s+/)[0] || session?.user.email?.split("@")[0] || "there";

  return (
    <main className="workspace-shell">
      <aside className="workspace-sidebar">
        <Link className="workspace-brand" to="/"><span className="brand-mark"><BarChart3 size={19}/></span><span>Demand<span className="brand-iq">IQ</span></span></Link>
        <span className="workspace-nav-label">WORKSPACE</span>
        <nav className="workspace-nav" aria-label="Workspace navigation">
          <NavLink to="/workspace" end className={({ isActive }) => isActive ? "workspace-nav-link active" : "workspace-nav-link"}><BarChart3 size={17}/>Overview</NavLink>
          <NavLink to="/workspace/sales" className={({ isActive }) => isActive ? "workspace-nav-link active" : "workspace-nav-link"}><FileUp size={17}/>Sales & imports</NavLink>
          <NavLink to="/workspace/forecasts" className={({ isActive }) => isActive ? "workspace-nav-link active" : "workspace-nav-link"}><FileSpreadsheet size={17}/>Demand forecasts</NavLink>
          <NavLink to="/workspace/inventory" className={({ isActive }) => isActive ? "workspace-nav-link active" : "workspace-nav-link"}><Boxes size={17}/>Inventory planning</NavLink>
          <NavLink to="/workspace/analyses" className={({ isActive }) => isActive ? "workspace-nav-link active" : "workspace-nav-link"}><Clock3 size={17}/>Saved analyses</NavLink>
        </nav>
        <div className="workspace-sidebar-bottom"><div className="workspace-help-icon"><ShieldCheck size={17}/></div><b>Private workspace data</b><p>Sales records and source files are scoped to your signed-in account.</p><button className="workspace-signout" onClick={() => void signOut()}>Sign out</button></div>
      </aside>

      <section className="workspace-main">
        <header className="workspace-topbar"><div><span className="workspace-topbar-label">DEMANDIQ WORKSPACE</span><span className="workspace-account-email">{session?.user.email}</span></div><span className="workspace-secure"><ShieldCheck size={15}/> Secure account</span></header>
        <div className="workspace-content sales-workspace-content">
          <div className="workspace-welcome"><div><span className="forecast-eyebrow">WORKSPACE DATA FOUNDATION</span><h1>Sales & imports</h1><p>Bring historical sales into your private workspace, validate quality, and keep a traceable import history.</p></div></div>

          <div className="sales-summary-grid">
            <div className="sales-summary-card"><span>PRODUCTS IN CATALOGUE</span><strong>{productCount.toLocaleString()}</strong><small>Distinct item identifiers found in imports</small></div>
            <div className="sales-summary-card"><span>COMPLETED IMPORTS</span><strong>{imports.filter((item) => item.status === "completed").length}</strong><small>Recent import records in this workspace</small></div>
            <div className="sales-summary-card"><span>SALES ROWS IMPORTED</span><strong>{imports.reduce((total, item) => total + item.rows_imported, 0).toLocaleString()}</strong><small>Across the 50 most recent imports</small></div>
          </div>

          <section className="sales-panel-card">
            <div className="sales-panel-heading"><div><span className="forecast-eyebrow"><UploadCloud size={14}/> DATA IMPORT</span><h2>Import historical sales</h2><p>Upload a daily sales CSV. DemandIQ checks it before writing anything to your workspace.</p></div><span className="sales-file-limit">MAX 10 MB</span></div>
            <label className="forecast-upload sales-upload" htmlFor="workspace-sales-file"><UploadCloud size={25}/><strong>{file ? file.name : "Choose your sales CSV"}</strong><span>{file ? `${(file.size / 1024).toFixed(1)} KB · Select another file to replace` : "CSV only · Your original file is stored in private Supabase Storage"}</span><input id="workspace-sales-file" type="file" accept=".csv,text/csv" onChange={handleFileChange}/></label>
            <div className="forecast-format-note"><FileSpreadsheet size={17}/><span>Required columns: <b>date, store, item, sales</b>. Duplicate store-item dates block import. Invalid rows are excluded and reported before you continue.</span></div>
            <div className="sales-import-actions"><button className="button button-primary" type="button" onClick={() => void handleValidate()} disabled={!file || busy}>{busy ? <><LoaderCircle className="forecast-spinner" size={16}/> Working…</> : "Validate file"}</button>{validation?.can_import && <button className="button button-dark" type="button" onClick={() => void handleImport()} disabled={busy}>{busy ? "Importing…" : "Import validated data"}</button>}</div>
            {error && <div className="forecast-error" role="alert">{error}</div>}
            {notice && <div className="analysis-save-notice" role="status">{notice}</div>}
            {validation && <div className="sales-validation-result">
              <div className="sales-validation-heading"><div><b>Validation report</b><span>{validation.can_import ? "Ready to import" : "Needs attention"}</span></div>{validation.can_import ? <CheckCircle2 color="#25845e"/> : <XCircle color="#b65b4b"/>}</div>
              <div className="sales-quality-grid"><div><small>ROWS RECEIVED</small><strong>{validation.quality_report.rows_received.toLocaleString()}</strong></div><div><small>VALID ROWS</small><strong>{validation.quality_report.rows_valid.toLocaleString()}</strong></div><div><small>EXCLUDED</small><strong>{validation.excluded_rows.toLocaleString()}</strong></div><div><small>DUPLICATE DAILY KEYS</small><strong>{validation.quality_report.duplicate_rows.toLocaleString()}</strong></div></div>
              {validation.blocking_issues.map((issue) => <p className="sales-blocking-issue" key={issue}>{issue}</p>)}
              {validation.quality_report.warnings.map((warning) => <p className="sales-warning" key={warning}>{warning}</p>)}
              <div className="forecast-table-wrap"><div className="forecast-table-title"><b>Cleaned data preview</b><span>First {validation.preview_rows.length} accepted rows</span></div><table className="forecast-table"><thead><tr><th>Date</th><th>Store</th><th>Item</th><th>Units sold</th></tr></thead><tbody>{validation.preview_rows.map((row, index) => <tr key={`${row.date}-${row.store}-${row.item}-${index}`}><td>{row.date}</td><td>{row.store}</td><td>{row.item}</td><td>{row.sales}</td></tr>)}</tbody></table></div>
            </div>}
          </section>

          <section className="sales-panel-card sales-history-card">
            <div className="sales-panel-heading"><div><span className="forecast-eyebrow"><Clock3 size={14}/> DATA PROVENANCE</span><h2>Import history</h2><p>Review recent source files, row counts and import status.</p></div><button type="button" className="button data-export-button" onClick={() => void refreshHistory()} disabled={loadingHistory}>Refresh</button></div>
            {loadingHistory ? <p className="sales-history-empty">Loading import history…</p> : imports.length === 0 ? <div className="sales-history-empty"><FileUp size={25}/><b>No sales imports yet</b><span>Validated imports will appear here with their source filename and row counts.</span></div> : <div className="sales-history-list">{imports.map((item) => <article className="sales-history-row" key={item.id}><div className="sales-history-icon"><FileSpreadsheet size={18}/></div><div className="sales-history-main"><b>{item.filename}</b><span>{new Date(item.created_at).toLocaleString()} · {item.rows_imported.toLocaleString()} imported · {item.rows_excluded.toLocaleString()} excluded</span></div><span className={item.status === "completed" ? "sales-import-status complete" : "sales-import-status"}>{item.status}</span></article>)}</div>}
          </section>
          <div className="workspace-data-note"><ShieldCheck size={17}/><span><b>Workspace isolation is enforced by Supabase Row Level Security.</b> Source CSV files are stored in a private bucket. Sales and product records are associated with your personal workspace.</span></div>
        </div>
      </section>
    </main>
  );
}
