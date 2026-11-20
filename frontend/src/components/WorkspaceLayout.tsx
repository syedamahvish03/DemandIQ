import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { BarChart3, Building2, Boxes, CircleHelp, Clock3, FileUp, LineChart, PackageSearch, ShieldCheck, TrendingUp } from "lucide-react";
import { useAuth } from "../lib/AuthContext";

const workspaceLinks = [
  { to: "/workspace", label: "Overview", icon: BarChart3, end: true },
  { to: "/workspace/sales", label: "Sales & imports", icon: FileUp },
  { to: "/workspace/products", label: "Product catalogue", icon: PackageSearch },
  { to: "/workspace/suppliers", label: "Suppliers", icon: Building2 },
  { to: "/workspace/forecasts", label: "Demand forecasts", icon: LineChart },
  { to: "/workspace/inventory", label: "Inventory planning", icon: Boxes },
  { to: "/workspace/analyses", label: "Saved analyses", icon: Clock3 },
];

export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  return (
    <main className="workspace-shell">
      <aside className="workspace-sidebar">
        <Link className="workspace-brand" to="/workspace">
          <span className="brand-mark"><TrendingUp size={19}/></span>
          <span>Demand<span className="brand-iq">IQ</span></span>
        </Link>
        <span className="workspace-nav-label">WORKSPACE</span>
        <nav className="workspace-nav" aria-label="Workspace navigation">
          {workspaceLinks.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => isActive ? "workspace-nav-link active" : "workspace-nav-link"}>
              <Icon size={17}/>{label}
            </NavLink>
          ))}
        </nav>
        <div className="workspace-sidebar-bottom">
          <div className="workspace-help-icon"><CircleHelp size={17}/></div>
          <b>Building a clearer retail picture</b>
          <p>Explore your sales, demand forecasts and stock planning in one place.</p>
        </div>
      </aside>
      <section className="workspace-main">
        <header className="workspace-topbar">
          <div><span className="workspace-topbar-label">DEMANDIQ WORKSPACE</span><span className="workspace-account-email">{session?.user.email}</span></div>
          <span className="workspace-secure"><ShieldCheck size={15}/> Secure account</span>
        </header>
        <div className="workspace-content workspace-page-content">{children}</div>
      </section>
    </main>
  );
}
