import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy /api to the backend so the frontend can use same-origin paths.
const API_TARGET = process.env.VITE_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
    },
  },
  preview: { host: true, port: 5173 },
  build: { outDir: "dist", sourcemap: false },
});
