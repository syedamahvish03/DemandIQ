import { ArrowRight, BarChart3, Boxes, Building2, CircleHelp, Clock3, FileUp, LineChart, PackageSearch, ShieldCheck, Store, TrendingUp } from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";
import PwaInstallPrompt from "../components/PwaInstallPrompt";

const workspaceLinks = [
  { to: "/workspace", label: "Overview", icon: BarChart3, end: true },
  { to: "/workspace/sales", label: "Sales & imports", icon: FileUp },
  { to: "/workspace/products", label: "Product catalogue", icon: PackageSearch },
  { to: "/workspace/suppliers", label: "Suppliers", icon: Building2 },
  { to: "/workspace/forecasts", label: "Demand forecasts", icon: LineChart },
  { to: "/workspace/inventory", label: "Inventory planning", icon: Boxes },
  { to: "/workspace/analyses", label: "Saved analyses", icon: Clock3 },
];

export default function DashboardPage() {
  const { session } = useAuth();
  const metadataName = session?.user.user_metadata?.full_name;
  const firstName = typeof metadataName === "string" && metadataName.trim()
    ? metadataName.trim().split(/\s+/)[0]
    : session?.user.email?.split("@")[0] ?? "there";

  return (
    <main className="workspace-shell">
      <aside className="workspace-sidebar">
        <Link className="workspace-brand" to="/">
          <span className="brand-mark"><TrendingUp size={19} /></span>
          <span>Demand<span className="brand-iq">IQ</span></span>
        </Link>
        <span className="workspace-nav-label">WORKSPACE</span>
        <nav className="workspace-nav" aria-label="Workspace navigation">
          {workspaceLinks.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => isActive ? "workspace-nav-link active" : "workspace-nav-link"}>
              <Icon size={17} />{label}
            </NavLink>
          ))}
        </nav>
        <div className="workspace-sidebar-bottom">
          <div className="workspace-help-icon"><CircleHelp size={17}/></div>
          <b>Building a clearer retail picture</b>
          <p>Start with your sales history, then explore demand and stock planning.</p>
        </div>
      </aside>

      <section className="workspace-main">
        <header className="workspace-topbar">
          <div><span className="workspace-topbar-label">DEMANDIQ WORKSPACE</span><span className="workspace-account-email">{session?.user.email}</span></div>
          <span className="workspace-secure"><ShieldCheck size={15}/> Secure account</span>
        </header>

        <div className="workspace-content">
          <div className="workspace-welcome">
            <div>
              <span className="forecast-eyebrow">WORKSPACE OVERVIEW</span>
              <h1>Welcome, {firstName}.</h1>
              <p>Your retail planning workspace is ready. Choose a workflow to get started.</p>
            </div>
            <div className="workspace-date"><Clock3 size={15}/>{new Intl.DateTimeFormat(undefined, { dateStyle: "full" }).format(new Date())}<PwaInstallPrompt /></div>
          </div>

          <section className="workspace-start-section">
            <div className="workspace-section-heading"><div><h2>Plan your next move</h2><p>Use your own sales and inventory files to generate business insights.</p></div></div>
            <div className="workspace-action-grid">
              <Link to="/workspace/forecasts" className="workspace-action-card">
                <span className="workspace-action-icon blue"><LineChart size={21}/></span>
                <span className="workspace-card-eyebrow">DEMAND PLANNING</span>
                <strong>Generate a demand forecast</strong>
                <span className="workspace-card-description">Upload historical daily sales and estimate demand for the next 7, 15 or 30 days.</span>
                <span className="workspace-card-link">Open forecasts <ArrowRight size={15}/></span>
              </Link>
              <Link to="/workspace/inventory" className="workspace-action-card">
                <span className="workspace-action-icon mint"><Boxes size={21}/></span>
                <span className="workspace-card-eyebrow">INVENTORY PLANNING</span>
                <strong>Plan replenishment</strong>
                <span className="workspace-card-description">Combine sales history with actual stock and supplier inputs to calculate reorder guidance.</span>
                <span className="workspace-card-link">Open inventory <ArrowRight size={15}/></span>
              </Link>
            </div>
          </section>

          <section className="workspace-next-section">
            <div className="workspace-section-heading"><div><h2>Your workspace, at a glance</h2><p>Manage your sales data and products, then explore the tools already available in your workspace.</p></div></div>
            <div className="workspace-coming-grid">
              <Link to="/workspace/sales" className="workspace-coming-card"><FileUp size={19}/><div><b>Sales imports</b><span>Validate sales files, build your product identifiers and review import history</span></div><span className="workspace-coming-tag">Available now</span></Link>
              <Link to="/workspace/suppliers" className="workspace-coming-card"><Building2 size={19}/><div><b>Supplier directory</b><span>Maintain supplier contacts and default lead-time references</span></div><span className="workspace-coming-tag">Available now</span></Link>
              <article className="workspace-coming-card"><Store size={19}/><div><b>Store management</b><span>Manage store and location information</span></div><span className="workspace-coming-tag">Future enhancement</span></article>
              <Link to="/workspace/analyses" className="workspace-coming-card"><FileUp size={19}/><div><b>Saved analyses</b><span>Review, export or delete previous forecasts and inventory plans</span></div><span className="workspace-coming-tag">Available now</span></Link>
            </div>
          </section>

          <div className="workspace-data-note"><ShieldCheck size={17}/><span><b>Your analysis results are saved to your private workspace.</b> Forecast outputs and inventory recommendations are stored in Supabase and available when you sign in again. Original uploaded CSV files are not stored.</span></div>
        </div>
      </section>
    </main>
  );
}
