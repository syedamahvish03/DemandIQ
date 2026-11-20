import { useEffect, useState } from "react";
import { checkApiHealth } from "./lib/api";
import ForecastPage from "./pages/ForecastPage";
import InventoryPage from "./pages/InventoryPage";
import AnalysesPage from "./pages/AnalysesPage";
import DashboardPage from "./pages/DashboardPage";
import SalesPage from "./pages/SalesPage";
import ProductsPage from "./pages/ProductsPage";
import SuppliersPage from "./pages/SuppliersPage";
import AuthPage from "./components/AuthPage";
import ProtectedRoute from "./components/ProtectedRoute";
import WorkspaceLayout from "./components/WorkspaceLayout";
import { Link, Route, Routes } from "react-router-dom";
import {
  ArrowDownRight, ArrowRight, BarChart3, Boxes, Check,
  CircleHelp, LineChart, LockKeyhole, Menu, PackageSearch,
  ShieldCheck, Sparkles, Store, TrendingUp, UploadCloud, X, Zap
} from "lucide-react";

function Brand({ compact = false }: { compact?: boolean }) {
  return <Link className="brand" to="/" aria-label="DemandIQ home">
    <span className="brand-mark"><LineChart size={21} strokeWidth={2.4} /></span>
    {!compact && <span>Demand<span className="brand-iq">IQ</span></span>}
  </Link>;
}

function Header() {
  const [open, setOpen] = useState(false);
  return <header className="site-header">
    <div className="container nav-wrap">
      <Brand />
      <button className="mobile-menu" aria-label="Toggle navigation" onClick={() => setOpen(!open)}>
        {open ? <X /> : <Menu />}
      </button>
      <nav className={open ? "nav-links nav-open" : "nav-links"} aria-label="Main navigation">
        <a href="/#platform" onClick={() => setOpen(false)}>Platform</a>
        <a href="/#how-it-works" onClick={() => setOpen(false)}>How it works</a>
        <a href="/#security" onClick={() => setOpen(false)}>Security</a>
        <a href="/#about" onClick={() => setOpen(false)}>About</a>
      </nav>
      <div className="nav-actions">
        <Link className="button button-quiet button-small" to="/login">Sign in</Link>
        <Link className="button button-primary button-small" to="/workspace/forecasts">Try forecasting <ArrowRight size={15} /></Link>
      </div>
    </div>
  </header>;
}

function MiniChart() {
  const bars = [32, 44, 37, 55, 48, 66, 58, 76, 69, 91, 80, 100];
  return <div className="chart-bars" aria-label="Illustrative upward sales trend">
    {bars.map((height, index) => <span key={index} style={{ height: height + "%" }} />)}
  </div>;
}

function DashboardPreview() {
  return <div className="preview-shell">
    <div className="preview-top"><div className="window-dots"><i /><i /><i /></div><span>DEMANDIQ / WORKSPACE OVERVIEW</span><span className="live-pill"><b /> SAMPLE VIEW</span></div>
    <div className="preview-body">
      <aside className="preview-side">
        <div className="preview-side-brand"><span className="tiny-mark"><LineChart size={13}/></span> DemandIQ</div>
        <div className="preview-side-label">WORKSPACE</div>
        <div className="preview-nav active"><BarChart3 size={14}/> Overview</div>
        <div className="preview-nav"><PackageSearch size={14}/> Products</div>
        <div className="preview-nav"><TrendingUp size={14}/> Forecasts</div>
        <div className="preview-nav"><Boxes size={14}/> Inventory</div>
        <div className="preview-side-label second">MANAGE</div>
        <div className="preview-nav"><UploadCloud size={14}/> Data imports</div>
        <div className="preview-nav"><Store size={14}/> Stores</div>
      </aside>
      <div className="preview-main">
        <div className="preview-heading"><div><small>MONDAY, 18 NOVEMBER</small><h3>Good morning, Alex <span>✦</span></h3><p>Here’s the latest view of your retail performance.</p></div><div className="preview-avatar">A</div></div>
        <div className="preview-kpis">
          <div className="kpi-card"><small>NET SALES</small><strong>₹8.42L</strong><em className="positive">↗ 12.8% <span>vs last period</span></em></div>
          <div className="kpi-card"><small>UNITS SOLD</small><strong>2,846</strong><em className="positive">↗ 8.2% <span>vs last period</span></em></div>
          <div className="kpi-card"><small>PRODUCTS TRACKED</small><strong>128</strong><em className="muted-kpi">Across 3 locations</em></div>
        </div>
        <div className="preview-lower">
          <div className="preview-panel sales-panel"><div className="panel-title"><div><b>Sales performance</b><small>Illustrative dashboard preview</small></div><span>Last 30 days⌄</span></div><div className="chart-summary"><strong>₹8,42,560</strong><small className="positive">↗ 12.8%</small></div><MiniChart/><div className="chart-axis"><span>01 NOV</span><span>08 NOV</span><span>15 NOV</span><span>18 NOV</span></div></div>
          <div className="preview-panel insight-panel"><div className="panel-title"><b>Demand signals</b><Sparkles size={15}/></div><div className="signal"><span className="signal-icon violet"><TrendingUp size={15}/></span><div><b>Demand trending up</b><small>12 products · sample insight</small></div></div><div className="signal"><span className="signal-icon amber"><Boxes size={15}/></span><div><b>Review stock levels</b><small>5 products · sample alert</small></div></div><div className="signal"><span className="signal-icon green"><Check size={15}/></span><div><b>Data import ready</b><small>Last sync · sample status</small></div></div></div>
        </div>
        <div className="preview-disclaimer">Illustrative interface preview — all figures and alerts shown here are sample values, not live retailer data.</div>
      </div>
    </div>
  </div>;
}

