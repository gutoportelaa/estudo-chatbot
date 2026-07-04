import { useState } from "react";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  username: string;
  onSave: (body: { username?: string; password?: string }) => Promise<unknown>;
}

/**
 * Edição mínima de perfil (EPIC E): trocar username e/ou senha. Sem os campos
 * ricos (nome, avatar, bio) do épico B1/B2, ainda não integrado a este branch.
 */
export function ProfileModal({ isOpen, onClose, username, onSave }: Props) {
  const [newUsername, setNewUsername] = useState(username);
  const [password, setPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  if (!isOpen) return null;

  const submit = async () => {
    setError(null);
    setSuccess(false);
    const body: { username?: string; password?: string } = {};
    if (newUsername.trim() && newUsername.trim() !== username) body.username = newUsername.trim();
    if (password) {
      if (password.length < 8) {
        setError("Senha deve ter ao menos 8 caracteres");
        return;
      }
      body.password = password;
    }
    if (!body.username && !body.password) {
      setError("Altere o usuário e/ou a senha antes de salvar");
      return;
    }
    setSaving(true);
    try {
      await onSave(body);
      setPassword("");
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar o perfil");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Editar perfil</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Fechar" title="Fechar">
            ✕
          </button>
        </div>
        <div className="modal-body">
          <label className="auth-field">
            <span>Usuário</span>
            <input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} />
          </label>
          <label className="auth-field">
            <span>Nova senha (opcional)</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Deixe em branco para manter a atual"
              autoComplete="new-password"
            />
          </label>

          {error ? <p className="auth-error">{error}</p> : null}
          {success ? <p className="prefs-desc">Perfil atualizado.</p> : null}

          <button className="btn-primary" onClick={() => void submit()} disabled={saving}>
            {saving ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}
