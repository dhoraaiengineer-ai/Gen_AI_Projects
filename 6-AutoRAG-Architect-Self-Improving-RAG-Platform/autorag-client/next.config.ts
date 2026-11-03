import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  webpack: (config) => {
    // react-pdf/pdfjs-dist optionally pull in the Node-only `canvas` and
    // `encoding` packages (used for server-side PDF rendering, not needed in
    // the browser). Without aliasing them out, webpack tries to bundle them
    // for the client and pdf.mjs's module init crashes with
    // "Object.defineProperty called on non-object" -- documented react-pdf
    // Next.js setup requirement, not a version issue.
    config.resolve.alias.canvas = false;
    config.resolve.alias.encoding = false;
    return config;
  },
};

export default nextConfig;