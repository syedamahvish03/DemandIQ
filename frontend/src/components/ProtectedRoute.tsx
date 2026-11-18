import { Navigate } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth();
  if (loading) return <main className="forecast-page"><div className="forecast-container">Restoring your secure session…</div></main>;
  if (!session) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
