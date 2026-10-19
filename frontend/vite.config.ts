import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API calls through the dev server so the browser always sees a
// same-origin request. Without this, opening the app on 127.0.0.1 or a LAN
// address (host: "0.0.0.0" allows both) fails CORS against the backend.
const proxy = {
  "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
  "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
};

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, host: "0.0.0.0", proxy },
  preview: { port: 4173, host: "0.0.0.0", proxy },
});
