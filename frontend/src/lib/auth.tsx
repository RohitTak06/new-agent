import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, ApiError, errorFrom, getToken, send, setToken, setUnauthorizedHandler } from "./api";
import type { User } from "./types";

interface AuthValue {
  user: User | null;
  ready: boolean;
  /** A token exists but the server couldn't be reached to check it, so we don't know who this is yet. */
  unreachable: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

/**
 * Holds who is logged in. The token lives in localStorage, which is fine for this demo; a
 * production app would use an httpOnly cookie. Hiding screens here is only convenience:
 * the server checks the role on every request.
 */
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [unreachable, setUnreachable] = useState(false);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      return;
    }
    try {
      setUser(await api<User>("/crm/auth/me"));
      setUnreachable(false);
    } catch (err) {
      const offline = err instanceof ApiError && err.status === 0;
      setUnreachable(offline);
      if (!offline) setUser(null);
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    void refresh().finally(() => setReady(true));
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await send("/crm/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: email, password }),
    });
    if (!res.ok) throw await errorFrom(res);
    const { access_token } = (await res.json()) as { access_token: string };
    setToken(access_token);
    const me = await api<User>("/crm/auth/me");
    setUser(me);
    return me;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setUnreachable(false);
  }, []);

  const value = useMemo(() => ({ user, ready, unreachable, login, logout, refresh }),
    [user, ready, unreachable, login, logout, refresh]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

/** The screen a role lands on after login. */
export function homeFor(user: User | null): string {
  return user && user.role !== "student" ? "/pipeline" : "/chat";
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
