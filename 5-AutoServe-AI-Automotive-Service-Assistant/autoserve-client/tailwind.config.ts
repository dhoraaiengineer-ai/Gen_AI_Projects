import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      minHeight: { tap: "48px" },
      minWidth: { tap: "48px" },
    },
  },
  plugins: [],
} satisfies Config;
