/**
 * INTELLI-CREDIT Consolidated Auth Context
 * Supports Firebase sign-in/sign-up + demo mode fallback.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  updateProfile,
  User as FirebaseUser,
} from "firebase/auth";
import { firebaseAuth } from "./firebase";
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
  firebaseLogin: (email: string, password: string, role: UserRole) => Promise<void>;
  firebaseSignup: (email: string, password: string, role: UserRole) => Promise<void>;
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

/** Convert Firebase user + selected role → AuthUser */
async function firebaseUserToAuth(fbUser: FirebaseUser, role: UserRole): Promise<AuthUser> {
  const token = await fbUser.getIdToken();
  return {
    uid: fbUser.uid,
    email: fbUser.email || "",
    displayName: fbUser.displayName || fbUser.email?.split("@")[0] || "User",
    role,
    token,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore from localStorage on mount + listen for Firebase auth state
  useEffect(() => {
    const stored = localStorage.getItem("ic_user");
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as AuthUser;
        setUser(parsed);
        setAuthToken(parsed.token);
      } catch { /* ignore */ }
    }

    // Firebase auth state listener (refreshes token)
    const unsubscribe = onAuthStateChanged(firebaseAuth, async (fbUser) => {
      if (fbUser) {
        const storedRole = localStorage.getItem("ic_role") as UserRole || "borrower";
        const authUser = await firebaseUserToAuth(fbUser, storedRole);
        setUser(authUser);
        setAuthToken(authUser.token);
        localStorage.setItem("ic_user", JSON.stringify(authUser));
      }
      setLoading(false);
    });

    // If Firebase doesn't fire (no config), stop loading after timeout
    const timeout = setTimeout(() => setLoading(false), 2000);
    return () => { unsubscribe(); clearTimeout(timeout); };
  }, []);

  // Demo login (no Firebase)
  const login = useCallback((role: string, email?: string) => {
    const demoUser = DEMO_USERS[role] || DEMO_USERS.borrower;
    const finalUser: AuthUser = email
      ? { ...demoUser, displayName: email.split("@")[0], email }
      : demoUser;
    setUser(finalUser);
    setAuthToken(finalUser.token);
    localStorage.setItem("ic_user", JSON.stringify(finalUser));
    localStorage.setItem("ic_role", role);
  }, []);

  const loginWithRole = useCallback((role: UserRole) => {
    const demoUser = DEMO_USERS[role] || DEMO_USERS.borrower;
    setUser(demoUser);
    setAuthToken(demoUser.token);
    localStorage.setItem("ic_user", JSON.stringify(demoUser));
    localStorage.setItem("ic_role", role);
  }, []);

  // Firebase sign-in
  const firebaseLogin = useCallback(async (email: string, password: string, role: UserRole) => {
    const cred = await signInWithEmailAndPassword(firebaseAuth, email, password);
    localStorage.setItem("ic_role", role);
    const authUser = await firebaseUserToAuth(cred.user, role);
    setUser(authUser);
    setAuthToken(authUser.token);
    localStorage.setItem("ic_user", JSON.stringify(authUser));
  }, []);

  // Firebase sign-up (creates account + sets role)
  const firebaseSignup = useCallback(async (email: string, password: string, role: UserRole) => {
    const cred = await createUserWithEmailAndPassword(firebaseAuth, email, password);
    await updateProfile(cred.user, { displayName: email.split("@")[0] });
    localStorage.setItem("ic_role", role);
    const authUser = await firebaseUserToAuth(cred.user, role);
    setUser(authUser);
    setAuthToken(authUser.token);
    localStorage.setItem("ic_user", JSON.stringify(authUser));
  }, []);

  const logout = useCallback(async () => {
    try { await signOut(firebaseAuth); } catch { /* ignore */ }
    setUser(null);
    setAuthToken(null);
    localStorage.removeItem("ic_user");
    localStorage.removeItem("ic_role");
  }, []);

  const value: AuthContextType = {
    user,
    loading,
    isLoggedIn: !!user,
    role: (user?.role || "borrower") as UserRole,
    userName: user?.displayName || "User",
    login,
    loginWithRole,
    firebaseLogin,
    firebaseSignup,
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
