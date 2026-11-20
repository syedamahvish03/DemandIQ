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
          <section className="workspace-hero-panel">
            <div className="workspace-hero-orb workspace-hero-orb-one" />
            <div className="workspace-hero-orb workspace-hero-orb-two" />
            <div className="workspace-hero-copy">
              <span className="workspace-hero-kicker"><span /> YOUR RETAIL INTELLIGENCE WORKSPACE</span>
              <h1>Good to see you, {firstName}.</h1>
              <p>Your sales, demand forecasts and inventory decisions come together here. Choose a workflow and turn your data into your next move.</p>
              <div className="workspace-hero-chips"><span><LineChart size={13}/> Demand intelligence</span><span><Boxes size={13}/> Inventory planning</span><span><ShieldCheck size={13}/> Private workspace</span></div>
            </div>
            <div className="workspace-hero-meta">
              <div className="workspace-hero-date"><Clock3 size={15}/><span>{new Intl.DateTimeFormat(undefined, { dateStyle: "full" }).format(new Date())}</span></div>
              <PwaInstallPrompt />
              <div className="workspace-hero-orbit-icon"><TrendingUp size={29}/></div>
              <span className="workspace-hero-meta-caption">PLAN AHEAD WITH CLARITY</span>
            </div>
          </section>

          <section className="workspace-start-section">
            <div className="workspace-section-heading"><div><span className="workspace-section-kicker">START HERE</span><h2>Choose your next move</h2><p>Start with a demand forecast or go straight to inventory replenishment.</p></div><span className="workspace-section-aside">TWO CORE WORKFLOWS <ArrowRight size={13}/></span></div>
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
            <div className="workspace-section-heading"><div><span className="workspace-section-kicker">WORKSPACE TOOLS</span><h2>Everything in its place</h2><p>Manage the information that powers your forecasts and replenishment plans.</p></div></div>
            <div className="workspace-coming-grid">
              <Link to="/workspace/sales" className="workspace-coming-card"><FileUp size={19}/><div><b>Sales imports</b><span>Validate sales files, build your product identifiers and review import history</span></div><span className="workspace-coming-tag">Available now</span></Link>
              <Link to="/workspace/suppliers" className="workspace-coming-card"><Building2 size={19}/><div><b>Supplier directory</b><span>Maintain supplier contacts and default lead-time references</span></div><span className="workspace-coming-tag">Available now</span></Link>
              <article className="workspace-coming-card"><Store size={19}/><div><b>Store management</b><span>Manage store and location information</span></div><span className="workspace-coming-tag">Future enhancement</span></article>
              <Link to="/workspace/analyses" className="workspace-coming-card"><FileUp size={19}/><div><b>Saved analyses</b><span>Review, export or delete previous forecasts and inventory plans</span></div><span className="workspace-coming-tag">Available now</span></Link>
            </div>
          </section>

          <div className="workspace-data-note"><ShieldCheck size={17}/><span><b>Your analysis results are saved to your private workspace.</b> Forecast outputs and inventory recommendations are stored in Supabase and available when you sign in again. Original sales CSV files are retained in private workspace storage with user-scoped access controls.</span></div>
        </div>
      </section>
    </main>
  );
}
