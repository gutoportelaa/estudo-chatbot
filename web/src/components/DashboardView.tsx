import { BookIcon, ChartIcon, SettingsIcon } from "./icons";

interface Props {
  username: string;
  onGoUpload: () => void;
  onGoBiblioteca: () => void;
  onOpenSummaries: () => void;
  onOpenProfile: () => void;
}

/**
 * Dashboard pós-login (EPIC E): ponto de entrada com atalhos para upload,
 * listagem de documentos, resumos (individual/consolidado) e edição de perfil.
 */
export function DashboardView({
  username,
  onGoUpload,
  onGoBiblioteca,
  onOpenSummaries,
  onOpenProfile,
}: Props) {
  return (
    <section className="dashboard">
      <header className="biblioteca-header">
        <div>
          <h2>Olá, {username}</h2>
          <p className="biblioteca-sub">O que você quer fazer agora?</p>
        </div>
      </header>

      <div className="dashboard-grid">
        <button type="button" className="dashboard-card" onClick={onGoUpload}>
          <BookIcon />
          <span className="dashboard-card-title">Enviar documento</span>
          <p className="dashboard-card-desc">Adicione um PDF à sua biblioteca.</p>
        </button>

        <button type="button" className="dashboard-card" onClick={onGoBiblioteca}>
          <BookIcon />
          <span className="dashboard-card-title">Meus documentos</span>
          <p className="dashboard-card-desc">Veja, selecione e organize sua biblioteca.</p>
        </button>

        <button type="button" className="dashboard-card" onClick={onOpenSummaries}>
          <ChartIcon />
          <span className="dashboard-card-title">Resumos</span>
          <p className="dashboard-card-desc">
            Veja resumos individuais e consolidados já gerados.
          </p>
        </button>

        <button type="button" className="dashboard-card" onClick={onOpenProfile}>
          <SettingsIcon />
          <span className="dashboard-card-title">Editar perfil</span>
          <p className="dashboard-card-desc">Altere seu usuário ou senha.</p>
        </button>
      </div>
    </section>
  );
}