const features = [
  { icon: <PackageSearch />, number: "01", title: "Know every product", body: "Bring product and sales information together. See what moves, what slows down and how each item performs." },
  { icon: <TrendingUp />, number: "02", title: "Look ahead with forecasts", body: "Explore 7, 15 and 30-day demand estimates, with model context that helps you interpret the numbers." },
  { icon: <Boxes />, number: "03", title: "Plan inventory with context", body: "Use your stock and supplier inputs to understand reorder points and possible replenishment needs." },
  { icon: <BarChart3 />, number: "04", title: "Turn data into decisions", body: "Translate sales patterns into clear product-level insights and reports your team can act on." }
];


function ApiConnectionStatus() {
  const [status, setStatus] = useState<"checking" | "connected" | "offline">("checking");

  useEffect(() => {
    let active = true;
    checkApiHealth()
      .then(() => {
        if (active) setStatus("connected");
      })
      .catch(() => {
        if (active) setStatus("offline");
      });

    return () => {
      active = false;
    };
  }, []);

  const label = status === "connected"
    ? "API connected"
    : status === "offline"
      ? "API unavailable"
      : "Checking API";

  return <span className={`api-status api-status-${status}`} role="status">
    <i aria-hidden="true" />{label}
  </span>;
}

function HomePage() {
  return <>
    <Header />
    <main>
      <section className="hero-section">
        <div className="hero-glow glow-one" /><div className="hero-glow glow-two" />
        <div className="container hero-grid">
          <div className="hero-copy">
            <div className="eyebrow"><span className="eyebrow-dot" /> RETAIL INTELLIGENCE, MADE CLEAR</div>
            <h1>See what’s selling.<br/><span>Know what’s next.</span></h1>
            <p className="hero-lede">DemandIQ brings your sales, product performance and demand forecasts into one clear workspace — so you can plan your next move with confidence.</p>
            <div className="hero-actions"><Link className="button button-primary button-large" to="/signup">Create your workspace <ArrowRight size={17}/></Link><a className="text-link" href="#platform">Explore the platform <ArrowDownRight size={17}/></a></div>
            <div className="hero-trust"><span><ShieldCheck size={15}/> Private business workspace</span><span><Zap size={15}/> Clear, guided workflows</span></div>
          </div>
          <div className="hero-visual"><div className="visual-orbit orbit-a"/><div className="visual-orbit orbit-b"/><DashboardPreview/><div className="floating-note"><span className="float-icon"><TrendingUp size={17}/></span><div><b>Plan ahead, not by guesswork</b><small>Sales signals · Forecasts · Inventory</small></div></div></div>
        </div>
        <div className="container hero-foot"><span>BUILT FOR RETAIL TEAMS THAT WANT CLARITY</span><span>ONE WORKSPACE · YOUR BUSINESS DATA · YOUR DECISIONS</span></div>
      </section>
      <section className="section platform-section" id="platform">
        <div className="container"><div className="section-heading"><div className="eyebrow dark-eyebrow">THE DEMANDIQ WORKSPACE</div><h2>Your retail picture,<br/><span>all in one place.</span></h2><p>Move from scattered spreadsheets to a clearer view of products, sales and the demand signals shaping your business.</p></div>
          <div className="feature-grid">{features.map((item) => <article className="feature-card" key={item.number}><div className="feature-top"><span className="feature-icon">{item.icon}</span><small>{item.number}</small></div><h3>{item.title}</h3><p>{item.body}</p><span className="feature-line"/></article>)}</div>
        </div>
      </section>
      <section className="section workflow-section" id="how-it-works">
        <div className="container workflow-grid"><div className="workflow-copy"><div className="eyebrow dark-eyebrow">A CLEARER WAY TO WORK</div><h2>From your data<br/>to your next move.</h2><p>Getting started should feel straightforward. DemandIQ is designed to guide you through each step without requiring a background in data science.</p><Link className="button button-dark" to="/signup">Get started <ArrowRight size={16}/></Link></div>
          <div className="steps-list"><div className="step-item"><span>01</span><div><b>Bring your data</b><p>Upload a sales file or start with a guided sample workspace.</p></div><UploadCloud/></div><div className="step-item"><span>02</span><div><b>Understand your business</b><p>Review product performance, trends and data-quality feedback.</p></div><BarChart3/></div><div className="step-item"><span>03</span><div><b>Explore what may come next</b><p>Generate demand forecasts and understand the model context.</p></div><TrendingUp/></div><div className="step-item"><span>04</span><div><b>Plan with confidence</b><p>Add verified stock information to explore replenishment recommendations.</p></div><Boxes/></div></div>
        </div>
      </section>
      <section className="security-section" id="security"><div className="container security-card"><div className="security-icon"><LockKeyhole size={25}/></div><div><div className="eyebrow">YOUR BUSINESS, YOUR WORKSPACE</div><h2>Private by design.<br/><span>Built with care.</span></h2><p>DemandIQ is being built around individual business workspaces, with access controls designed to keep each retailer’s information separate. Account security and workspace isolation will be connected before customer data is stored.</p></div><div className="security-points"><span><ShieldCheck/> Workspace-level data boundaries</span><span><LockKeyhole/> Protected account access</span><span><CircleHelp/> Clear data and model explanations</span></div></div></section>
      <section className="cta-section" id="about"><div className="container cta-inner"><div className="eyebrow">MAKE YOUR NEXT DECISION A CLEARER ONE</div><h2>Start with your data.<br/><span>Move with insight.</span></h2><p>Explore a more thoughtful way to understand retail demand.</p><Link className="button button-primary button-large" to="/signup">Get started with DemandIQ <ArrowRight size={17}/></Link><small>Create a secure account to access your workspace. Cloud workspace storage is still under development.</small></div></section>
    </main>
    <footer className="site-footer"><div className="container footer-inner"><Brand/><span>Retail clarity, ahead of demand.</span><div><a href="#platform">Platform</a><a href="#security">Security</a><a href="mailto:hello@demandiq.app">Contact</a></div><ApiConnectionStatus/><small>© 2026 DemandIQ. Product preview.</small></div></footer>
  </>;
}

