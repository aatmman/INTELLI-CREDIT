import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, UserRole } from "@/lib/auth";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import BorrowerDashboard from "./pages/BorrowerDashboard";
import PreQualForm from "./pages/PreQualForm";
import DocumentUpload from "./pages/DocumentUpload";
import RMDashboard from "./pages/RMDashboard";
import RMApplicationReview from "./pages/RMApplicationReview";
import AnalysisWorkspace from "./pages/AnalysisWorkspace";
import FieldVisitForm from "./pages/FieldVisitForm";
import CreditManagerDecision from "./pages/CreditManagerDecision";
import SanctioningDecision from "./pages/SanctioningDecision";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/auth/login" element={<LoginPage />} />
            <Route path="/borrower" element={<BorrowerDashboard />} />
            <Route path="/borrower/pre-qual" element={<PreQualForm />} />
            <Route path="/borrower/apply" element={<DocumentUpload />} />
            <Route path="/borrower/applications" element={<BorrowerDashboard />} />
            <Route path="/borrower/notifications" element={<BorrowerDashboard />} />
            <Route path="/borrower/profile" element={<BorrowerDashboard />} />
            <Route path="/rm" element={<RMDashboard />} />
            <Route path="/rm/:appId" element={<RMApplicationReview />} />
            <Route path="/analyst/:appId" element={<AnalysisWorkspace />} />
            <Route path="/analyst/:appId/field-visit" element={<FieldVisitForm />} />
            <Route path="/credit-manager/:appId" element={<CreditManagerDecision />} />
            <Route path="/sanctioning/:appId" element={<SanctioningDecision />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
