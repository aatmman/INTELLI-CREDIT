import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff, ArrowRight, Activity, ShieldCheck, BrainCircuit, FileSearch } from "lucide-react";
import { useAuth, ROLE_ROUTES } from "@/lib/auth";

const FEATURES = [
  { icon: <FileSearch className="w-4 h-4" />, label: "Docling + PyMuPDF extraction" },
  { icon: <BrainCircuit className="w-4 h-4" />, label: "8 LangGraph agentic workflows" },
  { icon: <ShieldCheck className="w-4 h-4" />, label: "SHAP explainability on every score" },
  { icon: <Activity className="w-4 h-4" />, label: "XGBoost AUC 0.91 credit risk model" },
];

const TICKER_ITEMS = [
  "ACME CORP — ₹14 CR — GRADE C — UNDER REVIEW",
  "DELTA LOGISTICS — ₹25 CR — GRADE B — APPROVED",
  "GLOBAL TECH — ₹8.5 CR — PRE-QUAL — STAGE 1",
  "STARLIGHT VENTURES — ₹6 CR — BORDERLINE — RM REVIEW",
  "PRECISION TOOLS — ₹19 CR — GRADE A — SANCTIONED",
];

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("borrower");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    await new Promise((r) => setTimeout(r, 500));
    login(role, email);
    navigate(ROLE_ROUTES[role] || "/borrower");
    setLoading(false);
  };

  const doubled = [...TICKER_ITEMS, ...TICKER_ITEMS];

  return (
    <div className="flex flex-col min-h-screen bg-background overflow-hidden">
      {/* Ticker bar */}
      <div className="ticker-wrap">
        <div className="ticker-inner">
          {doubled.map((item, i) => (
            <span key={i}>
              <span className="ticker-item">{item}</span>
              <span className="ticker-sep">·</span>
            </span>
          ))}
        </div>
      </div>

      {/* Main grid */}
      <div className="flex flex-1">
        {/* ── Left editorial panel ── */}
        <div className="hidden lg:flex lg:w-[52%] flex-col justify-between p-14 bg-foreground text-background relative overflow-hidden">
          {/* Subtle grid texture */}
          <div
            className="absolute inset-0 opacity-[0.035]"
            style={{
              backgroundImage: `linear-gradient(hsl(0 0% 100% / 1) 1px, transparent 1px), linear-gradient(90deg, hsl(0 0% 100% / 1) 1px, transparent 1px)`,
              backgroundSize: "40px 40px",
            }}
          />

          {/* Large background letter */}
          <div
            className="absolute bottom-[-60px] right-[-30px] select-none pointer-events-none"
            style={{
              fontFamily: "'Syne', sans-serif",
              fontSize: "340px",
              fontWeight: 800,
              lineHeight: 1,
              color: "hsl(0 0% 100% / 0.04)",
              letterSpacing: "-0.06em",
            }}
          >
            IC
          </div>

          <div className="relative z-10">
            {/* Wordmark */}
            <div className="flex items-center gap-3 mb-16">
              <div
                className="w-8 h-8 rounded-[3px] border border-background/20 flex items-center justify-center"
                style={{ background: "hsl(0 0% 100% / 0.1)" }}
              >
                <span className="text-background font-mono text-xs font-bold tracking-wider">IC</span>
              </div>
              <span className="text-background/90 font-display text-sm tracking-[-0.02em] font-bold uppercase">
                Intelli-Credit
              </span>
            </div>

            {/* Headline */}
            <div className="mb-12">
              <p className="text-mono text-background/40 mb-4 tracking-widest text-[10px] uppercase">
                v3.0 — IIT Hyderabad Hackathon
              </p>
              <h1
                className="text-background leading-none mb-5"
                style={{
                  fontFamily: "'Syne', sans-serif",
                  fontSize: "clamp(3rem, 5vw, 4.5rem)",
                  fontWeight: 800,
                  letterSpacing: "-0.04em",
                }}
              >
                Corporate
                <br />
                Credit
                <br />
                <span style={{ color: "hsl(0 0% 100% / 0.4)" }}>Intelligence</span>
              </h1>
              <p className="text-background/50 text-sm leading-relaxed max-w-sm" style={{ letterSpacing: "-0.01em" }}>
                End-to-end AI-powered credit decisioning engine for Indian banks.
                4 ML models. 8 agentic workflows. 5 role-based portals.
              </p>
            </div>

            {/* Feature list */}
            <div className="space-y-3">
              {FEATURES.map((f) => (
                <div key={f.label} className="flex items-center gap-3">
                  <div
                    className="w-7 h-7 rounded-[3px] flex items-center justify-center text-background/60 flex-shrink-0"
                    style={{ background: "hsl(0 0% 100% / 0.07)", border: "1px solid hsl(0 0% 100% / 0.1)" }}
                  >
                    {f.icon}
                  </div>
                  <span className="text-sm text-background/60" style={{ letterSpacing: "-0.01em" }}>{f.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Bottom stat row */}
          <div className="relative z-10 flex items-center gap-8 border-t border-background/10 pt-6">
            {[
              { v: "84.7%", l: "XGBoost Accuracy" },
              { v: "0.91", l: "AUC-ROC Score" },
              { v: "<200ms", l: "Inference Speed" },
            ].map((s) => (
              <div key={s.l}>
                <p className="text-background font-mono text-lg font-bold" style={{ letterSpacing: "-0.03em" }}>{s.v}</p>
                <p className="text-background/30 text-[10px] font-mono tracking-wider uppercase mt-0.5">{s.l}</p>
              </div>
            ))}
          </div>
        </div>

        {/* ── Right login form ── */}
        <div className="w-full lg:w-[48%] flex items-center justify-center p-8 sm:p-14">
          <div className="w-full max-w-[380px]">
            {/* Mobile logo */}
            <div className="lg:hidden flex items-center gap-2 mb-12">
              <div className="w-7 h-7 rounded-[3px] bg-foreground flex items-center justify-center">
                <span className="text-background font-mono text-[10px] font-bold">IC</span>
              </div>
              <span className="font-display text-sm font-bold uppercase tracking-[-0.01em]">Intelli-Credit</span>
            </div>

            <div className="mb-10">
              <p className="section-label mb-2">Secure Access Portal</p>
              <h2
                className="text-foreground"
                style={{ fontFamily: "'Syne', sans-serif", fontSize: "1.875rem", fontWeight: 800, letterSpacing: "-0.04em" }}
              >
                Welcome back.
              </h2>
              <p className="text-muted-foreground text-sm mt-1" style={{ letterSpacing: "-0.01em" }}>
                Sign in to continue to your dashboard.
              </p>
            </div>

            <form onSubmit={handleLogin} className="space-y-5">
              <div>
                <label className="section-label mb-1.5">Email Address</label>
                <input
                  type="email"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="ic-input"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="section-label mb-0">Password</label>
                  <a href="#" className="text-[11px] text-muted-foreground hover:text-foreground transition-colors font-mono tracking-wider">FORGOT?</a>
                </div>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="ic-input pr-11"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="section-label mb-1.5">
                  Portal Access{" "}
                  <span className="text-foreground/30">— Demo Mode</span>
                </label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="ic-input cursor-pointer"
                  style={{ appearance: "none" }}
                >
                  <option value="borrower">Borrower Portal</option>
                  <option value="rm">Relationship Manager</option>
                  <option value="analyst">Credit Analyst</option>
                  <option value="credit-manager">Credit Manager</option>
                  <option value="sanctioning">Sanctioning Authority</option>
                </select>
              </div>

              <div className="pt-1">
                <button
                  type="submit"
                  className="btn-primary w-full h-12 text-sm"
                  disabled={loading}
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <span className="w-3 h-3 border border-background/40 border-t-background rounded-full animate-spin" />
                      Authenticating...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      Sign In
                      <ArrowRight className="w-4 h-4" />
                    </span>
                  )}
                </button>
              </div>
            </form>

            <div className="mt-10 flex items-center gap-3">
              <div className="flex-1 h-px bg-border" />
              <span className="text-mono text-muted-foreground">AES-256 ENCRYPTED</span>
              <div className="flex-1 h-px bg-border" />
            </div>

            <p className="text-center text-[10px] text-muted-foreground font-mono tracking-wider mt-4">
              © 2026 INTELLI-CREDIT · IIT HYDERABAD
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
