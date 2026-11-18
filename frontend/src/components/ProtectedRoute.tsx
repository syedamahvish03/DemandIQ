import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { session, loading, signOut } = useAuth();

  if (loading) {
    return <main className="forecast-page"><div className="forecast-container">Restoring your secure session…</div></main>;
  }
  if (!session) return <Navigate to="/login" replace />;

  return <>
    <div className="workspace-account-bar" style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: "14px", padding: "12px 5%", borderBottom: "1px solid #e8eaf0", background: "#fff" }}>
      <span style={{ fontSize: "13px", color: "#526078" }}>{session.user.email}</span>
      <button className="button button-quiet button-small" type="button" onClick={() => { void signOut().catch((error: unknown) => console.error("Sign out failed:", error)); }}>Sign out</button>
    </div>
    {children}
  </>;
}
