"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { onAuthExpired, setApiToken } from "@/lib/api/client";
import { apiFetch } from "@/lib/api/client";

/**
 * 登录态上下文（P4）。
 * 凭证策略（refactor-plan P4 风险项既定）：Bearer token 存 localStorage，
 * 每次请求经 Authorization 头携带；登录成功即轮换 token（后端行为）。
 * 仅浏览器端注入凭证，RSC/SSR 不受登录态影响（SEO 分离）。
 */

interface AuthUser {
  email: string;
}

interface AuthContextValue {
  /** undefined = 尚未完成挂载检查；null = 未登录 */
  user: AuthUser | null | undefined;
  login: (token: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: undefined,
  login: async () => {},
  logout: () => {},
});

const TOKEN_KEY = "govps_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null | undefined>(undefined);

  const logout = useCallback(() => {
    setApiToken(null);
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* storage 不可用时忽略 */
    }
    setUser(null);
  }, []);

  const fetchMe = useCallback(async (token: string) => {
    setApiToken(token);
    try {
      const me = await apiFetch<{ email: string }>("/api/auth/me");
      setUser({ email: me.email });
    } catch {
      // token 失效：onAuthExpired 已清存储，这里兜底复位
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
    if (stored) void fetchMe(stored);
    else setUser(null);

    return onAuthExpired(() => setUser(null));
  }, [fetchMe]);

  const login = useCallback(
    async (token: string) => {
      try {
        localStorage.setItem(TOKEN_KEY, token);
      } catch {
        /* ignore */
      }
      await fetchMe(token);
    },
    [fetchMe],
  );

  const value = useMemo(() => ({ user, login, logout }), [user, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
