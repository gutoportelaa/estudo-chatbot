import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `VITE_BASE` permite publicar num subcaminho (GitHub Pages serve o site em
// /<repo>/). Vazio por padrão, para não afetar o deploy normal na EC2.
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
  },
});
