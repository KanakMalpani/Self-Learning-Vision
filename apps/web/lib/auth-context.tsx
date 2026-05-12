"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { getToken, clearToken, isAuthenticated as checkAuth } from "./auth";

const AUTH_ENABLED = process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  markAuthenticated: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  isAuthenticated: false,
  isLoading: true,
  markAuthenticated: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(!AUTH_ENABLED);
  const [isLoading, setIsLoading] = useState(true);

  // Check auth state on mount (hydrate from localStorage)
  useEffect(() => {
    if (!AUTH_ENABLED) {
      setIsAuthenticated(true);
      setIsLoading(false);
      return;
    }

    setIsAuthenticated(checkAuth());
    setIsLoading(false);

    const onStorage = () => {
      setIsAuthenticated(checkAuth());
    };

    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const markAuthenticated = () => {
    if (!AUTH_ENABLED) {
      setIsAuthenticated(true);
      return;
    }
    setIsAuthenticated(true);
  };

  const logout = () => {
    if (!AUTH_ENABLED) {
      setIsAuthenticated(true);
      return;
    }
    clearToken();
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, markAuthenticated, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

