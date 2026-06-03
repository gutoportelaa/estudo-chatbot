import { useEffect, useState } from "react";

export type Theme = "light" | "nocturne";

const STORAGE_KEY = "thinkai.theme";

/** Controla o tema (claro/nocturne), persistido em localStorage. */
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem(STORAGE_KEY) as Theme) ?? "light",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggle = () =>
    setTheme((t) => (t === "light" ? "nocturne" : "light"));

  return [theme, toggle];
}
