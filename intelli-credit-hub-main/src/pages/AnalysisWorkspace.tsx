import { useState } from "react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { useAuth, getRoleLabel } from "@/lib/auth";
import { Download, AlertTriangle, Info, TrendingUp, Scale, Wallet, BarChart3, ChevronDown, ChevronUp, Loader2, ArrowRight } from "lucide-react";
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
} from "recharts";
import { useParams, useNavigate } from "react-router-dom";
import { useFinancialAnalysis, useGSTAnalysis, useBankingAnalysis, useResearchAnalysis, useRiskTimeline, useGenerateCAM } from "@/hooks/useApi";

const NAV = [
  { label: "Workspace", path: "#" },
  { label: "Field Visit", path: "#" },
];

const C = {
  ink: "hsl(0 0% 4%)",
  dim: "hsl(0 0% 60%)",
  grid: "hsl(0 0% 91%)",
  muted: "hsl(0 0% 40%)",
};

const TT = {
  backgroundColor: "#fff",
  border: "1px solid hsl(0 0% 88%)",
  borderRadius: "3px",
  color: "hsl(0 0% 4%)",
  boxShadow: "0 4px 16px hsl(0 0% 0% / 0.06)",
  fontSize: "11px",
  fontFamily: "'JetBrains Mono', monospace",
};

const financialData = [
  { year: "FY22", revenue: 36.4, ebitda: 4.2, margin: 12.5 },
  { year: "FY23", revenue: 40.8, ebitda: 4.9, margin: 12.0 },
  { year: "FY24", revenue: 45.2, ebitda: 5.4, margin: 11.6 },
];

const gstBarData = Array.from({ length: 12 }, (_, i) => ({
  month: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][i],
  gstr3b: Math.round(300 + Math.random() * 200),
  gstr1: Math.round(280 + Math.random() * 200),
  bank: Math.round(350 + Math.random() * 150),
}));

const bankingBarData = Array.from({ length: 12 }, (_, i) => ({
  month: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][i],
  credits: Math.round(400 + Math.random() * 300),
  debits: Math.round(300 + Math.random() * 250),
}));

const balanceData = Array.from({ length: 12 }, (_, i) => ({
  month: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][i],
  balance: Math.round(200 + Math.sin(i / 2) * 100 + Math.random() * 50),
}));

const itcData = [
  { month: "Oct 2023", available: "₹12.4L", claimed: "₹11.8L", mismatch: false },
  { month: "Nov 2023", available: "₹14.1L", claimed: "₹13.9L", mismatch: false },
  { month: "Dec 2023", available: "₹11.2L", claimed: "₹15.6L", mismatch: true },
  { month: "Jan 2024", available: "₹13.5L", claimed: "₹13.0L", mismatch: false },
  { month: "Feb 2024", available: "₹12.8L", claimed: "₹12.5L", mismatch: false },
  { month: "Mar 2024", available: "₹15.1L", claimed: "₹14.8L", mismatch: false },
];

const researchFindings = [
  { severity: "HIGH", source: "MCA21", title: "Active charge ₹8.2 Cr — HDFC Bank (registered Mar 2024)", date: "Mar 2024", impact: "+22 pts" },
  { severity: "HIGH", source: "News", title: "Promoter named in GST evasion investigation (Economic Times)", date: "Nov 2023", impact: "+18 pts" },
  { severity: "MED", source: "e-Courts", title: "Pending civil suit — MSME supplier payment dispute ₹45L", date: "Jan 2024", impact: "+8 pts" },
  { severity: "MED", source: "RBI/Sector", title: "Manufacturing sector: 12% input cost increase (steel)", date: "Feb 2024", impact: "+5 pts" },
  { severity: "LOW", source: "RBI", title: "Not listed in RBI defaulter / caution list ✓", date: "Current", impact: "−4 pts" },
];

