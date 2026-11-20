import { useState } from "react";
import type { FormEvent } from "react";
import { ArrowRight, Eye, EyeOff, ShieldCheck, Sparkles } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";

export default function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const [showPassword, setShowPassword] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { signUp, signIn } = useAuth();
  const isSignup = mode === "signup";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setError("");

    if (isSignup && fullName.trim().length < 2) {
      setError("Please enter your full name.");
      return;
    }
    if (password.length < 8) {
      setError("Your password must contain at least 8 characters.");
      return;
    }

    setSubmitting(true);
    try {
      if (isSignup) {
        const result = await signUp(fullName, email.trim(), password);
        if (result.confirmationRequired) {
          setMessage("Your account has been created. Check your email and confirm your address before signing in.");
        } else {
          navigate("/workspace/forecasts", { replace: true });
        }
      } else {
        await signIn(email.trim(), password);
        navigate("/workspace/forecasts", { replace: true });
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Authentication failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return <div className="auth-layout">
    <div className="auth-art"><Link to="/" className="auth-brand"><span className="brand"><span className="brand-mark">↗</span><span>Demand<span className="brand-iq">IQ</span></span></span></Link><div className="auth-art-copy"><div className="eyebrow"><Sparkles size={14}/> RETAIL INTELLIGENCE, MADE CLEAR</div><h1>Your business<br/><span>has a next move.</span></h1><p>Bring your retail data into focus with product insights, demand forecasts and thoughtful inventory planning.</p><div className="auth-art-stat"><div><strong>7 / 15 / 30</strong><small>Day forecast horizons</small></div><div><strong>One place</strong><small>For your retail picture</small></div></div></div><div className="auth-art-bottom">DEMANDIQ · SECURE ACCOUNT ACCESS</div></div>
    <div className="auth-panel"><Link className="back-home" to="/">← Back to website</Link><div className="auth-form-wrap"><div className="auth-mobile-brand"><Link to="/" className="brand">Demand<span className="brand-iq">IQ</span></Link></div><div className="auth-kicker">YOUR DEMANDIQ WORKSPACE</div><h2>{isSignup ? "Create your account" : "Welcome back"}</h2><p className="auth-subtitle">{isSignup ? "Start building a clearer picture of your retail business." : "Sign in to continue to your workspace."}</p>
      {!isSignup && searchParams.get("confirmed") === "1" && <div className="form-notice" role="status">Email confirmed. You can now sign in to DemandIQ.</div>}
      <form onSubmit={handleSubmit}>
        {isSignup && <label>Full name<input type="text" placeholder="Your name" autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} required /></label>}
        <label>Work email<input type="email" placeholder="you@company.com" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
        <label>Password<div className="password-field"><input type={showPassword ? "text" : "password"} placeholder="At least 8 characters" autoComplete={isSignup ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required/><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff size={17}/> : <Eye size={17}/>}</button></div></label>
        {error && <div className="forecast-error" role="alert">{error}</div>}
        {message && <div className="form-notice" role="status">{message}</div>}
        <button className="button button-primary auth-submit" type="submit" disabled={submitting}>{submitting ? "Please wait…" : isSignup ? "Create account" : "Sign in"} <ArrowRight size={16}/></button>
      </form>
      <div className="auth-next"><ShieldCheck size={17}/><span>Your account is secured by Supabase authentication. Workspace data persistence is a separate upcoming step.</span></div>
      <div className="auth-switch">{isSignup ? "Already have an account?" : "New to DemandIQ?"} <Link to={isSignup ? "/login" : "/signup"}>{isSignup ? "Sign in" : "Create an account"}</Link></div>
    </div><div className="auth-legal">By continuing, you agree to use this product responsibly. Terms and privacy information will be published before customer launch.</div></div>
  </div>;
}
