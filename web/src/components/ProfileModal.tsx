/**
 * ProfileModal — edição de perfil do usuário (B2/#40).
 * Nome, email, descrição e avatar (upload). Reusa o padrão de modal existente.
 */

import { useEffect, useRef, useState } from "react";
import {
  fetchAvatarUrl,
  updateProfile,
  uploadAvatar,
  type AuthUser,
} from "../api/client";

interface Props {
  isOpen: boolean;
  user: AuthUser;
  onClose: () => void;
  onUpdated: (user: AuthUser) => void;
}

export function ProfileModal({ isOpen, user, onClose, onUpdated }: Props) {
  const [fullName, setFullName] = useState(user.full_name ?? "");
  const [email, setEmail] = useState(user.email ?? "");
  const [description, setDescription] = useState(user.description ?? "");
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    setFullName(user.full_name ?? "");
    setEmail(user.email ?? "");
    setDescription(user.description ?? "");
    setError(null);
  }, [isOpen, user]);

  // Carrega o avatar atual (autenticado) como object URL.
  useEffect(() => {
    if (!isOpen || !user.has_avatar) {
      setAvatarUrl(null);
      return;
    }
    let url: string | null = null;
    let active = true;
    fetchAvatarUrl()
      .then((u) => {
        if (active) {
          url = u;
          setAvatarUrl(u);
        } else {
          URL.revokeObjectURL(u);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [isOpen, user.has_avatar]);

  if (!isOpen) return null;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateProfile({
        full_name: fullName.trim() || null,
        email: email.trim() || null,
        description: description.trim() || null,
      });
      onUpdated(updated);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar o perfil");
    } finally {
      setSaving(false);
    }
  };

  const onPickAvatar = async (file: File) => {
    setError(null);
    try {
      const updated = await uploadAvatar(file);
      onUpdated(updated);
      const u = await fetchAvatarUrl().catch(() => null);
      if (u) setAvatarUrl(u);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao enviar o avatar");
    }
  };

  const initials = (user.full_name || user.username).slice(0, 2).toUpperCase();

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Perfil</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Fechar" title="Fechar">
            ✕
          </button>
        </div>
        <div className="modal-body">
          <div className="profile-avatar-row">
            <div className="profile-avatar">
              {avatarUrl ? (
                <img src={avatarUrl} alt="Avatar" />
              ) : (
                <span className="profile-avatar-initials">{initials}</span>
              )}
            </div>
            <div>
              <button className="btn-ghost" onClick={() => fileRef.current?.click()}>
                Trocar avatar
              </button>
              <p className="profile-hint">PNG, JPEG ou WEBP · até 2 MB</p>
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                hidden
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void onPickAvatar(f);
                  e.target.value = "";
                }}
              />
            </div>
          </div>

          <label className="auth-field">
            <span>Usuário</span>
            <input value={user.username} disabled />
          </label>
          <label className="auth-field">
            <span>Nome</span>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Seu nome" />
          </label>
          <label className="auth-field">
            <span>Email</span>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              placeholder="voce@exemplo.com"
            />
          </label>
          <label className="auth-field">
            <span>Descrição</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Áreas de interesse, objetivo de estudo…"
            />
          </label>

          {error ? <p className="auth-error">{error}</p> : null}

          <button className="auth-submit" onClick={() => void save()} disabled={saving}>
            {saving ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}
