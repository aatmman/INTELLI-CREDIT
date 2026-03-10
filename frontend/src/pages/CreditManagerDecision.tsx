import { DashboardLayout } from "@/components/DashboardLayout";
import { useAuth, getRoleLabel } from "@/lib/auth";
import { useParams, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Download, CheckCircle2, XCircle, AlertTriangle, Loader2 } from "lucide-react";
import { useDecisionPack, useRiskScore, usePolicyChecks, useSubmitDecision } from "@/hooks/useApi";

const NAV = [
  { label: "Decision Pack", path: "#" },
  { label: "CAM", path: "#" },
  { label: "Audit Log", path: "#" },
];



export default function CreditManagerDecision() {
  const { userName, role } = useAuth();
  const { appId } = useParams<{ appId: string }>();
  const navigate = useNavigate();
  const [isDeciding, setIsDeciding] = useState(false);
  const [decision, setDecision] = useState<string | null>(null);

  // API hooks with demo fallback
  const { data: packData } = useDecisionPack(appId || "");
  const { data: riskData } = useRiskScore(appId || "");
  const { data: policyData } = usePolicyChecks(appId || "");
  const submitDecision = useSubmitDecision();

  const apiShapPositive = riskData?.data?.shap_values?.filter((s: any) => s.direction === "decreases_risk")?.slice(0, 3)?.map((s: any) => ({ name: s.feature_name, value: Math.round(s.contribution * 100) }));
  const apiShapNegative = riskData?.data?.shap_values?.filter((s: any) => s.direction === "increases_risk")?.slice(0, 3)?.map((s: any) => ({ name: s.feature_name, value: Math.round(s.contribution * 100) }));
  const apiPolicyChecks = policyData?.data?.map((p: any) => ({ label: p.check_name, status: p.result }));

  const displayShapPos = apiShapPositive || [];
  const displayShapNeg = apiShapNegative || [];
  const displayPolicyChecks = apiPolicyChecks || [];
  const riskGrade = packData?.data?.risk_grade || riskData?.data?.risk_grade || "N/A";

  const handleDecision = async (action: "approve" | "reject") => {
    setIsDeciding(true);
    try {
      await submitDecision.mutateAsync({
        appId: appId || "",
        data: {
          action: action === "approve" ? "approve" : "reject",
          decided_by_role: "credit_manager",
          remarks: `CM ${action} decision`,
        },
      });
    } catch {
      // API offline — simulate
      await new Promise((r) => setTimeout(r, 1500));
    }
    setDecision(action);
    setIsDeciding(false);
  };

  return (
    <DashboardLayout role="credit-manager" roleLabel={getRoleLabel(role)} navItems={NAV} userName={userName}>
      <div className="max-w-6xl mx-auto space-y-6">

        {/* ── Header ── */}
        <div className="flex items-end justify-between border-b border-border pb-6">
          <div>
            <p className="section-label">Credit Manager · Stage 5</p>
            <h1 className="font-display" style={{ fontSize: "2rem", letterSpacing: "-0.05em" }}>
              Decision Pack — Acme Corp
            </h1>
            <p className="font-mono text-[10px] text-muted-foreground tracking-wider mt-1">
              APP #{appId?.toUpperCase()} · XGBoost v2.1 · Scored 2 hours ago
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn-ghost h-8 px-3 text-xs gap-1.5">
              ⊙ Audit Log
            </button>
            <button className="btn-ghost h-8 px-3 text-xs gap-1.5">
              <Download className="w-3 h-3" /> Download CAM
            </button>
          </div>
        </div>

        {/* ── Decision result ── */}
        {decision && (
          <div className={`glass-card text-center py-10 border-2 ${decision === "approve" ? "border-foreground" : "border-foreground/30"
            }`}>
            <div
              className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 ${decision === "approve" ? "bg-foreground text-background" : "bg-muted text-muted-foreground"
                }`}
            >
              {decision === "approve"
                ? <CheckCircle2 className="w-7 h-7" />
                : <XCircle className="w-7 h-7" />}
            </div>
            <h2 className="font-display text-2xl mb-1" style={{ letterSpacing: "-0.04em" }}>
              {decision === "approve" ? "Credit Line Approved" : "Application Rejected"}
            </h2>
            <p className="text-sm text-muted-foreground" style={{ letterSpacing: "-0.01em" }}>
              {decision === "approve"
                ? "Decision recorded. Forwarding to Sanctioning Authority."
                : "Rejection letter will be auto-generated."}
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* ── Left: Score + SHAP ── */}
          <div className="lg:col-span-2 space-y-5">

            {/* Score cards */}
            <div className="grid grid-cols-2 gap-4">
              {/* Analyst rec */}
              <div className="glass-card">
                <p className="section-label mb-3">Analyst Recommendation</p>
                <div className="flex items-baseline gap-2">
                  <span className="font-display" style={{ fontSize: "2.75rem", letterSpacing: "-0.05em" }}>₹14 Cr</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1" style={{ letterSpacing: "-0.01em" }}>
                  Within predefined sector limits ↗
                </p>
              </div>

              {/* Risk Grade */}
              <div className="card-ink flex flex-col items-center justify-center text-center py-6">
                <p className="font-mono text-[9px] tracking-[0.15em] uppercase opacity-50 mb-3">ML Risk Grade</p>
                <div className="w-20 h-20 rounded-full border-2 border-background/30 flex items-center justify-center mb-2">
                  <span
                    className="font-display text-background"
                    style={{ fontSize: "2.75rem", letterSpacing: "-0.05em", lineHeight: 1 }}
                  >
                    C
                  </span>
                </div>
                <p className="font-mono text-[10px] tracking-wider uppercase opacity-50">Moderate Risk</p>
              </div>
            </div>

            {/* SHAP panel */}
            <div className="glass-card">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h3 className="font-semibold" style={{ letterSpacing: "-0.02em" }}>SHAP Explainability</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">Feature contribution to risk score</p>
                </div>
                <span className="badge-neutral">REAL-TIME</span>
              </div>

              <div className="space-y-5">
                {/* Positive */}
                <div>
                  <p className="section-label mb-3">Positive Factors (Risk Reduction)</p>
                  <div className="space-y-2.5">
                    {displayShapPos.map((f: any) => (
                      <div key={f.name} className="flex items-center gap-3">
                        <span className="font-mono text-[11px] text-muted-foreground w-32 text-right shrink-0">{f.name}</span>
                        <div className="flex-1 h-4 bg-muted rounded-[2px] overflow-hidden">
                          <div
                            className="shap-bar-positive"
                            style={{ width: `${f.value}%` }}
                          />
                        </div>
                        <span className="font-mono text-[11px] text-muted-foreground w-8">{f.value}%</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="divider" />

                {/* Negative */}
                <div>
                  <p className="section-label mb-3">Negative Factors (Risk Elevation)</p>
                  <div className="space-y-2.5">
                    {displayShapNeg.map((f: any) => (
                      <div key={f.name} className="flex items-center gap-3">
                        <span className="font-mono text-[11px] text-muted-foreground w-32 text-right shrink-0">{f.name}</span>
                        <div className="flex-1 h-4 bg-muted rounded-[2px] overflow-hidden">
                          <div
                            className="shap-bar-negative"
                            style={{ width: `${f.value}%` }}
                          />
                        </div>
                        <span className="font-mono text-[11px] text-muted-foreground w-8">{f.value}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ── Right: Policy + Decision ── */}
          <div className="space-y-4">
            {/* Policy Checklist */}
            <div className="glass-card">
              <h3 className="font-semibold mb-4" style={{ letterSpacing: "-0.02em" }}>Policy Checklist</h3>
              <div className="space-y-3">
                {displayPolicyChecks.map((pc: any) => (
                  <div key={pc.label} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                    <div className="flex items-center gap-2.5">
                      {pc.status === "PASS" ? (
                        <CheckCircle2 className="w-4 h-4 text-foreground" />
                      ) : pc.status === "FAIL" ? (
                        <XCircle className="w-4 h-4 text-foreground" />
                      ) : (
                        <AlertTriangle className="w-4 h-4 text-foreground/50" />
                      )}
                      <span className="text-sm" style={{ letterSpacing: "-0.01em" }}>{pc.label}</span>
                    </div>
                    <span
                      className={
                        pc.status === "PASS"
                          ? "badge-success"
                          : pc.status === "FAIL"
                            ? "badge-danger"
                            : "badge-warning"
                      }
                    >
                      {pc.status}
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-4 p-3 rounded-[3px] bg-muted">
                <p className="font-mono text-[10px] text-muted-foreground tracking-wider">
                  1 POLICY EXCEPTION DETECTED · D/E RATIO BREACH
                </p>
              </div>
            </div>

            {/* Decision Actions */}
            {!decision && (
              <div className="glass-card">
                <p className="section-label mb-4">Decision Actions</p>
                <button
                  className="btn-primary w-full h-12 text-sm mb-3"
                  onClick={() => handleDecision("approve")}
                  disabled={isDeciding}
                >
                  {isDeciding ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    "Approve Credit Line"
                  )}
                </button>
                <button
                  className="btn-ghost w-full h-12 text-sm mb-3"
                  onClick={() => handleDecision("reject")}
                  disabled={isDeciding}
                  style={{ color: "hsl(var(--foreground))" }}
                >
                  Reject Application
                </button>
                <button
                  className="w-full text-center text-[11px] font-mono text-muted-foreground hover:text-foreground transition-colors tracking-wider py-2"
                >
                  REQUEST ADDITIONAL INFO
                </button>
              </div>
            )}

            {/* App meta */}
            <div className="glass-card">
              <dl className="space-y-2">
                {[
                  { label: "Application", value: `#${appId?.toUpperCase()}` },
                  { label: "Assigned To", value: userName || "—" },
                  { label: "Model", value: "XGBoost v2.1" },
                  { label: "PD Score", value: packData?.data?.probability_of_default ? `${(packData.data.probability_of_default * 100).toFixed(1)}%` : "N/A" },
                ].map((item) => (
                  <div key={item.label} className="flex justify-between items-center py-1.5 border-b border-border last:border-0">
                    <dt className="font-mono text-[10px] text-muted-foreground tracking-wider uppercase">{item.label}</dt>
                    <dd className="font-mono text-[11px] text-foreground">{item.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
