import { DashboardLayout } from "@/components/DashboardLayout";
import { useAuth, getRoleLabel } from "@/lib/auth";
import { useApplications } from "@/hooks/useApi";
import { useNavigate } from "react-router-dom";
import { Filter, Download, ChevronLeft, ChevronRight, Loader2, AlertCircle, ArrowRight } from "lucide-react";

const NAV = [
  { label: "Dashboard", path: "/rm" },
  { label: "Applications", path: "/rm" },
  { label: "Reports", path: "/rm" },
];

const DEMO_APPS = [
  { id: "APP-2490", company_name: "Acme Corp Industries", loan_type: "Term Loan", loan_amount_requested: 14_00_00_000, created_at: "2024-10-12", completeness: 80, pre_qual: "PASS", current_stage: "rm_review" },
  { id: "APP-2491", company_name: "Global Tech Solutions", loan_type: "Cash Credit", loan_amount_requested: 8_50_00_000, created_at: "2024-10-14", completeness: 45, pre_qual: "PASS", current_stage: "document_upload" },
  { id: "APP-2492", company_name: "Delta Logistics Pvt Ltd", loan_type: "WCTL", loan_amount_requested: 25_00_00_000, created_at: "2024-10-15", completeness: 100, pre_qual: "PASS", current_stage: "decision" },
  { id: "APP-2493", company_name: "Starlight Ventures", loan_type: "Bank Guarantee", loan_amount_requested: 6_00_00_000, created_at: "2024-10-18", completeness: 92, pre_qual: "BORDERLINE", current_stage: "analysis" },
];

const stageLabel = (stage: string) => {
  const map: Record<string, string> = {
    pre_qualification: "Pre-Qual",
    document_upload: "Documents",
    rm_review: "In Review",
    analysis: "Analysis",
    decision: "Approved",
  };
  return map[stage] || stage;
};

const stageStyle = (stage: string) => {
  if (stage === "decision") return "badge-success";
  if (stage === "rm_review") return "badge-dark";
  if (stage === "analysis") return "badge-info";
  return "badge-neutral";
};

const preQualStyle = (pq: string) => {
  if (pq === "PASS") return "badge-success";
  if (pq === "BORDERLINE") return "badge-warning";
  return "badge-danger";
};

export default function RMDashboard() {
  const { userName, role } = useAuth();
  const navigate = useNavigate();
  const { data, isLoading, error } = useApplications();

  const apiApps = data?.data?.items;
  const apps = apiApps && apiApps.length > 0 ? apiApps : DEMO_APPS;
  const isDemo = !apiApps || apiApps.length === 0;

  const stats = [
    { label: "Total Pipeline", value: String(apps.length) },
    { label: "Awaiting Action", value: String(apps.filter((a: any) => a.current_stage === "rm_review").length) },
    { label: "In Analysis", value: String(apps.filter((a: any) => a.current_stage === "analysis").length) },
    { label: "Completed", value: String(apps.filter((a: any) => a.current_stage === "decision").length) },
  ];

  return (
    <DashboardLayout role="rm" roleLabel={getRoleLabel(role)} navItems={NAV} userName={userName}>
      <div className="space-y-8">

        {/* ── Header ── */}
        <div className="border-b border-border pb-6">
          <p className="section-label">Relationship Manager</p>
          <h1 className="font-display" style={{ fontSize: "2.25rem", letterSpacing: "-0.05em" }}>
            RM Dashboard
          </h1>
          <p className="text-sm text-muted-foreground mt-1" style={{ letterSpacing: "-0.01em" }}>
            Corporate Credit · Application Pipeline
          </p>
        </div>

        {/* ── Stats ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {stats.map((s, i) => (
            <div key={i} className="glass-card">
              <p className="stat-label">{s.label}</p>
              <p className="stat-value">{s.value}</p>
            </div>
          ))}
        </div>

        {/* ── Pipeline table ── */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <p className="section-label mb-0">Application Pipeline</p>
            <div className="flex items-center gap-2">
              {isDemo && error && (
                <span className="badge-warning flex items-center gap-1.5">
                  <AlertCircle className="w-3 h-3" /> Demo data
                </span>
              )}
              <button className="btn-ghost h-8 px-3 text-xs gap-1.5">
                <Filter className="w-3 h-3" /> Filter
              </button>
              <button className="btn-ghost h-8 px-3 text-xs gap-1.5">
                <Download className="w-3 h-3" /> Export
              </button>
            </div>
          </div>

          <div className="glass-card p-0 overflow-hidden">
            {isLoading ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                <span className="ml-3 text-sm text-muted-foreground">Loading applications...</span>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead>
                    <tr>
                      {["Company", "Loan Type", "Amount", "Date", "Completeness", "Pre-Qual", "Stage", ""].map((h) => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {apps.map((app: any) => (
                      <tr key={app.id} className="cursor-pointer" onClick={() => navigate(`/rm/${app.id}`)}>
                        <td>
                          <div>
                            <p className="font-medium text-sm" style={{ letterSpacing: "-0.01em" }}>{app.company_name}</p>
                            <p className="font-mono text-[10px] text-muted-foreground tracking-wider">#{app.id?.slice(0, 8)}</p>
                          </div>
                        </td>
                        <td>
                          <span className="badge-neutral">{app.loan_type}</span>
                        </td>
                        <td>
                          <span className="font-mono text-sm font-medium">
                            ₹{Number(app.loan_amount_requested || 0).toLocaleString("en-IN")}
                          </span>
                        </td>
                        <td>
                          <span className="font-mono text-xs text-muted-foreground">
                            {app.created_at ? new Date(app.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : "—"}
                          </span>
                        </td>
                        <td>
                          <div className="flex items-center gap-2">
                            <div className="w-20 progress-track">
                              <div className="progress-fill" style={{ width: `${app.completeness || 0}%` }} />
                            </div>
                            <span className="font-mono text-[11px] text-muted-foreground">{app.completeness || 0}%</span>
                          </div>
                        </td>
                        <td>
                          <span className={preQualStyle(app.pre_qual || "")}>
                            {app.pre_qual || "—"}
                          </span>
                        </td>
                        <td>
                          <span className={stageStyle(app.current_stage || "")}>
                            {stageLabel(app.current_stage || "")}
                          </span>
                        </td>
                        <td>
                          <button
                            className="btn-ghost h-7 px-3 text-xs gap-1"
                            onClick={(e) => { e.stopPropagation(); navigate(`/rm/${app.id}`); }}
                          >
                            Review <ArrowRight className="w-3 h-3" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            <div className="flex items-center justify-between px-5 py-3 border-t border-border">
              <span className="font-mono text-[10px] text-muted-foreground tracking-wider">
                SHOWING 1–{apps.length} OF {apps.length}
              </span>
              <div className="flex items-center gap-1">
                <button className="w-7 h-7 rounded-[3px] border border-border flex items-center justify-center text-muted-foreground hover:border-foreground/30 transition-colors">
                  <ChevronLeft className="w-3.5 h-3.5" />
                </button>
                <button className="w-7 h-7 rounded-[3px] bg-foreground text-background flex items-center justify-center font-mono text-xs">
                  1
                </button>
                <button className="w-7 h-7 rounded-[3px] border border-border flex items-center justify-center text-muted-foreground hover:border-foreground/30 transition-colors">
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
