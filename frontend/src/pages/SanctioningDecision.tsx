import { DashboardLayout } from "@/components/DashboardLayout";
import { useAuth, getRoleLabel } from "@/lib/auth";
import { useParams } from "react-router-dom";
import { useState } from "react";
import { TrendingUp, AlertTriangle, Building2, Loader2, CheckCircle2, XCircle, RotateCcw } from "lucide-react";
import { useDecisionPack, useSubmitDecision } from "@/hooks/useApi";

const NAV = [
  { label: "Decision Pack", path: "#" },
  { label: "History", path: "#" },
];

const METRICS = [
  { label: "Revenue FY24", value: "₹45.2 Cr" },
  { label: "EBITDA", value: "₹5.4 Cr" },
  { label: "DSCR", value: "2.45×" },
  { label: "D/E Ratio", value: "0.82" },
  { label: "Collateral", value: "₹18.5 Cr" },
];

const STRENGTHS = [
  { n: "01", title: "Strong Cash Reserves", desc: "Maintains 3× more liquidity than industry average benchmarks." },
  { n: "02", title: "Diversified Client Portfolio", desc: "No single client accounts for more than 12% of total annual revenue." },
  { n: "03", title: "Operational Efficiency", desc: "Reduced overhead by 14% over 24 months via automation." },
];

const RISKS = [
  { n: "01", title: "Promoter Investigation", desc: "Named in GST evasion investigation (Nov 2023, Economic Times)." },
  { n: "02", title: "Circular Trading Risk", desc: "Score 65/100 — Bank-GST mismatch 2.99× detected." },
  { n: "03", title: "Active MCA Charge", desc: "₹8.2 Cr charge registered with HDFC Bank — active." },
];

