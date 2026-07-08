import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { AuthPage } from "./components/AuthPage";
import { ContextInspector } from "./components/ContextInspector";
import { Header } from "./components/Header";
import { PreferencesModal } from "./components/PreferencesModal";
import { ProfileModal } from "./components/ProfileModal";
import { AppUIProvider, useAppUI } from "./context/AppUIContext";
import { useAuth } from "./hooks/useAuth";
import { useTheme } from "./hooks/useTheme";
import { AppLayout } from "./layouts/AppLayout";
import { ChatLayout } from "./layouts/ChatLayout";
import { AutoCreateChatSession } from "./pages/AutoCreateChatSession";
import { BibliotecaPage } from "./pages/BibliotecaPage";
import { ChatPage } from "./pages/ChatPage";
import { ConsumoPage } from "./pages/ConsumoPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ResumosPage } from "./pages/ResumosPage";
import { SummaryDetailPage } from "./pages/SummaryDetailPage";

export default function App() {
  const { theme, toggleTheme, colorStart, colorEnd, setColorStart, setColorEnd } = useTheme();
  const auth = useAuth();

  if (auth.isLoading) {
    return (
      <div className="app">
        <div className="window">
          <Header theme={theme} onToggleTheme={toggleTheme} />
          <main className="content is-empty">
            <div className="welcome">
              <div className="orb" />
              <h1 className="greeting-title">Carregando...</h1>
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (!auth.isAuthenticated || !auth.user) {
    return (
      <AuthPage
        theme={theme}
        onToggleTheme={toggleTheme}
        isLoading={auth.isLoading}
        error={auth.error}
        onSignIn={auth.login}
        onSignUp={auth.register}
      />
    );
  }

  const layoutProps = {
    theme,
    onToggleTheme: toggleTheme,
    isAuthenticated: auth.isAuthenticated,
    userLabel: auth.user.username,
    onLogout: auth.logout,
  };

  return (
    <AppUIProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout {...layoutProps} />}>
            <Route index element={<Navigate to="/inicio" replace />} />
            <Route
              path="/inicio"
              element={
                <DashboardPage
                  username={auth.user.username}
                  isAuthenticated={auth.isAuthenticated}
                />
              }
            />
            <Route
              path="/biblioteca"
              element={<BibliotecaPage isAuthenticated={auth.isAuthenticated} />}
            />
            <Route path="/resumos" element={<ResumosPage />} />
            <Route path="/resumos/:summaryId" element={<SummaryDetailPage />} />
            <Route path="/consumo" element={<ConsumoPage />} />
          </Route>

          <Route element={<ChatLayout {...layoutProps} />}>
            <Route
              path="/chat"
              element={<AutoCreateChatSession isAuthenticated={auth.isAuthenticated} />}
            />
            <Route path="/chat/:sessionId" element={<ChatPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/inicio" replace />} />
        </Routes>

        <GlobalModals
          user={auth.user}
          onUserUpdated={auth.setUser}
          colorStart={colorStart}
          colorEnd={colorEnd}
          setColorStart={setColorStart}
          setColorEnd={setColorEnd}
        />
      </BrowserRouter>
    </AppUIProvider>
  );
}

interface ModalsProps {
  user: NonNullable<ReturnType<typeof useAuth>["user"]>;
  onUserUpdated: ReturnType<typeof useAuth>["setUser"];
  colorStart: string;
  colorEnd: string;
  setColorStart: (v: string) => void;
  setColorEnd: (v: string) => void;
}

/** Modais globais montados uma vez, controlados pelo AppUIContext. O ContextInspector
 * só existe quando estamos numa rota /chat/:sessionId — lê do URL. */
function GlobalModals({
  user,
  onUserUpdated,
  colorStart,
  colorEnd,
  setColorStart,
  setColorEnd,
}: ModalsProps) {
  const ui = useAppUI();
  return (
    <>
      <PreferencesModal
        isOpen={ui.preferencesOpen}
        onClose={ui.closePreferences}
        colorStart={colorStart}
        colorEnd={colorEnd}
        setColorStart={setColorStart}
        setColorEnd={setColorEnd}
      />
      <ProfileModal
        isOpen={ui.profileOpen}
        user={user}
        onClose={ui.closeProfile}
        onUpdated={onUserUpdated}
      />
      <Routes>
        <Route path="/chat/:sessionId" element={<ContextInspectorGate />} />
      </Routes>
    </>
  );
}

function ContextInspectorGate() {
  const ui = useAppUI();
  const { sessionId } = useParams<{ sessionId: string }>();
  if (!ui.contextOpen || !sessionId) return null;
  return <ContextInspector sessionId={sessionId} onClose={ui.closeContext} />;
}
