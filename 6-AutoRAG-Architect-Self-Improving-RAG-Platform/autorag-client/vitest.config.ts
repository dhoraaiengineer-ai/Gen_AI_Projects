import { resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "./"),
      "react": resolve(__dirname, "../node_modules/react"),
      "react-dom": resolve(__dirname, "../node_modules/react-dom"),
      "react/jsx-runtime": resolve(__dirname, "../node_modules/react/jsx-runtime"),
      "react/jsx-dev-runtime": resolve(__dirname, "../node_modules/react/jsx-dev-runtime"),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    // Use the forks pool (isolated child processes) instead of the default
    // threads pool: jsdom's shared globals race across worker_threads on
    // Windows, causing "failed to find the current suite" hook errors.
    pool: "forks",
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules", ".next", "e2e"],
    css: false,
  },
});