const timelineEvents = [
  { date: "Mar 2024", source: "MCA", title: "Active charge ₹8.2 Cr registered — HDFC Bank", impact: "+22 pts", high: true },
  { date: "Feb 2024", source: "GST", title: "ITC reversal anomaly detected — Q3 FY24", impact: "+12 pts", high: false },
  { date: "Jan 2024", source: "Courts", title: "Civil suit filed — supplier payment dispute ₹45L", impact: "+8 pts", high: false },
  { date: "Nov 2023", source: "News", title: "Promoter mentioned in GST investigation report", impact: "+18 pts", high: true },
  { date: "Aug 2023", source: "Banking", title: "2 EMI bounces — ₹3.2L total (Aug 2023)", impact: "+10 pts", high: false },
  { date: "Jul 2023", source: "GST", title: "GSTR-3B filing missed — Jul 2023", impact: "+6 pts", high: false },
];

const camSections = [
  { title: "Executive Summary", done: true, content: "Acme Corp is a mid-sized manufacturing entity established in 2010 with annual revenue of ₹45.2 Cr (FY24). Consistent revenue growth of 20% YoY with stable EBITDA margins. Proposed credit facility: ₹14 Cr for business expansion. [Source: FY24 Balance Sheet, pg.12]" },
  { title: "Borrower Profile", done: true, content: "Entity Type: Private Limited · CIN: U12345MH2010PTC201234 · Maharashtra. Key promoter: Rajesh Kumar (52%). Industry: Textile Manufacturing. [Source: Certificate of Incorporation]" },
  { title: "Financial Analysis", done: true, content: "Revenue CAGR 11.4% (FY22–24). EBITDA stable at ~12%. DSCR 2.45× — strong debt servicing. D/E 0.82 within limits. Net worth +18% to ₹22.4 Cr. [Source: Audited Financial Statements FY22-24]" },
  { title: "GST Analysis", done: false, content: "GST turnover ₹42.1 Cr. Compliance 22/24 months. ITC reversal anomaly Dec 2023: claimed exceeds available by ₹4.4L. Circular trading risk: 65/100 (HIGH). [Source: GSTR-3B, GSTR-1]" },
  { title: "Banking Behavior", done: true, content: "Avg monthly balance ₹24.5L. Two EMI bounces Aug 2023. Cash withdrawal within normal range. Banking conduct score: 72/100. [Source: Bank Statements 12 months]" },
  { title: "External Research", done: true, content: "Active charge ₹8.2 Cr HDFC Bank (MCA21, Mar 2024). Promoter in GST investigation (ET, Nov 2023). Civil suit ₹45L. Not on RBI defaulter list. [Source: MCA, News, e-Courts, RBI]" },
  { title: "Risk Assessment", done: false, content: "Total risk score: 76 basis points across 8 events. Highest severity: Nov 2023. Key concerns: circular trading risk, active MCA charge, promoter investigation. [Source: Multi-source analysis]" },
  { title: "Collateral Analysis", done: true, content: "Primary: Commercial property ₹18.5 Cr (LTV 75.7%). Encumbrance certificate pending. Collateral cover 1.32×. [Source: Property Deed, Valuation Report]" },
  { title: "Recommendations", done: true, content: "Approve with conditions: (1) Enhanced monitoring 12 months, (2) Quarterly GST reconciliation, (3) Resolve civil suit pre-disbursement, (4) Additional collateral margin 10%. Suggested limit: ₹12.5 Cr. [Source: AI Analysis Engine v2.1]" },
  { title: "Final Credit Opinion", done: false, content: "" },
];

