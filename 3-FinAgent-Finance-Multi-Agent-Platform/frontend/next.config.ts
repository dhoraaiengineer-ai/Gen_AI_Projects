import path from "node:path";

import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// One shared .env at the repo root (ADR-028). Only browser-safe values are exposed below:
// the Supabase URL, the *publishable* key and the API URL. Secrets never reach the client.
// forceReload: Next has already loaded (and cached) frontend/'s env by now; without it this call is
// a silent no-op and the browser bundle ships without the Supabase settings.
loadEnvConfig(path.resolve(__dirname, ".."), process.env.NODE_ENV !== "production", undefined, true);

const nextConfig: NextConfig = {
  // Docker image only (NEXT_OUTPUT=standalone): self-contained server.js, no node_modules copy.
  // Local `next start` keeps the default output.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  // cacheComponents / partialPrefetching break a client-side sign-in gate (CLAUDE.md pitfall).
  cacheComponents: false,
  partialPrefetching: false,
  env: {
    NEXT_PUBLIC_SUPABASE_URL: process.env.SUPABASE_URL ?? "",
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env.SUPABASE_PUBLISHABLE_KEY ?? "",
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? `http://127.0.0.1:${process.env.API_PORT ?? "8020"}`,
    // proxy (default) | direct | mock — see lib/config.ts
    NEXT_PUBLIC_API_MODE: process.env.NEXT_PUBLIC_API_MODE ?? "proxy",
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
