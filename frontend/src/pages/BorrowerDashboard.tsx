import { DashboardLayout } from "@/components/DashboardLayout";
import { useAuth, getRoleLabel } from "@/lib/auth";
import { useApplications } from "@/hooks/useApi";
import { useNavigate } from "react-router-dom";
import { FileText, Upload, Clock, CheckCircle, ArrowRight, Loader2, AlertCircle } from "lucide-react";

const NAV = [
  { label: "Dashboard", path: "/borrower" },
  { label: "Applications", path: "/borrower/applications" },
  { label: "Documents", path: "/borrower/apply" },
  { label: "Settings", path: "/borrower/profile" },
];

const STAGE_STEPS = [
  { key: "pre_qualification", label: "Pre-Qual" },
  { key: "document_upload", label: "Docs" },
  { key: "rm_review", label: "RM Review" },
  { key: "analysis", label: "Analysis" },
  { key: "decision", label: "Decision" },
];

export default function BorrowerDashboard() {
  const { userName, role } = useAuth();
  const navigate = useNavigate();
  const { data, isLoading, error } = useApplications();
  const apps = data?.data?.items || [];
  const activeApp = apps.length > 0 ? apps[0] : null;

  const getStageIndex = (stage: string) => {
    const idx = STAGE_STEPS.findIndex((s) => s.key === stage);
    return idx >= 0 ? idx : 0;
  };

  return (
    <DashboardLayout role="borrower" roleLabel={getRoleLabel(role)} navItems={NAV} userName={userName}>
      <div className="max-w-5xl mx-auto space-y-8">

        {/* ── Header ── */}
        <div className="flex items-end justify-between border-b border-border pb-6">
          <div>
            <p className="section-label">Borrower Portal</p>
            <h1 className="font-display" style={{ fontSize: "2.25rem", letterSpacing: "-0.05em" }}>
              {userName}
            </h1>
            <p className="text-muted-foreground text-sm mt-1" style={{ letterSpacing: "-0.01em" }}>
              Your credit application dashboard.
            </p>
          </div>
          <button
            onClick={() => navigate("/borrower/pre-qual")}
            className="btn-primary gap-2"
          >
            New Application <ArrowRight className="w-4 h-4" />
          </button>
        </div>

        {/* ── Stats row ── */}
        <div className="grid grid-cols-3 gap-4">
          {[
            {
              label: "Applications",
              value: isLoading ? "—" : String(apps.length),
              sub: apps.length > 0 ? "Active" : "None yet",
            },
            {
              label: "Completeness",
              value: activeApp ? "78%" : "—",
              sub: activeApp ? "4 docs pending" : "Start an application",
              bar: activeApp ? 78 : null,
            },
            {
              label: "Eligibility",
              value: activeApp ? "PASS" : "—",
              sub: activeApp ? "Pre-qual approved" : "Complete pre-qual",
              tag: activeApp,
            },
          ].map((s, i) => (
            <div key={i} className="glass-card">
              <p className="stat-label">{s.label}</p>
              {s.tag ? (
                <div className="mt-2 flex items-center gap-2">
                  <CheckCircle className="w-4 h-4" />
                  <span className="font-display text-xl" style={{ letterSpacing: "-0.04em" }}>
                    {s.value}
                  </span>
                </div>
              ) : (
                <p className="stat-value">{s.value}</p>
              )}
              {s.bar && (
                <div className="progress-track mt-3">
                  <div className="progress-fill" style={{ width: `${s.bar}%` }} />
                </div>
              )}
              <p className="text-xs text-muted-foreground mt-2" style={{ letterSpacing: "-0.01em" }}>{s.sub}</p>
            </div>
          ))}
        </div>

        {/* ── Active Application ── */}
        {isLoading ? (
          <div className="glass-card flex items-center justify-center py-16">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            <span className="ml-3 text-sm text-muted-foreground">Loading...</span>
          </div>
        ) : error ? (
          <div className="glass-card border-l-4 border-foreground">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-muted-foreground mt-0.5" />
              <div>
                <h3 className="font-semibold text-sm mb-1">Backend offline</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Start with <code className="text-xs bg-muted px-1.5 py-0.5 rounded-[2px] font-mono">python main.py</code>
                </p>
                <button className="btn-ghost text-xs h-8 px-3" onClick={() => navigate("/borrower/pre-qual")}>
                  Start New Application →
                </button>
              </div>
            </div>
          </div>
        ) : activeApp ? (
          <div className="glass-card">
            <div className="flex items-start justify-between mb-6">
              <div>
                <p className="section-label mb-1">Active Application</p>
                <h3 className="font-display text-xl" style={{ letterSpacing: "-0.04em" }}>
                  {activeApp.company_name || "Business Expansion Loan"}
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {activeApp.loan_type} · ₹{Number(activeApp.loan_amount_requested || 0).toLocaleString("en-IN")}
                </p>
              </div>
              <span className="font-mono text-[10px] text-muted-foreground tracking-wider">
                REF #{activeApp.id?.slice(0, 8)?.toUpperCase()}
              </span>
            </div>

            {/* Progress bar + steps */}
            <div className="relative mb-6">
              {/* Track */}
              <div className="absolute top-3.5 left-0 right-0 h-px bg-border" />
              <div className="flex items-start justify-between relative">
                {STAGE_STEPS.map((step, i) => {
                  const currentIdx = getStageIndex(activeApp.current_stage || "document_upload");
                  const isDone = i < currentIdx;
                  const isCurrent = i === currentIdx;
                  return (
                    <div key={step.key} className="flex flex-col items-center w-1/5">
                      <div
                        className={`w-7 h-7 rounded-full flex items-center justify-center z-10 transition-colors ${
                          isDone
                            ? "bg-foreground"
                            : isCurrent
                            ? "bg-foreground ring-4 ring-background"
                            : "bg-background border border-border"
                        }`}
                      >
                        {isDone ? (
                          <CheckCircle className="w-3.5 h-3.5 text-background" />
                        ) : (
                          <span
                            className={`font-mono text-[10px] font-bold ${
                              isCurrent ? "text-background" : "text-muted-foreground"
                            }`}
                          >
                            {i + 1}
                          </span>
                        )}
                      </div>
                      <p
                        className={`text-[10px] font-mono tracking-wider uppercase mt-2 text-center ${
                          isCurrent
                            ? "text-foreground font-medium"
                            : isDone
                            ? "text-foreground/60"
                            : "text-muted-foreground"
                        }`}
                      >
                        {step.label}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>

            <p className="text-sm text-muted-foreground" style={{ letterSpacing: "-0.01em" }}>
              Currently in{" "}
              <span className="text-foreground font-medium">
                {activeApp.current_stage?.replace(/_/g, " ")}
              </span>{" "}
              stage.
            </p>
          </div>
        ) : (
          <div className="glass-card text-center py-16">
            <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
              <FileText className="w-5 h-5 text-muted-foreground" />
            </div>
            <h3 className="font-display text-xl mb-2" style={{ letterSpacing: "-0.04em" }}>
              No applications yet
            </h3>
            <p className="text-sm text-muted-foreground mb-6" style={{ letterSpacing: "-0.01em" }}>
              Start your credit journey with a free eligibility check.
            </p>
            <button onClick={() => navigate("/borrower/pre-qual")} className="btn-primary gap-2">
              Check Eligibility <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* ── Quick Actions ── */}
        <div>
          <p className="section-label">Quick Actions</p>
          <div className="grid grid-cols-3 gap-3">
            {[
              {
                icon: <Upload className="w-5 h-5" />,
                label: "Upload Documents",
                sub: "Submit required files",
                path: "/borrower/apply",
              },
              {
                icon: <FileText className="w-5 h-5" />,
                label: "Pre-Qualification",
                sub: "Check eligibility in 30s",
                path: "/borrower/pre-qual",
              },
              {
                icon: <Clock className="w-5 h-5" />,
                label: "Track Status",
                sub: "View application progress",
                path: "/borrower",
              },
            ].map((action) => (
              <button
                key={action.label}
                onClick={() => navigate(action.path)}
                className="glass-card flex items-center gap-4 text-left group"
              >
                <div className="w-10 h-10 rounded-[3px] bg-foreground/6 border border-border flex items-center justify-center text-muted-foreground group-hover:bg-foreground group-hover:text-background group-hover:border-foreground transition-all">
                  {action.icon}
                </div>
                <div>
                  <p className="text-sm font-semibold" style={{ letterSpacing: "-0.01em" }}>{action.label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{action.sub}</p>
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
              </button>
            ))}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
