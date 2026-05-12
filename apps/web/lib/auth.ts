/**
 * Auth token management utilities
 * 
 * Note: Tokens are stored in localStorage for this private local app.
 * Tradeoff: localStorage is vulnerable to XSS but acceptable for local-first app
 * in private network. For production, consider more secure storage.
 */

const TOKEN_KEY = "auth_token";
const USER_ID_KEY = "user_id";

export interface AuthToken {
  access_token: string;
  token_type?: string;
}

export interface AuthUser {
  user_id: string;
}

export function setToken(token: AuthToken): void {
  if (typeof window !== "undefined") {
    localStorage.setItem(TOKEN_KEY, token.access_token);
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_ID_KEY);
  }
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

export function setUserId(userId: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem(USER_ID_KEY, userId);
  }
}

export function getUserId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USER_ID_KEY);
}

