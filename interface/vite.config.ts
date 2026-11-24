import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// npm run dev : l'API du noyau de développement (port 8800) ; ouvrir d'abord /fenetre/entree?j=<jeton> sur le noyau pour le cookie.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/api": "http://127.0.0.1:8800", "/fenetre": "http://127.0.0.1:8800" } },
  build: { outDir: "dist", assetsDir: "assets", chunkSizeWarningLimit: 2000 },
});
