/**
 * Auth Hook — manages demo login state, role, and token
 */
import { useState, useCallback, createContext, useContext, ReactNode } from "react";
import { setAuthToken } from "@/lib/api";

interface AuthState {
    isLoggedIn: boolean;
    role: string;
    userName: string;
    uid: string;
    token: string | null;
}

interface AuthContextValue extends AuthState {
    login: (role: string, email?: string) => void;
    logout: () => void;
}

const ROLE_NAMES: Record<string, string> = {
    borrower: "Acme Corp",
    rm: "Sarah Jenkins",
    analyst: "Dr. Patel",
    "credit-manager": "VP Credit",
    sanctioning: "CGM Office",
};

const ROLE_LABELS: Record<string, string> = {
    borrower: "Borrower",
    rm: "Relationship Manager",
    analyst: "Credit Analyst",
    "credit-manager": "Credit Manager",
    sanctioning: "Sanctioning Authority",
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<AuthState>(() => {
        const saved = sessionStorage.getItem("ic-auth");
        if (saved) {
            const parsed = JSON.parse(saved);
            if (parsed.token) setAuthToken(parsed.token);
            return parsed;
        }
        return { isLoggedIn: false, role: "borrower", userName: "User", uid: "", token: null };
    });

    const login = useCallback((role: string, email?: string) => {
        // Demo mode: generate a fake token
        const demoToken = `demo-${role}-${Date.now()}`;
        const newState: AuthState = {
            isLoggedIn: true,
            role,
            userName: email ? email.split("@")[0] : ROLE_NAMES[role] || "User",
            uid: `demo-uid-${role}`,
            token: demoToken,
        };
        setAuthToken(demoToken);
        sessionStorage.setItem("ic-auth", JSON.stringify(newState));
        setState(newState);
    }, []);

    const logout = useCallback(() => {
        setAuthToken(null);
        sessionStorage.removeItem("ic-auth");
        setState({ isLoggedIn: false, role: "borrower", userName: "User", uid: "", token: null });
    }, []);

    return (
        <AuthContext.Provider value= {{ ...state, login, logout }
}>
    { children }
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
