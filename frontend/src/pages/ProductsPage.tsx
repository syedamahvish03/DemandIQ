import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { BarChart3, Boxes, Clock3, FileSpreadsheet, FileUp, LoaderCircle, PackageSearch, Plus, Save, ShieldCheck, Trash2, X } from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";
import { supabase } from "../lib/supabase";

type Product = {
  id: string;
  item_code: string;
  product_name: string;
  category: string | null;
  created_at: string;
};

const emptyForm = { item_code: "", product_name: "", category: "" };

export default function ProductsPage() {
  const { session, signOut } = useAuth();
  const [products, setProducts] = useState<Product[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");

  async function loadProducts() {
    setLoading(true);
    const { data, error: queryError } = await supabase
      .from("products")
      .select("id, item_code, product_name, category, created_at")
      .order("item_code", { ascending: true })
      .limit(500);
    if (queryError) setError(queryError.message);
    else setProducts((data ?? []) as Product[]);
    setLoading(false);
  }

  useEffect(() => {
    void loadProducts();
  }, []);

  function beginEdit(product: Product) {
    setEditingId(product.id);
    setForm({ item_code: product.item_code, product_name: product.product_name, category: product.category ?? "" });
    setError("");
    setNotice("");
  }

  function resetForm() {
    setEditingId(null);
    setForm(emptyForm);
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const itemCode = form.item_code.trim();
    const productName = form.product_name.trim();
    if (!itemCode || !productName) {
      setError("Item code and product name are required.");
      return;
    }
    setSaving(true);
    setError("");
    setNotice("");
    const { data: { user }, error: userError } = await supabase.auth.getUser();
    if (userError || !user) {
      setError(userError?.message ?? "Please sign in again.");
      setSaving(false);
      return;
    }
    const { data: workspace, error: workspaceError } = await supabase
      .from("workspaces").select("id").eq("owner_id", user.id).single();
    if (workspaceError) {
      setError(workspaceError.message);
      setSaving(false);
      return;
    }
    const values = {
      workspace_id: workspace.id,
      owner_id: user.id,
      item_code: itemCode,
      product_name: productName,
      category: form.category.trim() || null,
    };
    const query = editingId
      ? supabase.from("products").update(values).eq("id", editingId)
      : supabase.from("products").insert(values);
    const { error: saveError } = await query;
    if (saveError) setError(saveError.message);
    else {
      setNotice(editingId ? "Product details updated." : "Product added to your catalogue.");
      resetForm();
      await loadProducts();
    }
    setSaving(false);
  }

  async function handleDelete(product: Product) {
    if (!window.confirm(`Delete ${product.product_name}? Products referenced by sales history cannot be deleted.`)) return;
    setError("");
    setNotice("");
    const { error: deleteError } = await supabase.from("products").delete().eq("id", product.id);
    if (deleteError) setError(deleteError.message);
    else {
      setNotice("Product removed from the catalogue.");
      await loadProducts();
    }
  }

  const filtered = products.filter((product) =>
    `${product.item_code} ${product.product_name} ${product.category ?? ""}`.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <main className="workspace-shell">
      <aside className="workspace-sidebar">
        <Link className="workspace-brand" to="/"><span className="brand-mark"><BarChart3 size={19}/></span><span>Demand<span className="brand-iq">IQ</span></span></Link>
        <span className="workspace-nav-label">WORKSPACE</span>
        <nav className="workspace-nav" aria-label="Workspace navigation">
          <NavLink to="/workspace" end className={({ isActive }) => isActive ? "workspace-nav-link active" : "workspace-nav-link"}><BarChart3 size={17}/>Overview</NavLink>
          <NavLink to="/workspace/sales" className={({ isActive }) => isActive ? "workspace-nav-link active" : "workspace-nav-link"}><FileUp size={17}/>Sales & imports</NavLink>
          <NavLink to="/workspace/products" className={({ isActive }) => isActive ? "workspace-nav-link active" : "workspace-nav-link"}><PackageSearch size={17}/>Products</NavLink>
          <NavLink to="/workspace/forecasts" className={({ isActive }) => isActive ? "workspace-nav-link active" : "workspace-nav-link"}><FileSpreadsheet size={17}/>Demand forecasts</NavLink>
          <NavLink to="/workspace/inventory" className={({ isActive }) => isActive ? "workspace-nav-link active" : "workspace-nav-link"}><Boxes size={17}/>Inventory planning</NavLink>
          <NavLink to="/workspace/analyses" className={({ isActive }) => isActive ? "workspace-nav-link active" : "workspace-nav-link"}><Clock3 size={17}/>Saved analyses</NavLink>
        </nav>
        <div className="workspace-sidebar-bottom"><div className="workspace-help-icon"><ShieldCheck size={17}/></div><b>Product catalogue</b><p>Maintain the item identifiers and descriptions used across your sales data.</p><button className="workspace-signout" onClick={() => void signOut()}>Sign out</button></div>
      </aside>
      <section className="workspace-main">
        <header className="workspace-topbar"><div><span className="workspace-topbar-label">DEMANDIQ WORKSPACE</span><span className="workspace-account-email">{session?.user.email}</span></div><span className="workspace-secure"><ShieldCheck size={15}/> Secure account</span></header>
        <div className="workspace-content">
          <div className="workspace-welcome"><div><span className="forecast-eyebrow">PRODUCT DATA</span><h1>Product catalogue</h1><p>Manage the item identifiers discovered in your sales imports and add product descriptions.</p></div></div>
          <div className="sales-summary-grid"><div className="sales-summary-card"><span>PRODUCTS IN CATALOGUE</span><strong>{products.length.toLocaleString()}</strong><small>Up to 500 products shown in this view</small></div></div>
          <section className="sales-panel-card">
            <div className="sales-panel-heading"><div><span className="forecast-eyebrow"><Plus size={14}/> CATALOGUE MANAGEMENT</span><h2>{editingId ? "Edit product" : "Add a product"}</h2><p>Item codes must be unique within your workspace.</p></div></div>
            <form className="product-form" onSubmit={(event) => void handleSave(event)}>
              <label>Item code<input value={form.item_code} onChange={(event) => setForm({ ...form, item_code: event.target.value })} disabled={Boolean(editingId)} placeholder="e.g. SKU-100" required/></label>
              <label>Product name<input value={form.product_name} onChange={(event) => setForm({ ...form, product_name: event.target.value })} placeholder="e.g. Classic Cotton T-Shirt" required/></label>
              <label>Category (optional)<input value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} placeholder="e.g. Apparel"/></label>
              <div className="product-form-actions"><button className="button button-primary" type="submit" disabled={saving}>{saving ? <><LoaderCircle className="forecast-spinner" size={15}/> Saving…</> : <><Save size={15}/> {editingId ? "Save changes" : "Add product"}</>}</button>{editingId && <button className="button data-export-button" type="button" onClick={resetForm}><X size={15}/> Cancel</button>}</div>
            </form>
            {error && <div className="forecast-error" role="alert">{error}</div>}
            {notice && <div className="analysis-save-notice" role="status">{notice}</div>}
          </section>
          <section className="sales-panel-card">
            <div className="sales-panel-heading"><div><span className="forecast-eyebrow"><PackageSearch size={14}/> WORKSPACE CATALOGUE</span><h2>Products</h2><p>Products are automatically discovered when sales data is imported.</p></div><input className="product-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search products…"/></div>
            {loading ? <p className="sales-history-empty">Loading products…</p> : filtered.length === 0 ? <div className="sales-history-empty"><PackageSearch size={25}/><b>{products.length ? "No matching products" : "Your catalogue is empty"}</b><span>Import a sales CSV or add your first product above.</span><Link className="button data-export-button" to="/workspace/sales">Open sales imports</Link></div> : <div className="forecast-table-wrap"><table className="forecast-table product-table"><thead><tr><th>Item code</th><th>Product name</th><th>Category</th><th>Actions</th></tr></thead><tbody>{filtered.map((product) => <tr key={product.id}><td>{product.item_code}</td><td>{product.product_name}</td><td>{product.category || "—"}</td><td><div className="product-row-actions"><button type="button" onClick={() => beginEdit(product)}>Edit</button><button type="button" onClick={() => void handleDelete(product)} aria-label={`Delete ${product.product_name}`}><Trash2 size={14}/></button></div></td></tr>)}</tbody></table></div>}
          </section>
          <div className="workspace-data-note"><ShieldCheck size={17}/><span><b>Product records belong to your private workspace.</b> Sales history references product codes so catalogue changes cannot silently break imported records.</span></div>
        </div>
      </section>
    </main>
  );
}
