import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login, signup } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import { BrainCircuit } from "./icons_extra";

interface AuthProps {
  mode: "login" | "signup";
}

export const Auth: React.FC<AuthProps> = ({ mode }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setToken } = useAuth();
  const navigate = useNavigate();

  const isLogin = mode === "login";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (isLogin) {
        const token = await login(username, password);
        setToken(token);
        navigate("/chat");
      } else {
        await signup(username, password);
        const token = await login(username, password);
        setToken(token);
        navigate("/chat");
      }
    } catch (err: any) {
      setError(err.message || "Erro de autenticação");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-box">
        <div className="auth-header">
          <BrainCircuit className="auth-icon" />
          <h2>{isLogin ? "Welcome back" : "Create an account"}</h2>
          <p>{isLogin ? "Sign in to continue" : "Sign up to start chatting"}</p>
        </div>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label>Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              required
              autoComplete="username"
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
              autoComplete="current-password"
            />
          </div>
          
          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? "Please wait..." : (isLogin ? "Sign In" : "Sign Up")}
          </button>
        </form>

        <div className="auth-footer">
          {isLogin ? (
            <p>Don't have an account? <span onClick={() => navigate("/signup")}>Sign up</span></p>
          ) : (
            <p>Already have an account? <span onClick={() => navigate("/login")}>Sign in</span></p>
          )}
        </div>
      </div>
    </div>
  );
};
