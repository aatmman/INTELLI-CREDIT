import { useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import { DashboardLayout } from "@/components/DashboardLayout";
import { useAuth, getRoleLabel } from "@/lib/auth";
import { useApplication, useDocuments, useTransitionStage } from "@/hooks/useApi";
import { ArrowLeft, Download, CheckCircle2, AlertTriangle, XCircle, Flag, Share2, Clock, Loader2, ArrowRight } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

const NAV = [
  { label: "Dashboard", path: "/rm" },
  { label: "Applications", path: "/rm" },
];



const RISK_SIGNALS = [
  { label: "Identity Verified", ok: true },
  { label: "Sanctions Clear", ok: true },
  { label: "Minor Credit Lag", ok: false },
  { label: "No Adverse Media", ok: true },
];



export default function RMApplicationReview() {
  const [activeTab, setActiveTab] = useState("Summary");
  const navigate = useNavigate();
  const { appId } = useParams<{ appId: string }>();
  const { userName, role } = useAuth();
  const tabs = ["Summary", "Verification", "Actions"];

  // API hooks
  const { data: appData } = useApplication(appId || "");
  const { data: docsRes } = useDocuments(appId || "");
  const verificationDocs = docsRes?.data?.items || [];
  const company = appData?.data || {};
  const transitionMutation = useTransitionStage();

  const handleForward = async () => {
    if (!appId) return;
    try {
      await transitionMutation.mutateAsync({
        id: appId,
        data: { target_stage: "credit_analysis", remarks: "RM review complete, forwarded to analyst" },
      });
    } catch { /* handled by mutation */ }
  };

  return (
    <DashboardLayout role="rm" roleLabel={getRoleLabel(role)} navItems={NAV} userName={userName}>
      <div className="max-w-6xl mx-auto">
        {/* App header */}
        <div className="flex items-center gap-4 border-b border-border pb-5 mb-6">
          <button onClick={() => navigate("/rm")} className="w-9 h-9 rounded-[3px] border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex-1">
            <p className="section-label mb-0.5">RM Review</p>
            <h1 className="font-display text-xl" style={{ letterSpacing: "-0.04em" }}>
              {company.company_name || "Unknown Company"}
            </h1>
            <p className="font-mono text-[10px] text-muted-foreground tracking-wider mt-0.5">
              APP #{appId?.toUpperCase()} · {company.loan_type || "N/A"} · ₹{Number(company.loan_amount_requested || 0).toLocaleString("en-IN")}
            </p>
          </div>
          <StatusBadge variant="warning">UNDER REVIEW</StatusBadge>
        </div>

        {/* Tabs */}
        <div className="tab-bar mb-6">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`tab-item ${activeTab === tab ? "active" : ""}`}
            >
              {tab}
            </button>
          ))}
        </div>

        {activeTab === "Summary" && (
          <div className="space-y-5">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Company Snapshot */}
              <div className="glass-card lg:col-span-2">
                <p className="section-label mb-3">Company Snapshot</p>
                <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                  {[
                    { label: "Entity Type", value: company.entity_type || "N/A" },
                    { label: "Registration", value: company.registration || "N/A" },
                    { label: "Jurisdiction", value: company.jurisdiction || "N/A" },
                    { label: "Industry", value: company.industry || "N/A" },
                  ].map((item) => (
                    <div key={item.label} className="border-b border-border pb-2.5">
                      <p className="font-mono text-[10px] text-muted-foreground tracking-wider uppercase mb-1">{item.label}</p>
                      <p className="text-sm font-medium" style={{ letterSpacing: "-0.01em" }}>{item.value}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Risk Signals */}
              <div className="glass-card">
                <p className="section-label mb-3">Risk Signals</p>
                <div className="space-y-3">
                  {RISK_SIGNALS.map((rs) => (
                    <div key={rs.label} className="flex items-center gap-2.5">
                      <span className={rs.ok ? "risk-dot-low" : "risk-dot-med"} />
                      <span className="text-sm" style={{ letterSpacing: "-0.01em" }}>{rs.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Pre-Qual Score */}
              <div className="glass-card">
                <div className="flex items-center justify-between mb-3">
                  <p className="section-label mb-0">Pre-Qual Score</p>
                  <span className="font-display text-2xl" style={{ letterSpacing: "-0.04em" }}>
                    {company.pre_qual_score || 0}<span className="text-sm font-normal text-muted-foreground">/100</span>
                  </span>
                </div>
                <div className="progress-track h-1.5">
                  <div className="progress-fill" style={{ width: `${company.pre_qual_score || 0}%` }} />
                </div>
              </div>

              {/* System Verdict */}
              <div className="glass-card border-l-2 border-foreground">
                <p className="section-label mb-1">System Verdict</p>
                <h3 className="font-display text-xl mb-2" style={{ letterSpacing: "-0.04em" }}>Proceed Recommended</h3>
                <p className="text-xs text-muted-foreground" style={{ letterSpacing: "-0.01em" }}>
                  Application meets the standard risk profile for private manufacturing entities. Verification of minor credit lag is advised.
                </p>
              </div>
            </div>

            {/* Bottom info */}
            <div className="glass-card flex items-center justify-between">
              <div className="flex gap-8">
                <div>
                  <p className="font-mono text-[10px] text-muted-foreground tracking-wider uppercase">Assigned To</p>
                  <p className="text-sm font-medium mt-0.5" style={{ letterSpacing: "-0.01em" }}>{userName}</p>
                </div>
                <div>
                  <p className="font-mono text-[10px] text-muted-foreground tracking-wider uppercase">SLA Timer</p>
                  <p className="text-sm font-medium mt-0.5 flex items-center gap-1.5">
                    <Clock className="w-3 h-3 text-muted-foreground" />
                    <span className="font-mono">02h : 14m : 11s</span>
                  </p>
                </div>
              </div>
              <div className="flex gap-1.5">
                <button className="w-8 h-8 rounded-[3px] border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors">
                  <Flag className="w-3.5 h-3.5" />
                </button>
                <button className="w-8 h-8 rounded-[3px] border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors">
                  <Share2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === "Verification" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="section-label mb-0">Document Verification</p>
              <div className="flex gap-2">
                <button className="btn-ghost h-8 px-3 text-xs gap-1.5"><Download className="w-3 h-3" /> Download</button>
                <button className="btn-primary h-8 px-3 text-xs">Submit Final Call</button>
              </div>
            </div>
            <div className="glass-card p-0 overflow-hidden">
              <table className="data-table">
                <thead>
                  <tr>
                    {["", "Document", "Uploaded", "Result", ""].map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {verificationDocs.map((doc: any) => (
                    <tr key={doc.document_type || doc.id}>
                      <td className="w-10">
                        <input type="checkbox" className="rounded border-border accent-foreground" defaultChecked />
                      </td>
                      <td>
                        <span className="font-medium text-sm" style={{ letterSpacing: "-0.01em" }}>{doc.document_type?.replace(/_/g, ' ') || "Document"}</span>
                      </td>
                      <td>
                        <span className="font-mono text-xs text-muted-foreground">{doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : "—"}</span>
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          {doc.verification_status === "verified" ? <CheckCircle2 className="w-3.5 h-3.5" /> :
                            doc.verification_status === "failed" ? <XCircle className="w-3.5 h-3.5" /> :
                              <AlertTriangle className="w-3.5 h-3.5 text-muted-foreground" />}
                          <span className="text-xs" style={{ letterSpacing: "-0.01em" }}>{doc.verification_remarks || doc.verification_status || "Pending"}</span>
                        </div>
                      </td>
                      <td>
                        <button className="font-mono text-[10px] text-muted-foreground hover:text-foreground tracking-wider">RESUBMIT</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === "Actions" && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 mb-2">
              <StatusBadge variant="warning">UNDER REVIEW</StatusBadge>
              <span className="font-mono text-[10px] text-muted-foreground tracking-wider">APPLICATION #{appId?.toUpperCase()}</span>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {[
                { title: "Send Back to Borrower", desc: "Return application with notes for revision", btnLabel: "Send", primary: false },
                { title: "Reject Application", desc: "Generate rejection letter with reasons", btnLabel: "Reject", primary: false },
                { title: "Assign Field Visit", desc: "Schedule on-site verification visit", btnLabel: "Schedule", primary: false },
                { title: "Forward to Analysis Team", desc: "Requires completeness ≥ 80%", btnLabel: "Forward", primary: true },
              ].map((action) => (
                <div key={action.title} className="glass-card">
                  <h4 className="font-semibold text-sm mb-1" style={{ letterSpacing: "-0.01em" }}>{action.title}</h4>
                  <p className="text-xs text-muted-foreground mb-3" style={{ letterSpacing: "-0.01em" }}>{action.desc}</p>
                  <textarea className="ic-input mb-3 resize-none" rows={2} placeholder="Add notes..." style={{ height: "auto" }} />
                  <button
                    className={action.primary ? "btn-primary w-full text-sm gap-2" : "btn-ghost w-full text-sm"}
                    onClick={action.primary ? handleForward : undefined}
                    disabled={action.primary && transitionMutation.isPending}
                  >
                    {action.primary && transitionMutation.isPending ? (
                      <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Forwarding...</>
                    ) : (
                      <>{action.btnLabel} {action.primary && <ArrowRight className="w-3.5 h-3.5" />}</>
                    )}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
