// Flat ESLint config (ESLint 9 + Next.js 16).
// `next lint` was removed in Next 16 and the legacy .eslintrc.json is not
// compatible with eslint-config-next@16's flat config — so the lint entrypoint
// is `eslint .` against this file. Rules preserve the team's prior standards.
//
// eslint-config-next still ships its shareable configs in legacy eslintrc
// shape (an `extends` object, not a flat-config array) — bridge it with
// FlatCompat, per Next.js's own flat-config migration guide.

import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FlatCompat } from "@eslint/eslintrc";

const __dirname = dirname(fileURLToPath(import.meta.url));
const compat = new FlatCompat({ baseDirectory: __dirname });

// "next/typescript" is what actually registers the @typescript-eslint
// plugin (via plugin:@typescript-eslint/recommended) — core-web-vitals
// alone only wires up react/react-hooks/@next/next.
const nextConfigs = compat.extends("next/core-web-vitals", "next/typescript");

const config = [
  {
    ignores: ["node_modules/**", ".next/**", "e2e/**", "next-env.d.ts"],
  },
  ...nextConfigs,
  {
    // Scope to TS/TSX — @typescript-eslint rules only apply there.
    files: ["**/*.ts", "**/*.tsx"],
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/consistent-type-imports": ["warn", { prefer: "type-imports" }],
      "no-console": ["warn", { allow: ["warn", "error"] }],
      "prefer-const": "error",
      "no-var": "error",
    },
  },
];

export default config;
