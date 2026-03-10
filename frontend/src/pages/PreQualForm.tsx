import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@/components/DashboardLayout";
import { useAuth, getRoleLabel } from "@/lib/auth";
import { usePreQualCheck } from "@/hooks/useApi";
import { ArrowRight, CheckCircle2, XCircle, AlertTriangle, Loader2 } from "lucide-react";

const NAV = [
  { label: "Dashboard", path: "/borrower" },
  { label: "Pre-Qualification", path: "/borrower/pre-qual" },
  { label: "Documents", path: "/borrower/apply" },
];

const SECTORS = ["Manufacturing", "IT/Software", "NBFC", "Infrastructure", "Trading", "Pharmaceuticals", "Textiles", "Real Estate", "Agriculture", "Services"];
const LOAN_TYPES = [
  { value: "CC", label: "Cash Credit", desc: "Working capital" },
  { value: "TL", label: "Term Loan", desc: "Long-term debt" },
  { value: "WCTL", label: "WCTL", desc: "WC term loan" },
];
const TURNOVER_RANGES = [
  { value: 5_00_00_000, label: "1–10 Cr" },
  { value: 30_00_00_000, label: "10–50 Cr" },
  { value: 75_00_00_000, label: "50–100 Cr" },
  { value: 200_00_00_000, label: "100 Cr+" },
];

