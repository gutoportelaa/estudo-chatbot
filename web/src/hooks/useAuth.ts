import { useState } from "react";
import { signin, signup } from "../api/client";

const TOKEN_KEY = "thinkai.token";
const USERNAME_KEY = "thinkai.username";

export interface AuthState {
  token: string | null;
  username: string | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

export function useAuth(): AuthState {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [username, setUsername] = useState<string | null>(() => localStorage.getItem(USERNAME_KEY));

  const login = async (user: string, password: string) => {
    const t = await signin(user, password);
    localStorage.setItem(TOKEN_KEY, t);
    localStorage.setItem(USERNAME_KEY, user);
    setToken(t);
    setUsername(user);
  };

  const register = async (user: string, password: string) => {
    await signup(user, password);
    await login(user, password);
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
    localStorage.removeItem("thinkai.session_id");
    setToken(null);
    setUsername(null);
  };

  return { token, username, login, register, logout };
}
