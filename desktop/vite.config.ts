import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// @ts-expect-error type error without @types/node package
import process from "node:process";
const host = process.env.TAURI_DEV_HOST;

// https://vite.dev/config/
export default defineConfig(() => ({
  plugins: [react()],

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    // The standalone browser dev server is local-only. Tauri may set an
    // explicit host when remote HMR is needed for its own dev workflow.
    host: host || "127.0.0.1",
    // Browser development uses the same authenticated local Core as the
    // installed app. Keep API credentials in the app; this only forwards the
    // request to the loopback server.
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8766",
        changeOrigin: false,
      },
    },
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      // 3. tell Vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },
  },
}));
