import { useEffect, useState } from "react";

export type Theme = "light" | "nocturne";

const STORAGE_KEY = "thinkai.theme";
const COLOR_START_KEY = "thinkai.color.start";
const COLOR_END_KEY = "thinkai.color.end";

export const DEFAULT_COLOR_START = "#3a9c5c";
export const DEFAULT_COLOR_END = "#2f8f4e";

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem(STORAGE_KEY) as Theme) ?? "light",
  );

  const [colorStart, setColorStart] = useState<string>(
    () => localStorage.getItem(COLOR_START_KEY) ?? DEFAULT_COLOR_START
  );

  const [colorEnd, setColorEnd] = useState<string>(
    () => localStorage.getItem(COLOR_END_KEY) ?? DEFAULT_COLOR_END
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.style.setProperty("--theme-gradient-start", colorStart);
    localStorage.setItem(COLOR_START_KEY, colorStart);
  }, [colorStart]);

  useEffect(() => {
    document.documentElement.style.setProperty("--theme-gradient-end", colorEnd);
    localStorage.setItem(COLOR_END_KEY, colorEnd);
  }, [colorEnd]);

  const toggleTheme = () =>
    setTheme((t) => (t === "light" ? "nocturne" : "light"));

  return { theme, toggleTheme, colorStart, colorEnd, setColorStart, setColorEnd };
}
