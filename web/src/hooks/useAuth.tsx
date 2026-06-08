import React, { createContext, useContext, useEffect, useState } from "react";
import { getToken } from "../api/client";

interface AuthContextType {
  token: string | null;
  setToken: (token: string | null) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  setToken: () => {},
  logout: () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setTokenState] = useState<string | null>(getToken());

  const setToken = (newToken: string | null) => {
    if (newToken) {
      localStorage.setItem("thinkai.token", newToken);
    } else {
      localStorage.removeItem("thinkai.token");
    }
    setTokenState(newToken);
  };

  const logout = () => {
    setToken(null);
  };

  useEffect(() => {
    // Escuta mudanças de storage (caso logout em outra aba)
    const handleStorage = () => {
      setTokenState(getToken());
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  return (
    <AuthContext.Provider value={{ token, setToken, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
