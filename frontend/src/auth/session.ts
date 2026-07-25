const SESSION_STORAGE_KEY = "mergegate.session-token";

export function getSessionToken(): string | null {
  return window.sessionStorage.getItem(SESSION_STORAGE_KEY);
}

export function setSessionToken(token: string): void {
  window.sessionStorage.setItem(SESSION_STORAGE_KEY, token);
}

export function clearSessionToken(): void {
  window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
}

export function consumeOAuthCallback(): boolean {
  if (window.location.pathname !== "/auth/callback") return false;
  const token = new URLSearchParams(window.location.hash.slice(1)).get("session");
  if (!token) return false;
  setSessionToken(token);
  window.history.replaceState({}, "", "/");
  return true;
}
