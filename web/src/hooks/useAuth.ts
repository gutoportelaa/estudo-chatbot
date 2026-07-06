import { useCallback, useEffect, useState } from "react";
import { getAuthToken, getProfile, logout as clearAuth, signin, signup, type AuthUser } from "../api/client";

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function bootstrap() {
      const token = getAuthToken();
      if (!token) {
        if (active) setIsLoading(false);
        return;
      }
      try {
        const profile = await getProfile();
        if (active) { setUser(profile); setError(null); }
      } catch {
        clearAuth();
        if (active) setUser(null);
      } finally {
        if (active) setIsLoading(false);
      }
    }

    void bootstrap();
    return () => { active = false; };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await signin(username, password);
      const profile = await getProfile();
      setUser(profile);
      return profile;
    } catch (err) {
      clearAuth();
      setUser(null);
      setError(err instanceof Error ? err.message : "Falha ao autenticar");
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await signup(username, password);
      await signin(username, password);
      const profile = await getProfile();
      setUser(profile);
      return profile;
    } catch (err) {
      clearAuth();
      setUser(null);
      setError(err instanceof Error ? err.message : "Falha ao cadastrar");
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
    setError(null);
  }, []);

  return { user, setUser, isLoading, error, isAuthenticated: Boolean(user), login, register, logout };
}

export type AuthState = ReturnType<typeof useAuth>;