export default function AnalysisWorkspace() {
  const { userName, role } = useAuth();
  const { appId } = useParams<{ appId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("Financials");
  const [gstSub, setGstSub] = useState("GST Analysis");
  const [expandedCam, setExpandedCam] = useState<number[]>([0, 1, 2]);
  const [sliders, setSliders] = useState({ collateral: 18.5, revenue: 0, loan: 14, management: 0 });
  const [isGenerating, setIsGenerating] = useState(false);

  // API hooks — real data when backend online, demo fallback otherwise
  const { data: finApiData } = useFinancialAnalysis(appId || "");
  const { data: gstApiData } = useGSTAnalysis(appId || "");
  const { data: bankApiData } = useBankingAnalysis(appId || "");
  const { data: researchApiData } = useResearchAnalysis(appId || "");
  const { data: timelineApiData } = useRiskTimeline(appId || "");
  const generateCAM = useGenerateCAM();

  const tabs = ["Financials", "GST/Banking", "Research", "Timeline", "CAM", "What-If"];
  const score = Math.round(64 + (sliders.collateral - 18.5) * 0.5 + sliders.revenue * 0.3 - (sliders.loan - 14) * 0.8 + sliders.management * 0.6);
  const grade = score >= 75 ? "B" : score >= 60 ? "C" : "D";

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      await generateCAM.mutateAsync(appId || "");
    } catch {
      await new Promise((r) => setTimeout(r, 2000));
    }
    setIsGenerating(false);
  };

  return (
    <DashboardLayout
      role="analyst"
      roleLabel={getRoleLabel(role)}
      navItems={[...NAV, { label: "Field Visit", path: `/analyst/${appId}/field-visit` }]}
      userName={userName}
    >
      <div className="max-w-7xl mx-auto">
        {/* ── Header ── */}
        <div className="flex items-end justify-between border-b border-border pb-5 mb-6">
          <div>
            <p className="section-label">Credit Analyst · Stage 4</p>
            <h1 className="font-display" style={{ fontSize: "2rem", letterSpacing: "-0.05em" }}>
              Analysis Workspace
            </h1>
            <p className="font-mono text-[10px] text-muted-foreground tracking-wider mt-1">
              ACME CORP INDUSTRIES · APP #{appId?.slice(0, 8)?.toUpperCase()}
            </p>
          </div>
          <button
            onClick={() => navigate(`/analyst/${appId}/field-visit`)}
            className="btn-ghost h-9 px-4 text-xs gap-1.5"
          >
            Field Visit <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        {/* ── Tab bar ── */}
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

        {/* ══════════════════ TAB: Financials ══════════════════ */}
        {activeTab === "Financials" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-xl" style={{ letterSpacing: "-0.04em" }}>
                Financial Performance Overview
              </h2>
              <button className="btn-ghost h-8 px-3 text-xs gap-1.5">
                <Download className="w-3 h-3" /> Export
              </button>
            </div>

            {/* Metrics table */}
            <div className="glass-card p-0 overflow-hidden">
              <table className="data-table">
                <thead>
                  <tr>
                    {["Metric", "FY22", "FY23", "FY24", "YoY Δ", "Trend"].map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    { metric: "Revenue (₹ Cr)", fy22: "36.4", fy23: "40.8", fy24: "45.2", change: "+10.8%", pos: true, key: "revenue" },
                    { metric: "EBITDA (₹ Cr)", fy22: "4.2", fy23: "4.9", fy24: "5.4", change: "+10.2%", pos: true, key: "ebitda" },
                    { metric: "Net Profit Margin", fy22: "12.5%", fy23: "12.0%", fy24: "11.6%", change: "−3.3%", pos: false, key: "margin" },
                  ].map((row) => (
                    <tr key={row.metric}>
                      <td className="font-medium">{row.metric}</td>
                      <td className="font-mono text-muted-foreground">{row.fy22}</td>
                      <td className="font-mono text-muted-foreground">{row.fy23}</td>
                      <td className="font-mono font-medium">{row.fy24}</td>
                      <td>
                        <span className={row.pos ? "badge-success" : "badge-warning"}>{row.change}</span>
                      </td>
                      <td className="w-28">
                        <ResponsiveContainer width="100%" height={28}>
                          <LineChart data={financialData}>
                            <Line
                              type="monotone" dataKey={row.key}
                              stroke={row.pos ? C.ink : C.muted}
                              strokeWidth={1.5} dot={{ r: 2, fill: row.pos ? C.ink : C.muted, strokeWidth: 0 }}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Ratios */}
            <div>
              <p className="section-label">Key Ratios</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: "DSCR", value: "2.45×", sub: "Debt Service Coverage" },
                  { label: "D/E Ratio", value: "0.82", sub: "Leverage Indicator" },
                  { label: "Current Ratio", value: "1.94×", sub: "Liquidity" },
                  { label: "ROE", value: "18.4%", sub: "Return on Equity" },
                ].map((r) => (
                  <div key={r.label} className="glass-card">
                    <p className="stat-label">{r.label}</p>
                    <p className="stat-value">{r.value}</p>
                    <p className="text-xs text-muted-foreground mt-1.5">{r.sub}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Anomalies */}
            <div>
              <p className="section-label">Anomaly Alerts</p>
              <div className="space-y-2.5">
                {[
                  { level: "WARN", title: "Operating Expenses Spike", desc: "OpEx increased 24% in Q3 FY24 vs historical average. Manual review suggested." },
                  { level: "INFO", title: "Unusual Cash Inflow", desc: "One-time payment ₹1.4 Cr in February. Potential misclassification detected." },
                ].map((a) => (
                  <div key={a.title} className={`glass-card flex items-start justify-between border-l-2 ${a.level === "WARN" ? "border-foreground" : "border-foreground/30"}`}>
                    <div className="flex items-start gap-3">
                      <span className={a.level === "WARN" ? "badge-danger" : "badge-info"}>{a.level}</span>
                      <div>
                        <p className="font-medium text-sm" style={{ letterSpacing: "-0.01em" }}>{a.title}</p>
                        <p className="text-xs text-muted-foreground mt-0.5" style={{ letterSpacing: "-0.01em" }}>{a.desc}</p>
                      </div>
                    </div>
                    <button className="text-xs font-mono text-muted-foreground hover:text-foreground whitespace-nowrap ml-4">VIEW →</button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ══════════════════ TAB: GST/Banking ══════════════════ */}
        {activeTab === "GST/Banking" && (
          <div className="space-y-5">
            <div className="tab-bar mb-5">
              {["GST Analysis", "Banking Analysis"].map((st) => (
                <button
                  key={st}
                  onClick={() => setGstSub(st)}
                  className={`tab-item ${gstSub === st ? "active" : ""}`}
                >
                  {st}
                </button>
              ))}
            </div>

            {gstSub === "GST Analysis" && (
              <div className="space-y-5">
                <div className="glass-card">
                  <h3 className="font-semibold mb-4" style={{ letterSpacing: "-0.02em" }}>24-Month GST Turnover Comparison</h3>
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={gstBarData} barGap={1}>
                      <CartesianGrid strokeDasharray="1 4" stroke={C.grid} vertical={false} />
                      <XAxis dataKey="month" tick={{ fontSize: 10, fill: C.dim, fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: C.dim, fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={TT} />
                      <Bar dataKey="gstr3b" fill={C.ink} radius={[2, 2, 0, 0]} name="GSTR-3B" />
                      <Bar dataKey="gstr1" fill="hsl(0 0% 60%)" radius={[2, 2, 0, 0]} name="GSTR-1" />
                      <Bar dataKey="bank" fill="hsl(0 0% 80%)" radius={[2, 2, 0, 0]} name="Bank Turnover" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="glass-card">
                    <h3 className="font-semibold mb-3" style={{ letterSpacing: "-0.02em" }}>ITC Reconciliation</h3>
                    <table className="data-table text-sm">
                      <thead>
                        <tr>{["Month", "Available", "Claimed", "Status"].map((h) => <th key={h}>{h}</th>)}</tr>
                      </thead>
                      <tbody>
                        {itcData.map((r) => (
                          <tr key={r.month} className={r.mismatch ? "bg-foreground/3" : ""}>
                            <td className="font-mono text-xs">{r.month}</td>
                            <td className="font-mono text-xs">{r.available}</td>
                            <td className="font-mono text-xs">{r.claimed}</td>
                            <td>{r.mismatch && <span className="badge-danger">MISMATCH</span>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="space-y-4">
                    <div className="glass-card">
                      <h3 className="font-semibold mb-3" style={{ letterSpacing: "-0.02em" }}>Filing Calendar</h3>
                      {[2023, 2024].map((yr) => (
                        <div key={yr} className="mb-2">
                          <p className="font-mono text-[10px] text-muted-foreground tracking-wider mb-1.5">{yr}</p>
                          <div className="grid grid-cols-12 gap-0.5">
                            {["J","F","M","A","M","J","J","A","S","O","N","D"].map((m, i) => {
                              const miss = yr === 2023 && i === 6;
                              return (
                                <div key={i} className={miss ? "filing-cell-miss" : "filing-cell-ok"}>
                                  {m}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="glass-card border-l-2 border-foreground">
                      <p className="section-label mb-2">Circular Trading Risk</p>
                      <div className="flex items-baseline gap-2 mb-2">
                        <span className="font-display" style={{ fontSize: "2.5rem", letterSpacing: "-0.05em" }}>65</span>
                        <span className="font-mono text-[10px] text-muted-foreground">/100</span>
                        <span className="badge-danger ml-1">HIGH RISK</span>
                      </div>
                      <ul className="space-y-1 text-xs text-muted-foreground font-mono">
                        <li>· Bank-GST mismatch 2.99× detected</li>
                        <li>· ITC reversal anomaly found</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {gstSub === "Banking Analysis" && (
              <div className="space-y-5">
                <div className="glass-card">
                  <h3 className="font-semibold mb-4" style={{ letterSpacing: "-0.02em" }}>Credits vs Debits (12 months)</h3>
                  <ResponsiveContainer width="100%" height={230}>
                    <BarChart data={bankingBarData} barGap={2}>
                      <CartesianGrid strokeDasharray="1 4" stroke={C.grid} vertical={false} />
                      <XAxis dataKey="month" tick={{ fontSize: 10, fill: C.dim, fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: C.dim, fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={TT} />
                      <Bar dataKey="credits" fill={C.ink} radius={[2, 2, 0, 0]} name="Credits" />
                      <Bar dataKey="debits" fill="hsl(0 0% 75%)" radius={[2, 2, 0, 0]} name="Debits" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="glass-card">
                  <h3 className="font-semibold mb-4" style={{ letterSpacing: "-0.02em" }}>End-of-Month Balance Trend</h3>
                  <ResponsiveContainer width="100%" height={180}>
                    <LineChart data={balanceData}>
                      <CartesianGrid strokeDasharray="1 4" stroke={C.grid} vertical={false} />
                      <XAxis dataKey="month" tick={{ fontSize: 10, fill: C.dim, fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: C.dim, fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={TT} />
                      <Line type="monotone" dataKey="balance" stroke={C.ink} strokeWidth={1.5} dot={{ r: 2.5, fill: C.ink, strokeWidth: 0 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="glass-card">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold" style={{ letterSpacing: "-0.02em" }}>Banking Conduct Score</h3>
                    <span className="font-display text-2xl" style={{ letterSpacing: "-0.04em" }}>
                      72<span className="text-sm font-normal text-muted-foreground">/100</span>
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { label: "Bounce Frequency", status: "LOW", ok: true },
                      { label: "Cash Withdrawal", status: "MEDIUM", ok: false },
                      { label: "EMI Burden", status: "LOW", ok: true },
                      { label: "Balance Volatility", status: "MEDIUM", ok: false },
                    ].map((b) => (
                      <div key={b.label} className="flex items-center justify-between p-3 rounded-[3px] bg-muted/50 border border-border">
                        <span className="text-xs" style={{ letterSpacing: "-0.01em" }}>{b.label}</span>
                        <span className={b.ok ? "badge-success" : "badge-warning"}>{b.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ══════════════════ TAB: Research ══════════════════ */}
        {activeTab === "Research" && (
          <div className="space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-display text-xl" style={{ letterSpacing: "-0.04em" }}>External Research Findings</h2>
                <p className="text-xs text-muted-foreground mt-1 font-mono">Research Agent: 4/5 complete</p>
              </div>
              <div className="flex items-center gap-2">
                <div className="progress-track w-32">
                  <div className="progress-fill" style={{ width: "80%" }} />
                </div>
              </div>
            </div>

            <div className="flex gap-1.5">
              {["All", "News", "MCA", "e-Courts", "Sector", "RBI"].map((f) => (
                <button
                  key={f}
                  className={`h-7 px-3 text-xs font-mono rounded-[3px] transition-colors ${
                    f === "All"
                      ? "bg-foreground text-background"
                      : "bg-muted text-muted-foreground hover:text-foreground border border-border hover:border-foreground/30"
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>

            <div className="space-y-2.5">
              {researchFindings.map((f, i) => (
                <div
                  key={i}
                  className={`glass-card border-l-2 ${
                    f.severity === "HIGH" ? "border-foreground" : f.severity === "MED" ? "border-foreground/40" : "border-foreground/15"
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1.5">
                          <span
                            className={
                              f.severity === "HIGH"
                                ? "badge-danger"
                                : f.severity === "MED"
                                ? "badge-warning"
                                : "badge-success"
                            }
                          >
                            {f.severity}
                          </span>
                          <span className="badge-neutral">{f.source}</span>
                        </div>
                        <p className="font-medium text-sm" style={{ letterSpacing: "-0.01em" }}>{f.title}</p>
                        <p className="font-mono text-[10px] text-muted-foreground mt-1 tracking-wider">
                          {f.date} · RISK IMPACT: {f.impact}
                        </p>
                      </div>
                    </div>
                    {i === 0 && (
                      <span className="font-mono text-[10px] text-muted-foreground tracking-wider shrink-0">REVIEWED ✓</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ══════════════════ TAB: Timeline ══════════════════ */}
        {activeTab === "Timeline" && (
          <div className="space-y-6">
            <div>
              <h2 className="font-display text-xl" style={{ letterSpacing: "-0.04em" }}>Risk Timeline</h2>
              <p className="text-xs text-muted-foreground mt-1 font-mono tracking-wider">
                8 RISK EVENTS · 3 SOURCES · HIGHEST SEVERITY: NOV 2023
              </p>
            </div>

            <div className="relative pl-9">
              <div className="timeline-line" />
              {timelineEvents.map((e, i) => (
                <div key={i} className="relative flex items-start gap-4 mb-6 last:mb-0">
                  <div className={e.high ? "timeline-dot-high" : "timeline-dot-med"} />
                  <span className="font-mono text-[10px] text-muted-foreground tracking-wider min-w-[56px] pt-0.5">
                    {e.date}
                  </span>
                  <div className="glass-card flex-1">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="badge-neutral">{e.source}</span>
                      <span className={e.high ? "badge-danger" : "badge-warning"}>{e.impact}</span>
                    </div>
                    <p className="text-sm font-medium" style={{ letterSpacing: "-0.01em" }}>{e.title}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ══════════════════ TAB: CAM ══════════════════ */}
        {activeTab === "CAM" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-display text-xl" style={{ letterSpacing: "-0.04em" }}>Credit Appraisal Memo</h2>
                <p className="font-mono text-[10px] text-muted-foreground tracking-wider mt-1">
                  v2 · Generated 2 hours ago · Analyst edited 3 sections
                </p>
              </div>
              <button
                className="btn-primary gap-2"
                onClick={handleGenerate}
                disabled={isGenerating}
              >
                {isGenerating ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
                ) : (
                  <><BarChart3 className="w-4 h-4" /> Regenerate CAM</>
                )}
              </button>
            </div>

            <div className="space-y-1.5">
              {camSections.map((s, i) => {
                const expanded = expandedCam.includes(i);
                return (
                  <div key={i} className="glass-card p-0 overflow-hidden">
                    <button
                      onClick={() => setExpandedCam((prev) =>
                        prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]
                      )}
                      className="w-full px-5 py-3.5 flex items-center justify-between text-left hover:bg-muted/30 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-[10px] text-muted-foreground tracking-wider w-5">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <span className="text-sm font-medium" style={{ letterSpacing: "-0.01em" }}>{s.title}</span>
                        <span className={s.done ? "badge-success" : "badge-neutral"}>
                          {s.done ? "DONE" : "DRAFT"}
                        </span>
                      </div>
                      {expanded ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                    </button>
                    {expanded && s.content && (
                      <div className="px-5 pb-4">
                        <div className="bg-muted/40 rounded-[3px] p-4 text-sm text-muted-foreground leading-relaxed border border-border" style={{ letterSpacing: "-0.01em" }}>
                          {s.content}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <button className="btn-primary w-full h-12">Submit to Credit Manager</button>
          </div>
        )}

        {/* ══════════════════ TAB: What-If ══════════════════ */}
        {activeTab === "What-If" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Sliders */}
            <div className="space-y-4">
              <div>
                <h2 className="font-display text-xl mb-1" style={{ letterSpacing: "-0.04em" }}>What-If Simulator</h2>
                <p className="text-xs text-muted-foreground font-mono tracking-wider">Adjust inputs to see score impact</p>
              </div>

              {[
                { label: "Collateral Value", value: sliders.collateral, min: 9.25, max: 27.75, unit: "₹ Cr", key: "collateral" as const },
                { label: "Revenue Scenario", value: sliders.revenue, min: -30, max: 30, unit: "%", key: "revenue" as const },
                { label: "Loan Amount", value: sliders.loan, min: 5, max: 25, unit: "₹ Cr", key: "loan" as const },
                { label: "Management Score Adj.", value: sliders.management, min: -10, max: 10, unit: "pts", key: "management" as const },
              ].map((s) => (
                <div key={s.key} className="glass-card">
                  <div className="flex items-center justify-between mb-3">
                    <label className="text-sm font-medium" style={{ letterSpacing: "-0.01em" }}>{s.label}</label>
                    <span className="font-mono text-sm font-bold">
                      {s.value.toFixed(1)} {s.unit}
                    </span>
                  </div>
                  <input
                    type="range" min={s.min} max={s.max} step={0.1} value={s.value}
                    onChange={(e) => setSliders((prev) => ({ ...prev, [s.key]: parseFloat(e.target.value) }))}
                    className="w-full"
                  />
                  <div className="flex justify-between mt-1">
                    <span className="font-mono text-[9px] text-muted-foreground">{s.min} {s.unit}</span>
                    <span className="font-mono text-[9px] text-muted-foreground">{s.max} {s.unit}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Result */}
            <div className="space-y-4">
              {/* Score display */}
              <div className="card-ink text-center py-10">
                <p className="font-mono text-[10px] tracking-[0.15em] uppercase mb-4" style={{ color: "hsl(0 0% 100% / 0.4)" }}>
                  Simulated Risk Score
                </p>
                <div
                  className="font-display mb-2"
                  style={{ fontSize: "5rem", lineHeight: 1, letterSpacing: "-0.06em", color: "hsl(var(--background))" }}
                >
                  {score}
                </div>
                <p className="font-mono text-sm" style={{ color: "hsl(0 0% 100% / 0.5)" }}>
                  Grade: {grade}
                </p>
              </div>

              {/* SHAP visual */}
              <div className="glass-card">
                <p className="section-label mb-3">Top SHAP Factors</p>
                {[
                  { label: "Cash Flow", value: 65, pos: true },
                  { label: "Collateral", value: 50, pos: true },
                  { label: "Revenue Growth", value: 40, pos: true },
                  { label: "Market Volatility", value: 45, pos: false },
                  { label: "Industry Risk", value: 30, pos: false },
                ].map((f) => (
                  <div key={f.label} className="flex items-center gap-3 mb-2.5">
                    <span className="font-mono text-[10px] text-muted-foreground text-right w-28 shrink-0">{f.label}</span>
                    <div className="flex-1 h-3 bg-muted rounded-[2px] overflow-hidden">
                      <div
                        className={`h-full rounded-[2px] transition-all duration-500 ${f.pos ? "bg-foreground" : "bg-foreground/30"}`}
                        style={{ width: `${f.value}%` }}
                      />
                    </div>
                    <span className="font-mono text-[10px] text-muted-foreground w-6">{f.value}%</span>
                  </div>
                ))}
              </div>

              <p className="font-mono text-xs text-muted-foreground tracking-wider">
                COLLATERAL IMPACT:{" "}
                <span className="text-foreground">
                  {sliders.collateral > 18.5
                    ? `−${((sliders.collateral - 18.5) * 0.5).toFixed(1)} pts`
                    : `+${((18.5 - sliders.collateral) * 0.5).toFixed(1)} pts`}
                </span>
              </p>

              <button className="btn-ghost w-full text-sm">Export Scenario</button>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