export default function SanctioningDecision() {
  const { userName, role } = useAuth();
  const { appId } = useParams<{ appId: string }>();
  const [isDeciding, setIsDeciding] = useState(false);
  const [decision, setDecision] = useState<string | null>(null);

  // API hooks with demo fallback
  const { data: packData } = useDecisionPack(appId || "");
  const submitDecision = useSubmitDecision();

  const apiMetrics = packData?.data ? [
    { label: "Revenue FY24", value: `₹${packData.data.loan_amount_requested ? (packData.data.loan_amount_requested / 1e7).toFixed(1) + " Cr" : "0 Cr"}` },
    { label: "Risk Grade", value: packData.data.risk_grade || "N/A" },
    { label: "PD Score", value: packData.data.probability_of_default ? `${(packData.data.probability_of_default * 100).toFixed(1)}%` : "N/A" },
  ] : null;

  const handleDecision = async (action: "approve" | "reject" | "return") => {
    setIsDeciding(true);
    const actionMap: Record<string, string> = { approve: "approve", reject: "reject", return: "return_for_review" };
    try {
      await submitDecision.mutateAsync({
        appId: appId || "",
        data: {
          action: actionMap[action],
          decided_by_role: "sanctioning_authority",
          remarks: `SA ${action} decision`,
        },
      });
    } catch {
      await new Promise((r) => setTimeout(r, 1500));
    }
    setDecision(action);
    setIsDeciding(false);
  };

  return (
    <DashboardLayout role="sanctioning" roleLabel={getRoleLabel(role)} navItems={NAV} userName={userName}>
      <div className="max-w-6xl mx-auto space-y-6">

        {/* ── Header ── */}
        <div className="border-b border-border pb-6">
          <div className="flex items-end justify-between">
            <div>
              <p className="section-label">Sanctioning Authority · Final Stage</p>
              <h1 className="font-display" style={{ fontSize: "2rem", letterSpacing: "-0.05em" }}>
                Decision Pack
              </h1>
              <p className="font-mono text-[10px] text-muted-foreground tracking-wider mt-1">
                APP #{appId?.toUpperCase()} · FINAL AUTHORITY
              </p>
            </div>
            <span className="badge-warning">PENDING DECISION</span>
          </div>
        </div>

        {/* ── Decision result ── */}
        {decision && (
          <div
            className={`glass-card text-center py-10 border-2 ${decision === "approve"
                ? "border-foreground"
                : decision === "reject"
                  ? "border-foreground/30"
                  : "border-border"
              }`}
          >
            <div
              className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 ${decision === "approve"
                  ? "bg-foreground text-background"
                  : "bg-muted text-foreground"
                }`}
            >
              {decision === "approve" ? (
                <CheckCircle2 className="w-7 h-7" />
              ) : decision === "reject" ? (
                <XCircle className="w-7 h-7" />
              ) : (
                <RotateCcw className="w-7 h-7" />
              )}
            </div>
            <h2 className="font-display text-2xl mb-1" style={{ letterSpacing: "-0.04em" }}>
              {decision === "approve"
                ? "Sanction Approved"
                : decision === "reject"
                  ? "Sanction Rejected"
                  : "Returned for Review"}
            </h2>
            <p className="text-sm text-muted-foreground" style={{ letterSpacing: "-0.01em" }}>
              {decision === "approve"
                ? "Sanction letter is being generated. Borrower will be notified."
                : decision === "reject"
                  ? "Final rejection recorded. Feedback sent to credit manager."
                  : "Application returned to credit manager for further analysis."}
            </p>
          </div>
        )}

        {/* ── Key Metrics strip ── */}
        <div className="grid grid-cols-5 gap-3">
          {(apiMetrics || METRICS).map((m) => (
            <div key={m.label} className="glass-card">
              <p className="stat-label">{m.label}</p>
              <p
                className="font-display mt-1.5"
                style={{ fontSize: "1.375rem", letterSpacing: "-0.04em" }}
              >
                {m.value}
              </p>
            </div>
          ))}
        </div>

        {/* ── Two-panel layout ── */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">

          {/* Company profile */}
          <div className="lg:col-span-2 glass-card">
            <div className="flex items-start justify-between mb-5">
              <div className="w-12 h-12 rounded-[3px] bg-foreground/8 border border-border flex items-center justify-center">
                <Building2 className="w-6 h-6 text-muted-foreground" />
              </div>
              <span className="badge-dark">GRADE C</span>
            </div>
            <h2 className="font-display text-xl mb-0.5" style={{ letterSpacing: "-0.04em" }}>
              Acme Corp Industries
            </h2>
            <p className="text-sm text-muted-foreground mb-5" style={{ letterSpacing: "-0.01em" }}>
              Manufacturing — Textiles · Est. 2010
            </p>
            <dl className="space-y-3">
              {[
                { label: "CIN", value: "U12345MH2010PTC201234" },
                { label: "Jurisdiction", value: "Maharashtra, India" },
                { label: "Employees", value: "450+ Permanent" },
                { label: "Last Review", value: "October 2024" },
              ].map((item) => (
                <div key={item.label} className="flex justify-between border-b border-border pb-2.5">
                  <dt className="font-mono text-[10px] text-muted-foreground tracking-wider uppercase">{item.label}</dt>
                  <dd className="text-sm font-medium" style={{ letterSpacing: "-0.01em" }}>{item.value}</dd>
                </div>
              ))}
            </dl>
            <button className="btn-ghost w-full mt-5 text-sm">
              View Full History
            </button>
          </div>

          {/* Strengths + Risks */}
          <div className="lg:col-span-3 space-y-4">
            {/* Strengths */}
            <div className="glass-card border-l-2 border-foreground">
              <div className="flex items-center gap-2.5 mb-4">
                <TrendingUp className="w-4 h-4" />
                <p className="section-label mb-0">Key Strengths</p>
              </div>
              <div className="space-y-4">
                {STRENGTHS.map((s) => (
                  <div key={s.n} className="flex items-start gap-3">
                    <span className="font-mono text-[10px] text-muted-foreground tracking-wider mt-0.5 w-5 shrink-0">{s.n}</span>
                    <div>
                      <p className="text-sm font-semibold" style={{ letterSpacing: "-0.01em" }}>{s.title}</p>
                      <p className="text-xs text-muted-foreground mt-0.5" style={{ letterSpacing: "-0.01em" }}>{s.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Risks */}
            <div className="glass-card border-l-2 border-foreground/30">
              <div className="flex items-center gap-2.5 mb-4">
                <AlertTriangle className="w-4 h-4 text-muted-foreground" />
                <p className="section-label mb-0">Primary Risk Factors</p>
              </div>
              <div className="space-y-4">
                {RISKS.map((r) => (
                  <div key={r.n} className="flex items-start gap-3">
                    <span className="font-mono text-[10px] text-muted-foreground tracking-wider mt-0.5 w-5 shrink-0">{r.n}</span>
                    <div>
                      <p className="text-sm font-semibold" style={{ letterSpacing: "-0.01em" }}>{r.title}</p>
                      <p className="text-xs text-muted-foreground mt-0.5" style={{ letterSpacing: "-0.01em" }}>{r.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── Decision bar (sticky) ── */}
        {!decision && (
          <div className="glass-card flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold" style={{ letterSpacing: "-0.01em" }}>
                Select final action
              </p>
              <p className="font-mono text-[10px] text-muted-foreground tracking-wider mt-0.5">
                PACK #{appId?.toUpperCase()} · SANCTIONING AUTHORITY DECISION
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                className="btn-ghost h-10 px-4 text-sm"
                onClick={() => handleDecision("return")}
                disabled={isDeciding}
              >
                Return
              </button>
              <button
                className="btn-ghost h-10 px-4 text-sm"
                onClick={() => handleDecision("reject")}
                disabled={isDeciding}
              >
                Reject
              </button>
              <button
                className="btn-primary h-10 px-6 text-sm"
                onClick={() => handleDecision("approve")}
                disabled={isDeciding}
              >
                {isDeciding ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  "Approve Sanction"
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
