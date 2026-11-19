import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ArrowLeft, Building2, LoaderCircle, Plus, RefreshCw, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { useAuth } from "../lib/AuthContext";

type Supplier = {
  id: string;
  supplier_name: string;
  contact_person: string | null;
  email: string | null;
  phone: string | null;
  default_lead_time_days: number | null;
  notes: string | null;
};

const emptyForm = { supplier_name: "", contact_person: "", email: "", phone: "", default_lead_time_days: "", notes: "" };

export default function SuppliersPage() {
  const { session } = useAuth();
  const [rows, setRows] = useState<Supplier[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    if (!session?.user.id) return;
    setLoading(true);
    setError("");
    const { data, error: requestError } = await supabase
      .from("suppliers")
      .select("id,supplier_name,contact_person,email,phone,default_lead_time_days,notes")
      .eq("owner_id", session.user.id)
      .order("supplier_name");
    if (requestError) setError(requestError.message);
    else setRows((data ?? []) as Supplier[]);
    setLoading(false);
  }, [session?.user.id]);

  useEffect(() => { void load(); }, [load]);

  function beginEdit(row: Supplier) {
    setEditingId(row.id);
    setForm({
      supplier_name: row.supplier_name,
      contact_person: row.contact_person ?? "",
      email: row.email ?? "",
      phone: row.phone ?? "",
      default_lead_time_days: row.default_lead_time_days?.toString() ?? "",
      notes: row.notes ?? "",
    });
    setMessage("");
  }

  function resetForm() {
    setEditingId("");
    setForm(emptyForm);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session?.user.id || !form.supplier_name.trim()) return;
    const leadTime = form.default_lead_time_days.trim() ? Number(form.default_lead_time_days) : null;
    if (leadTime !== null && (!Number.isInteger(leadTime) || leadTime <= 0)) {
      setError("Default lead time must be a positive whole number of days.");
      return;
    }
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const { data: workspace, error: workspaceError } = await supabase
        .from("workspaces").select("id").eq("owner_id", session.user.id).single();
      if (workspaceError) throw workspaceError;
      const payload = {
        workspace_id: workspace.id,
        owner_id: session.user.id,
        supplier_name: form.supplier_name.trim(),
        contact_person: form.contact_person.trim() || null,
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        default_lead_time_days: leadTime,
        notes: form.notes.trim() || null,
        updated_at: new Date().toISOString(),
      };
      const request = editingId
        ? await supabase.from("suppliers").update(payload).eq("id", editingId).eq("owner_id", session.user.id)
        : await supabase.from("suppliers").insert(payload);
      if (request.error) throw request.error;
      resetForm();
      setMessage(editingId ? "Supplier updated." : "Supplier added to your private workspace.");
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Supplier could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!session?.user.id || !window.confirm("Delete this supplier record?")) return;
    setError("");
    const { error: deleteError } = await supabase.from("suppliers").delete().eq("id", id).eq("owner_id", session.user.id);
    if (deleteError) setError(deleteError.message);
    else setRows(current => current.filter(row => row.id !== id));
  }

  return (
    <main className="forecast-page">
      <div className="forecast-container">
        <div className="forecast-page-links">
          <Link to="/workspace" className="forecast-back"><ArrowLeft size={16}/> Back to DemandIQ</Link>
          <button type="button" className="button data-export-button" onClick={() => void load()} disabled={loading}><RefreshCw size={14}/> Refresh suppliers</button>
        </div>
        <div className="forecast-heading">
          <span className="forecast-eyebrow"><Building2 size={15}/> SUPPLIER WORKSPACE</span>
          <h1>Supplier directory</h1>
          <p>Keep supplier contacts and default lead-time references in your private workspace. Confirm actual lead times when preparing each inventory plan.</p>
        </div>
        {error && <div className="forecast-error" role="alert">{error}</div>}
        {message && <div className="analysis-save-notice" role="status">{message}</div>}
        <section className="forecast-card supplier-form-card">
          <h2>{editingId ? "Update supplier" : "Add a supplier"}</h2>
          <form className="supplier-form" onSubmit={handleSubmit}>
            <label>Supplier name<input required maxLength={120} value={form.supplier_name} onChange={e => setForm({...form,supplier_name:e.target.value})} placeholder="e.g. Northside Wholesale"/></label>
            <label>Contact person<input maxLength={120} value={form.contact_person} onChange={e => setForm({...form,contact_person:e.target.value})} placeholder="Contact name"/></label>
            <label>Email<input type="email" maxLength={254} value={form.email} onChange={e => setForm({...form,email:e.target.value})} placeholder="supplier@example.com"/></label>
            <label>Phone<input type="tel" maxLength={40} value={form.phone} onChange={e => setForm({...form,phone:e.target.value})} placeholder="Phone number"/></label>
            <label>Default lead time (days)<input type="number" min="1" step="1" value={form.default_lead_time_days} onChange={e => setForm({...form,default_lead_time_days:e.target.value})} placeholder="Optional"/></label>
            <label className="supplier-notes-field">Notes<textarea maxLength={1000} value={form.notes} onChange={e => setForm({...form,notes:e.target.value})} placeholder="Products supplied, delivery schedule or other notes"/></label>
            <div className="product-form-actions">
              <button className="button button-primary button-small" type="submit" disabled={saving}>{saving ? <LoaderCircle className="forecast-spinner" size={15}/> : <Plus size={15}/>} {editingId ? "Save changes" : "Add supplier"}</button>
              {editingId && <button className="button data-export-button" type="button" onClick={resetForm}>Cancel</button>}
            </div>
          </form>
        </section>
        <section className="sales-panel-card">
          <div className="sales-panel-heading"><div><h2>Your suppliers</h2><p>{rows.length} supplier {rows.length === 1 ? "record" : "records"} in this workspace</p></div></div>
          {loading ? <div className="analyses-empty"><LoaderCircle className="forecast-spinner"/> Loading suppliers…</div> : rows.length === 0 ? <div className="analyses-empty"><Building2 size={26}/><b>No suppliers added yet</b><p>Add supplier contacts and default lead times to keep replenishment references together.</p></div> :
            <div className="forecast-table-wrap"><table className="forecast-table supplier-table"><thead><tr><th>Supplier</th><th>Contact</th><th>Email / phone</th><th>Default lead time</th><th>Actions</th></tr></thead><tbody>
              {rows.map(row => <tr key={row.id}><td><b>{row.supplier_name}</b>{row.notes && <small className="supplier-notes">{row.notes}</small>}</td><td>{row.contact_person || "—"}</td><td>{row.email || "—"}<small className="supplier-notes">{row.phone || ""}</small></td><td>{row.default_lead_time_days ? row.default_lead_time_days + " days" : "Not set"}</td><td><div className="product-row-actions"><button type="button" onClick={() => beginEdit(row)}>Edit</button><button type="button" onClick={() => void handleDelete(row.id)}><Trash2 size={13}/> Delete</button></div></td></tr>)}
            </tbody></table></div>}
        </section>
        <p className="forecast-disclaimer">Supplier records are reference information only. They do not automatically create purchase orders or override lead times entered in an inventory plan.</p>
      </div>
    </main>
  );
}
