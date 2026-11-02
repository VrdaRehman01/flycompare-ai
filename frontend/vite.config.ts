/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API calls through the dev server so the browser always sees a
// same-origin request. Without this, opening the app on 127.0.0.1 or a LAN
// address (host: "0.0.0.0" allows both) fails CORS against the backend.
const apiTarget = process.env.FLYCOMPARE_API_TARGET ?? "http://127.0.0.1:8000";
const proxy = {
  "/api": { target: apiTarget, changeOrigin: true },
  "/health": { target: apiTarget, changeOrigin: true },
};

export default defineConfig({
  plugins: [react()],
  build: {
    // MapLibre (~1 MB) is lazy-loaded only on pages that show a map.
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        // Keep the charting library in its own cacheable chunk.
        manualChunks: { charts: ["recharts"], vendor: ["react", "react-dom", "lucide-react"] },
      },
    },
  },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
  server: { port: 5173, host: "0.0.0.0", proxy },
  preview: { port: 4173, host: "0.0.0.0", proxy },
});
