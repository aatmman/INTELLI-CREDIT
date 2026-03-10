import { ReactNode, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import {
  LayoutDashboard, FileText, Upload, Bell, User, LogOut,
  BarChart3, Search, ChevronRight, Settings, Activity
} from "lucide-react";

interface NavItem { label: string; path: string; icon?: ReactNode; }

interface DashboardLayoutProps {
  children: ReactNode;
  role: string;
  roleLabel: string;
  navItems: NavItem[];
  userName?: string;
}

const ROLE_ICONS: Record<string, string> = {
  borrower: "BO",
  rm: "RM",
  analyst: "AN",
  "credit-manager": "CM",
  sanctioning: "SA",
};

const ROLE_COLORS: Record<string, string> = {
  borrower: "hsl(0 0% 20%)",
  rm: "hsl(0 0% 15%)",
  analyst: "hsl(0 0% 10%)",
  "credit-manager": "hsl(0 0% 8%)",
  sanctioning: "hsl(0 0% 4%)",
};

export function DashboardLayout({ children, role, roleLabel, navItems, userName }: DashboardLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout } = useAuth();
  const [notifOpen, setNotifOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/auth/login");
  };

  const abbr = ROLE_ICONS[role] || "US";

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* ── Top Navigation Bar ── */}
      <nav className="top-nav">
        <div className="max-w-[1440px] mx-auto px-6 h-full flex items-center justify-between gap-6">
          {/* Left: Wordmark + breadcrumb */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate("/" + role)}
              className="flex items-center gap-2.5 group"
            >
              <div className="w-7 h-7 rounded-[3px] bg-foreground flex items-center justify-center flex-shrink-0">
                <span className="text-background font-mono text-[9px] font-bold tracking-wider">IC</span>
              </div>
              <span
                className="hidden sm:block text-foreground text-sm font-bold"
                style={{ fontFamily: "'Syne', sans-serif", letterSpacing: "-0.03em" }}
              >
                Intelli-Credit
              </span>
            </button>

            <span className="text-border select-none">/</span>

            <div className="hidden md:flex items-center gap-1">
              <span
                className="text-xs px-2 py-1 rounded-[3px] font-mono tracking-wider uppercase"
                style={{
                  background: ROLE_COLORS[role] || "hsl(var(--foreground))",
                  color: "hsl(var(--background))",
                  fontSize: "10px",
                  fontWeight: 500,
                  letterSpacing: "0.1em",
                }}
              >
                {roleLabel}
              </span>
            </div>
          </div>

          {/* Center: Nav items */}
          <div className="hidden md:flex items-center gap-1">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path || location.pathname.startsWith(item.path + "/");
              return (
                <button
                  key={item.label}
                  onClick={() => navigate(item.path)}
                  className={`px-4 py-2 rounded-[3px] text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  }`}
                  style={{ letterSpacing: "-0.01em" }}
                >
                  {item.label}
                </button>
              );
            })}
          </div>

          {/* Right: Actions */}
          <div className="flex items-center gap-2">
            {/* Search hint */}
            <button className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-[3px] border border-border text-muted-foreground hover:border-foreground/30 transition-colors text-sm">
              <Search className="w-3.5 h-3.5" />
              <span className="font-mono text-[11px]">Search</span>
              <kbd>⌘K</kbd>
            </button>

            {/* Notifications */}
            <button
              onClick={() => setNotifOpen(!notifOpen)}
              className="relative w-9 h-9 rounded-[3px] border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
            >
              <Bell className="w-4 h-4" />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-foreground" />
            </button>

            {/* User */}
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-3 py-1.5 rounded-[3px] border border-border text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
            >
              <div
                className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                style={{ background: "hsl(var(--foreground))", color: "hsl(var(--background))" }}
              >
                <span className="font-mono text-[8px] font-bold">{abbr}</span>
              </div>
              <span className="hidden sm:block text-sm font-medium" style={{ letterSpacing: "-0.01em" }}>
                {userName || "User"}
              </span>
              <LogOut className="w-3.5 h-3.5 hidden sm:block" />
            </button>
          </div>
        </div>
      </nav>

      {/* ── Page Content ── */}
      <main className="flex-1 max-w-[1440px] mx-auto w-full px-6 py-8 page-enter">
        {children}
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-border px-6 py-3">
        <div className="max-w-[1440px] mx-auto flex items-center justify-between">
          <p className="font-mono text-muted-foreground" style={{ fontSize: "10px", letterSpacing: "0.08em" }}>
            INTELLI-CREDIT v3.0 · IIT HYDERABAD · 2026
          </p>
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-foreground/20 animate-pulse" />
            <span className="font-mono text-muted-foreground" style={{ fontSize: "10px", letterSpacing: "0.06em" }}>
              SYSTEM OPERATIONAL
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
