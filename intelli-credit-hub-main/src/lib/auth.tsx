/**
 * INTELLI-CREDIT Consolidated Auth Context
 * Single source of truth: demo login, role routing, token management.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { setAuthToken } from "./api";

export type UserRole = "borrower" | "rm" | "analyst" | "credit-manager" | "sanctioning";

export interface AuthUser {
  uid: string;
  email: string;
  displayName: string;
  role: UserRole;
  token: string;
}

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  isLoggedIn: boolean;
  role: UserRole;
  userName: string;
  login: (role: string, email?: string) => void;
  loginWithRole: (role: UserRole) => void;
  logout: () => void;
}

const ROLE_LABELS: Record<string, string> = {
  borrower: "Borrower",
  rm: "Relationship Manager",
  analyst: "Credit Analyst",
  "credit-manager": "Credit Manager",
  sanctioning: "Sanctioning Authority",
};

const DEMO_USERS: Record<string, AuthUser> = {
  borrower: { uid: "demo-borrower", email: "borrower@intellicredit.ai", displayName: "Acme Corp", role: "borrower", token: "demo-token-borrower" },
  rm: { uid: "demo-rm", email: "rm@intellicredit.ai", displayName: "Sarah Jenkins", role: "rm", token: "demo-token-rm" },
  analyst: { uid: "demo-analyst", email: "analyst@intellicredit.ai", displayName: "Dr. Patel", role: "analyst", token: "demo-token-analyst" },
  "credit-manager": { uid: "demo-cm", email: "cm@intellicredit.ai", displayName: "VP Credit", role: "credit-manager", token: "demo-token-cm" },
  sanctioning: { uid: "demo-sa", email: "sa@intellicredit.ai", displayName: "CGM Office", role: "sanctioning", token: "demo-token-sa" },
};

export const ROLE_ROUTES: Record<string, string> = {
  borrower: "/borrower",
  rm: "/rm",
  analyst: "/analyst/demo-app-001",
  "credit-manager": "/credit-manager/demo-app-001",
  sanctioning: "/sanctioning/demo-app-001",
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem("ic_user");
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as AuthUser;
        setUser(parsed);
        setAuthToken(parsed.token);
      } catch { /* ignore parse errors */ }
    }
    setLoading(false);
  }, []);

  const login = useCallback((role: string, email?: string) => {
    const demoUser = DEMO_USERS[role] || DEMO_USERS.borrower;
    const finalUser: AuthUser = email
      ? { ...demoUser, displayName: email.split("@")[0], email }
      : demoUser;
    setUser(finalUser);
    setAuthToken(finalUser.token);
    localStorage.setItem("ic_user", JSON.stringify(finalUser));
  }, []);

  const loginWithRole = useCallback((role: UserRole) => {
    const demoUser = DEMO_USERS[role] || DEMO_USERS.borrower;
    setUser(demoUser);
    setAuthToken(demoUser.token);
    localStorage.setItem("ic_user", JSON.stringify(demoUser));
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setAuthToken(null);
    localStorage.removeItem("ic_user");
  }, []);

  const value: AuthContextType = {
    user,
    loading,
    isLoggedIn: !!user,
    role: (user?.role || "borrower") as UserRole,
    userName: user?.displayName || "User",
    login,
    loginWithRole,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function getRoleLabel(role: string) {
  return ROLE_LABELS[role] || role;
}

export { DEMO_USERS };