export default function PreQualForm() {
  const { userName, role } = useAuth();
  const navigate = useNavigate();
  const preQualMutation = usePreQualCheck();

  const [form, setForm] = useState({
    company_name: "",
    cin_number: "",
    sector: "Manufacturing",
    loan_type: "CC",
    annual_turnover: 30_00_00_000,
    loan_amount_requested: 5_00_00_000,
    years_in_business: 8,
    existing_debt: 0,
    is_npa: false,
    incorporation_year: 2016,
    is_group_company: false,
    contact_email: "",
    contact_phone: "",
  });

  const [result, setResult] = useState<any>(null);
  const updateField = (key: string, value: any) => setForm((prev) => ({ ...prev, [key]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await preQualMutation.mutateAsync(form);
      setResult(res.data);
    } catch (err: any) {
      setResult({ error: err?.message || "Pre-qualification check failed" });
    }
  };

  /* ── Result screen ── */
  if (result && !result.error) {
    const tier = result.eligibility_tier || "UNKNOWN";
    const score = result.score || 0;
    const isEligible = tier === "ELIGIBLE";
    const isBorderline = tier === "BORDERLINE";

    return (
      <DashboardLayout role="borrower" roleLabel={getRoleLabel(role)} navItems={NAV} userName={userName}>
        <div className="max-w-md mx-auto py-16">
          <div
            className={`w-16 h-16 rounded-[3px] flex items-center justify-center mx-auto mb-6 ${
              isEligible ? "bg-foreground" : isBorderline ? "border-2 border-foreground" : "border-2 border-foreground/30"
            }`}
          >
            {isEligible ? (
              <CheckCircle2 className="w-8 h-8 text-background" />
            ) : isBorderline ? (
              <AlertTriangle className="w-8 h-8" />
            ) : (
              <XCircle className="w-8 h-8 text-muted-foreground" />
            )}
          </div>

          <div className="text-center mb-8">
            <h2 className="font-display text-2xl mb-1" style={{ letterSpacing: "-0.04em" }}>
              {isEligible ? "Eligible for Credit" : isBorderline ? "Borderline Eligibility" : "Not Eligible"}
            </h2>
            <p className="text-muted-foreground text-sm" style={{ letterSpacing: "-0.01em" }}>
              Pre-qualification score:{" "}
              <span className="font-mono font-bold text-foreground">{(score * 100).toFixed(0)}%</span>
            </p>
          </div>

          {result.reasons && result.reasons.length > 0 && (
            <div className="glass-card mb-6">
              <p className="section-label mb-3">Key Factors</p>
              <ul className="space-y-2">
                {result.reasons.map((r: string, i: number) => (
                  <li key={i} className="text-sm text-muted-foreground flex items-start gap-2" style={{ letterSpacing: "-0.01em" }}>
                    <span className="font-mono text-[10px] text-muted-foreground mt-0.5">→</span> {r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(isEligible || isBorderline) && result.application_id ? (
            <button onClick={() => navigate("/borrower/apply")} className="btn-primary w-full gap-2">
              Continue to Document Upload <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <button className="btn-ghost w-full" onClick={() => setResult(null)}>
              Try Again
            </button>
          )}
        </div>
      </DashboardLayout>
    );
  }

  /* ── Form ── */
  return (
    <DashboardLayout role="borrower" roleLabel={getRoleLabel(role)} navItems={NAV} userName={userName}>
      <div className="max-w-2xl mx-auto">
        <div className="border-b border-border pb-6 mb-8">
          <p className="section-label">Borrower · Step 1 of 2</p>
          <h1 className="font-display" style={{ fontSize: "2rem", letterSpacing: "-0.05em" }}>
            Pre-Qualification Check
          </h1>
          <p className="text-muted-foreground text-sm mt-1" style={{ letterSpacing: "-0.01em" }}>
            Instant eligibility assessment powered by ML (Logistic Regression · AUC 0.84)
          </p>
          <div className="flex items-center gap-2 mt-4">
            <div className="h-0.5 flex-1 bg-foreground rounded-full" />
            <div className="h-0.5 flex-1 bg-border rounded-full" />
          </div>
        </div>

        {result?.error && (
          <div className="glass-card border-l-2 border-foreground mb-6">
            <p className="text-sm" style={{ letterSpacing: "-0.01em" }}>
              {result.error}. Start backend with{" "}
              <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded-[2px]">python main.py</code>
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="glass-card space-y-5">
            <div>
              <label className="section-label mb-1.5">Company Name</label>
              <input
                type="text"
                placeholder="Registered company name"
                value={form.company_name}
                onChange={(e) => updateField("company_name", e.target.value)}
                className="ic-input"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="section-label mb-1.5">Sector</label>
                <select
                  value={form.sector}
                  onChange={(e) => updateField("sector", e.target.value)}
                  className="ic-input cursor-pointer"
                >
                  {SECTORS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="section-label mb-1.5">CIN Number</label>
                <input
                  type="text"
                  placeholder="L12345MH2020PLC"
                  value={form.cin_number}
                  onChange={(e) => updateField("cin_number", e.target.value)}
                  className="ic-input"
                />
              </div>
            </div>

            <div>
              <label className="section-label mb-2">Annual Turnover (Last FY)</label>
              <div className="grid grid-cols-4 gap-2">
                {TURNOVER_RANGES.map((r) => (
                  <button
                    key={r.label}
                    type="button"
                    onClick={() => updateField("annual_turnover", r.value)}
                    className={`py-2.5 rounded-[3px] text-sm font-medium transition-colors border ${
                      form.annual_turnover === r.value
                        ? "bg-foreground text-background border-foreground"
                        : "border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="section-label mb-1.5">Loan Amount Required (₹)</label>
              <input
                type="number"
                value={form.loan_amount_requested}
                onChange={(e) => updateField("loan_amount_requested", Number(e.target.value))}
                className="ic-input font-mono"
              />
            </div>

            <div>
              <label className="section-label mb-2">Years in Business</label>
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={() => updateField("years_in_business", Math.max(0, form.years_in_business - 1))}
                  className="w-10 h-10 rounded-[3px] border border-border flex items-center justify-center text-foreground hover:border-foreground/40 transition-colors font-mono"
                >
                  −
                </button>
                <span className="font-display text-3xl w-12 text-center" style={{ letterSpacing: "-0.05em" }}>
                  {form.years_in_business}
                </span>
                <button
                  type="button"
                  onClick={() => updateField("years_in_business", form.years_in_business + 1)}
                  className="w-10 h-10 rounded-[3px] border border-border flex items-center justify-center text-foreground hover:border-foreground/40 transition-colors font-mono"
                >
                  +
                </button>
              </div>
            </div>

            <div>
              <label className="section-label mb-2">Loan Type</label>
              <div className="grid grid-cols-3 gap-3">
                {LOAN_TYPES.map((lt) => (
                  <button
                    key={lt.value}
                    type="button"
                    onClick={() => updateField("loan_type", lt.value)}
                    className={`p-3 rounded-[3px] border text-left transition-colors ${
                      form.loan_type === lt.value
                        ? "bg-foreground text-background border-foreground"
                        : "border-border hover:border-foreground/30"
                    }`}
                  >
                    <p className="font-mono text-xs font-bold tracking-wider">{lt.value}</p>
                    <p className={`text-xs mt-0.5 ${form.loan_type === lt.value ? "text-background/60" : "text-muted-foreground"}`}>
                      {lt.desc}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center justify-between p-4 rounded-[3px] border border-border">
              <div>
                <p className="text-sm font-medium" style={{ letterSpacing: "-0.01em" }}>History of NPA?</p>
                <p className="text-xs text-muted-foreground">Defaulted on a loan in last 5 years?</p>
              </div>
              <div className="flex rounded-[3px] overflow-hidden border border-border">
                <button
                  type="button"
                  onClick={() => updateField("is_npa", true)}
                  className={`px-4 py-2 text-xs font-mono font-medium tracking-wider transition-colors ${
                    form.is_npa ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted"
                  }`}
                >
                  YES
                </button>
                <button
                  type="button"
                  onClick={() => updateField("is_npa", false)}
                  className={`px-4 py-2 text-xs font-mono font-medium tracking-wider border-l border-border transition-colors ${
                    !form.is_npa ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted"
                  }`}
                >
                  NO
                </button>
              </div>
            </div>
          </div>

          <button
            type="submit"
            className="btn-primary w-full h-12 text-sm gap-2"
            disabled={preQualMutation.isPending}
          >
            {preQualMutation.isPending ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Checking Eligibility...</>
            ) : (
              <>Check Eligibility <ArrowRight className="w-4 h-4" /></>
            )}
          </button>

          <p className="text-center font-mono text-[10px] text-muted-foreground tracking-[0.12em]">
            SECURE 256-BIT ENCRYPTED SUBMISSION
          </p>
        </form>
      </div>
    </DashboardLayout>
  );
}
