import { useState, useRef } from "react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { useAuth, getRoleLabel } from "@/lib/auth";
import { useUploadDocument, useDocuments, useDeleteDocument, useDocumentChecklist, useApplications } from "@/hooks/useApi";
import { FileText, BarChart3, Upload, Trash2, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "sonner";

const NAV = [
  { label: "Dashboard", path: "/borrower" },
  { label: "Pre-Qualification", path: "/borrower/pre-qual" },
  { label: "Documents", path: "/borrower/apply" },
];

interface DocItem {
  name: string;
  desc?: string;
  extracted?: string;
  warning?: string;
  fileName?: string;
  id?: string;
  fileUrl?: string;
}

const tabsData: Record<string, DocItem[]> = {
  "Identity & Legal": [
    { name: "Certificate of Incorporation", status: "uploaded", extracted: "CIN: U12345MH2010PTC201234 ✅" },
    { name: "MOA & AOA", status: "uploaded", extracted: "Company Type: Private Limited ✅" },
    { name: "PAN Card", status: "uploaded", extracted: "PAN: ABCDE1234F ✅" },
    { name: "GST Registration Certificate", status: "empty" },
    { name: "Board Resolution", status: "empty" },
  ],
  Financials: [
    { name: "Balance Sheet", desc: "Audited Balance Sheet for FY 2023-24", status: "uploaded", extracted: "Extracted: Revenue ₹45.2 Cr" },
    { name: "Profit & Loss Statement", desc: "Detailed P&L statement for last 2 fiscal years", status: "processing", fileName: "PL_FINAL_2024.PDF" },
    { name: "Audit Report", status: "empty" },
    { name: "Cash Flow Statement", status: "empty" },
  ],
  GST: [
    { name: "GSTR-3B (Last 24 months)", status: "uploaded", extracted: "Total GST Turnover: ₹42.1 Cr ✅" },
    { name: "GSTR-1 (Last 24 months)", status: "uploaded", extracted: "Filed: 22/24 months ✅" },
    { name: "GSTR-2B (Last 12 months)", status: "empty" },
    { name: "ITC Reconciliation Statement", status: "empty" },
  ],
  Bank: [
    { name: "Current Account Statement (12 months)", status: "uploaded", extracted: "Avg Monthly Balance: ₹24.5 L ✅" },
    { name: "CC/OD Account Statement", status: "uploaded", warning: "2 bounced EMIs detected — Please confirm" },
    { name: "Savings Account Statement", status: "empty" },
    { name: "FD/Collateral Account Statement", status: "empty" },
  ],
  ITR: [
    { name: "ITR-6 FY 2023-24", status: "uploaded", extracted: "Net Taxable Income: ₹3.8 Cr ✅" },
    { name: "ITR-6 FY 2022-23", status: "uploaded", extracted: "Net Taxable Income: ₹3.2 Cr ✅" },
    { name: "Form 26AS (Last 2 years)", status: "empty" },
    { name: "Computation of Income", status: "empty" },
  ],
  Collateral: [
    { name: "Property Title Deed", status: "uploaded", extracted: "Property Value: ₹18.5 Cr ✅" },
    { name: "Valuation Report", status: "processing" },
    { name: "Encumbrance Certificate", status: "empty" },
    { name: "Property Tax Receipts", status: "empty" },
    { name: "Legal Opinion Report", status: "empty" },
  ],
  Others: [
    { name: "Sanction Letter (existing loans)", status: "uploaded", extracted: "Existing Loan: ₹4.2 Cr ✅" },
    { name: "Lease Agreement (if rented premises)", status: "empty" },
    { name: "Insurance Policy", status: "empty" },
    { name: "Any Other Supporting Document", status: "empty" },
  ],
};

const tabs = Object.keys(tabsData);

export default function DocumentUpload() {
  const [activeTab, setActiveTab] = useState("Financials");
  const [uploadingDocType, setUploadingDocType] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { userName, role } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Use applicationId from navigate state, fallback to the user's latest application
  const { data: appsData, isLoading: isLoadingApps } = useApplications();
  const fallbackAppId = appsData?.data?.[0]?.id;
  
  // Don't use the hardcoded demo ID if we don't have to, wait for real data
  const applicationId = location.state?.applicationId || fallbackAppId || "5b62b322-26f6-498c-84d4-539c94b7c8df";

  const uploadMutation = useUploadDocument();
  const deleteMutation = useDeleteDocument();
  
  // Only fetch documents if we are not loading apps (to prevent 500s on bad fallback ID)
  const { data: documentsData, isLoading: isLoadingDocs } = useDocuments(
    applicationId, 
    { enabled: !isLoadingApps } // Add enabled parameter if supported by useDocuments, otherwise we just handle it via isLoading
  );
  
  const isLoading = isLoadingApps || isLoadingDocs;

  // Merge uploaded documents with the static required checklist structure
  // Cast documentsData as any to bypass TypeScript complaining 'data' doesn't exist on unknown
  const uploadedDocsList = (documentsData as any)?.data || [];

  const derivedTabsData: Record<string, any[]> = {};
  for (const [tabName, requiredDocs] of Object.entries(tabsData)) {
    derivedTabsData[tabName] = requiredDocs.map(reqDoc => {
      // Find matching uploaded document
      const uploadedMatch = uploadedDocsList.find((d: any) => d.document_type === reqDoc.name);

      if (uploadedMatch) {
        return {
          ...reqDoc,
          status: uploadedMatch.status === "parsed" || uploadedMatch.status === "verified" ? "uploaded" : "processing",
          extracted: uploadedMatch.status === "parsed" ? "Data Extracted ✅" : undefined,
          fileName: uploadedMatch.file_name,
          id: uploadedMatch.id,
          fileUrl: uploadedMatch.file_url,
        };
      }
      return { ...reqDoc, status: "empty" } as DocItem;
    });
  }

  const docs = derivedTabsData[activeTab] || [];

  const totalDocs = Object.values(derivedTabsData).flat().length;
  const uploadedCount = Object.values(derivedTabsData).flat().filter(d => d.status === "uploaded" || d.status === "processing").length;
  const completeness = Math.round((uploadedCount / totalDocs) * 100);

  const handleUpload = async (docName: string) => {
    setUploadingDocType(docName);
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !uploadingDocType) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("application_id", applicationId);
    formData.append("document_type", uploadingDocType);

    const toastId = toast.loading(`Uploading ${uploadingDocType}...`);

    uploadMutation.mutate(formData, {
      onSuccess: () => {
        toast.success(`${uploadingDocType} uploaded successfully!`, { id: toastId });
      },
      onError: (err) => {
        toast.error(`Failed to upload ${uploadingDocType}`, { id: toastId });
      },
      onSettled: () => {
        if (fileInputRef.current) fileInputRef.current.value = "";
        setUploadingDocType(null);
      }
    });
  };

  const handleView = (doc: DocItem) => {
    if (doc.fileUrl) {
      window.open(doc.fileUrl, "_blank");
    } else {
      toast.error("File URL not found");
    }
  };

  const handleDelete = (doc: DocItem) => {
    if (!doc.id) return;
    if (window.confirm(`Are you sure you want to delete ${doc.name}?`)) {
      const toastId = toast.loading(`Deleting ${doc.name}...`);
      deleteMutation.mutate(doc.id, {
        onSuccess: () => {
          toast.success(`${doc.name} deleted successfully`, { id: toastId });
        },
        onError: () => {
          toast.error(`Failed to delete ${doc.name}`, { id: toastId });
        }
      });
    }
  };

  return (
    <DashboardLayout role="borrower" roleLabel={getRoleLabel(role)} navItems={NAV} userName={userName}>
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-end justify-between border-b border-border pb-6 mb-6">
          <div>
            <p className="section-label">Borrower · Step 2 of 2</p>
            <h1 className="font-display" style={{ fontSize: "2rem", letterSpacing: "-0.05em" }}>
              Document Upload
            </h1>
            <p className="text-sm text-muted-foreground mt-1" style={{ letterSpacing: "-0.01em" }}>
              Provide the necessary business documentation for verification.
            </p>
          </div>
          <div className="text-right">
            <p className="font-mono text-xs font-bold">{completeness}%</p>
            <div className="w-48 progress-track mt-1.5">
              <div className="progress-fill" style={{ width: `${completeness}%` }} />
            </div>
            <p className="font-mono text-[10px] text-muted-foreground tracking-wider mt-1">
              {uploadedCount}/{totalDocs} UPLOADED
            </p>
          </div>
        </div>

        {/* Tabs */}
        <div className="tab-bar mb-6">
          {tabs.map((tab) => {
            const tabDocs = derivedTabsData[tab];
            const tabUploaded = tabDocs.filter(d => d.status !== "empty").length;
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`tab-item ${activeTab === tab ? "active" : ""}`}
              >
                {tab}
                <span
                  className={`ml-1.5 font-mono text-[9px] px-1.5 py-0.5 rounded-[2px] ${tabUploaded === tabDocs.length ? "badge-success" : "badge-neutral"
                    }`}
                >
                  {tabUploaded}/{tabDocs.length}
                </span>
              </button>
            );
          })}
        </div>

        {/* Hidden file input */}
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          accept=".pdf,.jpg,.png,.xlsx,.csv"
          onChange={handleFileChange}
        />

        {/* Documents */}
        <div className="space-y-3">
          {isLoading ? (
            <div className="text-center py-12">
              <Loader2 className="w-8 h-8 animate-spin mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground text-sm">Loading documents...</p>
            </div>
          ) : docs.map((doc) => (
            <div
              key={doc.name}
              className={`glass-card transition-all ${doc.status === "empty" ? "border-dashed" : ""
                }`}
            >
              {doc.status === "uploaded" && (
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-[3px] bg-foreground/6 border border-border flex items-center justify-center shrink-0">
                      {doc.extracted ? <BarChart3 className="w-4 h-4 text-foreground" /> : <FileText className="w-4 h-4 text-muted-foreground" />}
                    </div>
                    <div>
                      <p className="font-medium text-sm" style={{ letterSpacing: "-0.01em" }}>{doc.name}</p>
                      {doc.desc && <p className="text-xs text-muted-foreground">{doc.desc}</p>}
                      {doc.extracted && (
                        <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1.5">
                          <CheckCircle2 className="w-3 h-3 text-foreground" /> {doc.extracted}
                        </p>
                      )}
                      {doc.warning && (
                        <p className="text-xs mt-1 flex items-center gap-1.5 font-medium">
                          <AlertTriangle className="w-3 h-3" /> {doc.warning}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={() => handleView(doc)} className="btn-ghost h-7 px-3 text-xs">View</button>
                    <button onClick={() => handleDelete(doc)} className="w-7 h-7 rounded-[3px] border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}

              {doc.status === "processing" && (
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-[3px] bg-foreground/6 border border-border flex items-center justify-center shrink-0">
                      <BarChart3 className="w-4 h-4 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="font-medium text-sm" style={{ letterSpacing: "-0.01em" }}>{doc.name}</p>
                      {doc.desc && <p className="text-xs text-muted-foreground">{doc.desc}</p>}
                      <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1.5 italic">
                        <Loader2 className="w-3 h-3 animate-spin" /> AI Extracting data...
                      </p>
                    </div>
                  </div>
                  {doc.fileName && <span className="badge-info">{doc.fileName}</span>}
                </div>
              )}

              {doc.status === "empty" && (
                <div className="text-center py-4 cursor-pointer" onClick={() => handleUpload(doc.name)}>
                  <Upload className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
                  <p className="font-medium text-sm" style={{ letterSpacing: "-0.01em" }}>{doc.name}</p>
                  <p className="text-xs text-muted-foreground mt-1 mb-3">Click to upload or drag and drop (PDF, max 10MB)</p>
                  <button className="btn-ghost text-xs h-8 px-4">Upload Document</button>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Bottom Bar */}
        <div className="glass-card flex items-center justify-between mt-6">
          <p className="font-mono text-[10px] text-muted-foreground tracking-wider">
            AUTO-SAVE ENABLED · AES-256 ENCRYPTED
          </p>
          <div className="flex gap-2">
            <button className="btn-ghost text-sm">Save Draft</button>
            <button className="btn-primary text-sm">Submit Application</button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
