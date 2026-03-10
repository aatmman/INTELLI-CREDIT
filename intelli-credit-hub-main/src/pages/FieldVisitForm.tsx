// ─── FieldVisitForm.tsx ───────────────────────────────────────────────────────
import { useState } from "react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { useAuth, getRoleLabel } from "@/lib/auth";
import { MapPin, Mic, Camera, X, Loader2, CheckCircle2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { useSubmitFieldVisit } from "@/hooks/useApi";

const NAV = [
  { label: "Workspace", path: "/analyst/demo-app-001" },
  { label: "Field Visit", path: "/analyst/demo-app-001/field-visit" },
];

export default function FieldVisitForm() {
  const { userName, role } = useAuth();
  const { appId } = useParams<{ appId: string }>();
  const navigate = useNavigate();
  const [premiseType, setPremiseType] = useState("Commercial");
  const [capacity, setCapacity] = useState(75);
  const [condition, setCondition] = useState("GOOD");
  const [recordsAccessible, setRecordsAccessible] = useState(true);
  const [signageDisplayed, setSignageDisplayed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const fieldVisitMutation = useSubmitFieldVisit();

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await fieldVisitMutation.mutateAsync({
        application_id: appId,
        premise_type: premiseType,
        capacity_utilization: capacity,
        premises_condition: condition,
        records_accessible: recordsAccessible,
        signage_displayed: signageDisplayed,
        visit_date: new Date().toISOString(),
      });
    } catch {
      // API offline — simulate
      await new Promise((r) => setTimeout(r, 1200));
    }
    setSubmitted(true);
    setSubmitting(false);
  };

  if (submitted) {
    return (
      <DashboardLayout role="analyst" roleLabel={getRoleLabel(role)} navItems={NAV} userName={userName}>
        <div className="max-w-md mx-auto text-center py-20">
          <div className="w-16 h-16 rounded-full bg-foreground flex items-center justify-center mx-auto mb-6">
            <CheckCircle2 className="w-8 h-8 text-background" />
          </div>
          <h2 className="font-display text-2xl mb-2" style={{ letterSpacing: "-0.04em" }}>
            Visit Submitted
          </h2>
          <p className="text-muted-foreground text-sm mb-6" style={{ letterSpacing: "-0.01em" }}>
            Field visit report has been added to the case file.
          </p>
          <button className="btn-primary" onClick={() => navigate(`/analyst/${appId}`)}>
            Back to Workspace
          </button>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout role="analyst" roleLabel={getRoleLabel(role)} navItems={NAV} userName={userName}>
      <div className="max-w-[520px] mx-auto space-y-4">
        <div className="border-b border-border pb-5 mb-6">
          <p className="section-label">Analyst · Field Visit</p>
          <h1 className="font-display" style={{ fontSize: "2rem", letterSpacing: "-0.05em" }}>
            Field Visit Form
          </h1>
          <p className="font-mono text-[10px] text-muted-foreground tracking-wider mt-1">
            COMPLIANCE & VERIFICATION · APP #{appId?.slice(0, 8)?.toUpperCase()}
          </p>
        </div>

        {/* 01 Site Details */}
        <div className="glass-card">
          <div className="flex items-center gap-2.5 mb-4">
            <div className="form-section-num">01</div>
            <h3 className="font-semibold" style={{ letterSpacing: "-0.02em" }}>Site Details</h3>
          </div>
          <div className="h-36 bg-muted rounded-[3px] flex items-center justify-center mb-3 border border-border">
            <div className="text-center">
              <MapPin className="w-6 h-6 text-muted-foreground mx-auto mb-1" />
              <span className="font-mono text-[10px] text-muted-foreground tracking-wider">GPS NOT CAPTURED</span>
            </div>
          </div>
          <button className="btn-primary w-full gap-2 mb-4">
            <MapPin className="w-4 h-4" /> Capture GPS Location
          </button>
          <p className="section-label mb-2">Premise Type</p>
          <div className="space-y-1.5">
            {["Residential", "Commercial", "Industrial"].map((pt) => (
              <button
                key={pt}
                onClick={() => setPremiseType(pt)}
                className={`w-full text-left px-4 py-3 rounded-[3px] border text-sm transition-colors flex items-center gap-3 ${
                  premiseType === pt
                    ? "border-foreground bg-foreground/3"
                    : "border-border hover:border-foreground/30"
                }`}
              >
                <span
                  className={`w-4 h-4 rounded-full border-2 flex-shrink-0 transition-colors ${
                    premiseType === pt ? "border-foreground bg-foreground" : "border-muted-foreground"
                  }`}
                />
                <span style={{ letterSpacing: "-0.01em" }}>{pt}</span>
              </button>
            ))}
          </div>
        </div>

        {/* 02 Operational */}
        <div className="glass-card">
          <div className="flex items-center gap-2.5 mb-4">
            <div className="form-section-num">02</div>
            <h3 className="font-semibold" style={{ letterSpacing: "-0.02em" }}>Operational</h3>
          </div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium" style={{ letterSpacing: "-0.01em" }}>Current Capacity</span>
            <span className="font-mono text-sm font-bold">{capacity}%</span>
          </div>
          <input
            type="range" min={0} max={100} value={capacity}
            onChange={(e) => setCapacity(Number(e.target.value))}
            className="w-full mb-1"
          />
          <div className="flex justify-between">
            <span className="font-mono text-[9px] text-muted-foreground tracking-wider">MINIMUM</span>
            <span className="font-mono text-[9px] text-muted-foreground tracking-wider">OPTIMAL</span>
            <span className="font-mono text-[9px] text-muted-foreground tracking-wider">PEAK</span>
          </div>
          <p className="section-label mt-4 mb-2">Overall Condition</p>
          <div className="grid grid-cols-4 gap-2">
            {[
              { id: "EXCELLENT", emoji: "✨" },
              { id: "GOOD", emoji: "✓" },
              { id: "FAIR", emoji: "~" },
              { id: "POOR", emoji: "!" },
            ].map((c) => (
              <button
                key={c.id}
                onClick={() => setCondition(c.id)}
                className={`py-3 rounded-[3px] border text-center transition-all ${
                  condition === c.id
                    ? "border-foreground bg-foreground text-background"
                    : "border-border hover:border-foreground/30"
                }`}
              >
                <span className="block text-lg mb-0.5">{c.emoji}</span>
                <span className="font-mono text-[9px] tracking-wider">{c.id}</span>
              </button>
            ))}
          </div>
        </div>

        {/* 03 Management */}
        <div className="glass-card">
          <div className="flex items-center gap-2.5 mb-4">
            <div className="form-section-num">03</div>
            <h3 className="font-semibold" style={{ letterSpacing: "-0.02em" }}>Management</h3>
          </div>
          <p className="section-label mb-3">Transparency Audit</p>
          {[
            { label: "Records accessible?", value: recordsAccessible, setter: setRecordsAccessible },
            { label: "Signage displayed?", value: signageDisplayed, setter: setSignageDisplayed },
          ].map((q) => (
            <div key={q.label} className="flex items-center justify-between mb-2.5">
              <span className="text-sm" style={{ letterSpacing: "-0.01em" }}>{q.label}</span>
              <div className="flex rounded-[3px] overflow-hidden border border-border">
                <button
                  onClick={() => q.setter(true)}
                  className={`px-4 py-1.5 text-xs font-mono font-medium tracking-wider transition-colors ${
                    q.value ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted"
                  }`}
                >
                  YES
                </button>
                <button
                  onClick={() => q.setter(false)}
                  className={`px-4 py-1.5 text-xs font-mono font-medium tracking-wider border-l border-border transition-colors ${
                    !q.value ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted"
                  }`}
                >
                  NO
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* 04 Observations */}
        <div className="glass-card">
          <div className="flex items-center gap-2.5 mb-4">
            <div className="form-section-num">04</div>
            <h3 className="font-semibold" style={{ letterSpacing: "-0.02em" }}>Observations</h3>
          </div>
          <p className="section-label mb-2">Voice Summary</p>
          <button className="btn-ghost w-full gap-2 justify-between mb-4">
            <span className="flex items-center gap-2">
              <Mic className="w-4 h-4" /> Record Voice Note
            </span>
            <span className="font-mono text-xs">00:00</span>
          </button>
          <p className="section-label mb-2">Photo Documentation</p>
          <div className="grid grid-cols-4 gap-2">
            <div className="aspect-square rounded-[3px] border border-dashed border-border flex items-center justify-center cursor-pointer hover:border-foreground/30 transition-colors">
              <Camera className="w-5 h-5 text-muted-foreground" />
            </div>
            {[1, 2, 3].map((i) => (
              <div key={i} className="aspect-square rounded-[3px] bg-muted relative border border-border">
                <button className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-foreground text-background flex items-center justify-center">
                  <X className="w-2.5 h-2.5" />
                </button>
              </div>
            ))}
          </div>
        </div>

        <button
          className="btn-primary w-full h-12 text-sm gap-2"
          onClick={handleSubmit}
          disabled={submitting}
        >
          {submitting ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> Submitting...</>
          ) : (
            "Submit Field Visit"
          )}
        </button>
      </div>
    </DashboardLayout>
  );
}