export default function App() {
  return <Routes>
    <Route path="/" element={<HomePage/>}/>
    <Route path="/login" element={<AuthPage mode="login"/>}/>
    <Route path="/signup" element={<AuthPage mode="signup"/>}/>
    <Route path="/workspace" element={<ProtectedRoute><DashboardPage/></ProtectedRoute>}/>
    <Route path="/workspace/sales" element={<ProtectedRoute><SalesPage/></ProtectedRoute>}/>
    <Route path="/workspace/products" element={<ProtectedRoute><ProductsPage/></ProtectedRoute>}/>
    <Route path="/workspace/suppliers" element={<ProtectedRoute><WorkspaceLayout><SuppliersPage/></WorkspaceLayout></ProtectedRoute>}/>
    <Route path="/workspace/forecasts" element={<ProtectedRoute><WorkspaceLayout><ForecastPage/></WorkspaceLayout></ProtectedRoute>}/>
    <Route path="/workspace/inventory" element={<ProtectedRoute><WorkspaceLayout><InventoryPage/></WorkspaceLayout></ProtectedRoute>}/>
    <Route path="/workspace/analyses" element={<ProtectedRoute><WorkspaceLayout><AnalysesPage/></WorkspaceLayout></ProtectedRoute>}/>
    <Route path="*" element={<HomePage/>}/>
  </Routes>;
}
