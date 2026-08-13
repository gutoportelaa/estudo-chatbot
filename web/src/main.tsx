import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/theme.css";
import "./styles/app.css";

// Modo demo (GitHub Pages): intercepta a API e mostra o aviso de vitrine.
// `VITE_DEMO` só é definido no build do Pages; em produção nada disso entra no
// bundle (os imports são dinâmicos e ficam atrás da flag).
const isDemo = import.meta.env.VITE_DEMO === "1";

async function bootstrap(): Promise<ReactNode> {
  if (!isDemo) return null;
  const [{ installDemoApi }, { DemoBanner }] = await Promise.all([
    import("./demo/mockApi"),
    import("./demo/DemoBanner"),
  ]);
  installDemoApi();
  return <DemoBanner />;
}

void bootstrap().then((banner) => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
      {banner}
    </StrictMode>,
  );
});
