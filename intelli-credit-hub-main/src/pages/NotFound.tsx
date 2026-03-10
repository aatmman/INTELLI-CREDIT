import { useNavigate } from "react-router-dom";

export default function NotFound() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-8">
      <div className="text-center max-w-sm">
        <div
          className="font-display mb-4 select-none"
          style={{ fontSize: "6rem", lineHeight: 1, letterSpacing: "-0.06em" }}
        >
          404
        </div>
        <p className="section-label mb-2">Page Not Found</p>
        <p className="text-sm text-muted-foreground mb-6" style={{ letterSpacing: "-0.01em" }}>
          The page you're looking for doesn't exist or has been moved.
        </p>
        <button className="btn-primary" onClick={() => navigate("/auth/login")}>
          Back to Login
        </button>
      </div>
    </div>
  );
}
