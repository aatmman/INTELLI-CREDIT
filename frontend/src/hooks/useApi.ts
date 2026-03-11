/**
 * React Query hooks for all backend API endpoints.
 * Every page should use these hooks instead of calling api.ts directly.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { preQual, applications, documents, fieldVisit, analysis, cam, riskScore, decisions } from "@/lib/api";

// ── Pre-Qualification ──
export const usePreQualCheck = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (data: any) => preQual.check(data),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
    });
};

export const useSectorWeights = () =>
    useQuery({ queryKey: ["sector-weights"], queryFn: preQual.getSectorWeights, staleTime: 60_000 });

// ── Applications ──
export const useApplications = (params?: { stage?: string; page?: number; page_size?: number }) =>
    useQuery({
        queryKey: ["applications", params],
        queryFn: () => applications.list(params),
    });

export const useApplication = (id: string) =>
    useQuery({
        queryKey: ["application", id],
        queryFn: () => applications.get(id),
        enabled: !!id,
    });

export const useCreateApplication = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (data: any) => applications.create(data),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
    });
};

export const useUpdateApplication = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: any }) => applications.update(id, data),
        onSuccess: (_, v) => qc.invalidateQueries({ queryKey: ["application", v.id] }),
    });
};

export const useTransitionStage = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: any }) => applications.transitionStage(id, data),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
    });
};

// ── Documents ──
export const useUploadDocument = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (formData: FormData) => documents.upload(formData),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
    });
};

export const useDeleteDocument = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (documentId: string) => documents.delete(documentId),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
    });
};

export const useDocuments = (applicationId: string, options?: any) =>
    useQuery({
        queryKey: ["documents", applicationId],
        queryFn: () => documents.list(applicationId),
        enabled: !!applicationId,
        ...options,
    });

export const useDocumentStatus = (documentId: string) =>
    useQuery({
        queryKey: ["doc-status", documentId],
        queryFn: () => documents.getStatus(documentId),
        enabled: !!documentId,
        refetchInterval: 5000,
    });

export const useDocumentCompleteness = (applicationId: string) =>
    useQuery({
        queryKey: ["doc-completeness", applicationId],
        queryFn: () => documents.getCompleteness(applicationId),
        enabled: !!applicationId,
    });

export const useDocumentChecklist = (loanType: string) =>
    useQuery({
        queryKey: ["doc-checklist", loanType],
        queryFn: () => documents.getChecklist(loanType),
        enabled: !!loanType,
    });

// ── Field Visit ──
export const useSubmitFieldVisit = () =>
    useMutation({ mutationFn: (data: any) => fieldVisit.submit(data) });

export const useFieldVisit = (applicationId: string) =>
    useQuery({
        queryKey: ["field-visit", applicationId],
        queryFn: () => fieldVisit.get(applicationId),
        enabled: !!applicationId,
    });

// ── Analysis ──
export const useFinancialAnalysis = (appId: string) =>
    useQuery({ queryKey: ["analysis-financial", appId], queryFn: () => analysis.getFinancial(appId), enabled: !!appId });

export const useGSTAnalysis = (appId: string) =>
    useQuery({ queryKey: ["analysis-gst", appId], queryFn: () => analysis.getGST(appId), enabled: !!appId });

export const useBankingAnalysis = (appId: string) =>
    useQuery({ queryKey: ["analysis-banking", appId], queryFn: () => analysis.getBanking(appId), enabled: !!appId });

export const useResearchAnalysis = (appId: string) =>
    useQuery({ queryKey: ["analysis-research", appId], queryFn: () => analysis.getResearch(appId), enabled: !!appId });

export const useRiskTimeline = (appId: string) =>
    useQuery({ queryKey: ["analysis-timeline", appId], queryFn: () => analysis.getRiskTimeline(appId), enabled: !!appId });

export const useTriggerResearch = () =>
    useMutation({ mutationFn: (appId: string) => analysis.triggerResearch(appId) });

export const useRunWhatIf = () =>
    useMutation({ mutationFn: ({ appId, data }: { appId: string; data: any }) => analysis.runWhatIf(appId, data) });

export const useTriggerFullAnalysis = () =>
    useMutation({ mutationFn: (appId: string) => analysis.triggerFullAnalysis(appId) });

// ── CAM ──
export const useGenerateCAM = () =>
    useMutation({ mutationFn: (appId: string) => cam.generate(appId) });

export const useCAM = (appId: string) =>
    useQuery({ queryKey: ["cam", appId], queryFn: () => cam.get(appId), enabled: !!appId });

// ── Risk Score ──
export const useComputeRiskScore = () =>
    useMutation({ mutationFn: ({ appId, includeShap }: { appId: string; includeShap?: boolean }) => riskScore.compute(appId, includeShap) });

export const useRiskScore = (appId: string) =>
    useQuery({ queryKey: ["risk-score", appId], queryFn: () => riskScore.get(appId), enabled: !!appId });

export const usePolicyChecks = (appId: string) =>
    useQuery({ queryKey: ["policy-checks", appId], queryFn: () => riskScore.getPolicyChecks(appId), enabled: !!appId });

export const useRateRecommendation = (appId: string) =>
    useQuery({ queryKey: ["rate-rec", appId], queryFn: () => riskScore.getRateRecommendation(appId), enabled: !!appId });

// ── Decisions ──
export const useSubmitDecision = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ appId, data }: { appId: string; data: any }) => decisions.submit(appId, data),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
    });
};

export const useDecision = (appId: string) =>
    useQuery({ queryKey: ["decision", appId], queryFn: () => decisions.get(appId), enabled: !!appId });

export const useDecisionPack = (appId: string) =>
    useQuery({ queryKey: ["decision-pack", appId], queryFn: () => decisions.getDecisionPack(appId), enabled: !!appId });

export const useGenerateSanctionLetter = () =>
    useMutation({ mutationFn: ({ appId, data }: { appId: string; data: any }) => decisions.generateSanctionLetter(appId, data) });
