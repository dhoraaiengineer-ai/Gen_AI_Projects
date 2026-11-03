import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./ui/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        /* ── Brand (warm stone/amber/orange, 26-Jul-2026 — supersedes the
           25-Jul-2026 blue/indigo reskin per explicit direction; page-by-page
           retheme starting with /dashboard. Same token roles, warm hues. ── */
        brand: "#F97316",       // AutoRAG Architect wordmark (Rule 25) — unchanged
        "brand-1": "#F59E0B",   // primary amber accent (was indigo)
        "brand-2": "#EA580C",   // secondary deep-orange accent (was purple)

        /* ── Stone/amber palette — full scale, structurally mirrors the
           retired earth-tone scale (5 families, 100-900 ramps) so every
           token below keeps the same role, just a different hue. Only
           light_bronze's DEFAULT/300/400 are exercised by any component
           today (dashboard hover-link accents) -- those three are retuned
           to warm hues; the remaining unused shades in this block keep
           their prior placeholder values until a page that uses them is
           reskinned. ── */
        tea_green:    { DEFAULT: "#c7d2fe", 100: "#1e1b4b", 200: "#312e81", 300: "#4338ca", 400: "#6366f1", 500: "#c7d2fe", 600: "#d9e0fe", 700: "#e5e9fe", 800: "#eef0ff", 900: "#f7f8ff" },
        beige:        { DEFAULT: "#e0e7ff", 100: "#1e1b4b", 200: "#3730a3", 300: "#4f46e5", 400: "#818cf8", 500: "#e0e7ff", 600: "#e8edfe", 700: "#f0f2ff", 800: "#f5f7ff", 900: "#fafbff" },
        cornsilk:     { DEFAULT: "#f8fafc", 100: "#0f172a", 200: "#1e293b", 300: "#475569", 400: "#94a3b8", 500: "#f8fafc", 600: "#f9fbfd", 700: "#fbfcfe", 800: "#fdfdfe", 900: "#ffffff" },
        papaya_whip:  { DEFAULT: "#eef2ff", 100: "#1e1b4b", 200: "#3730a3", 300: "#6366f1", 400: "#a5b4fc", 500: "#eef2ff", 600: "#f1f4ff", 700: "#f5f7ff", 800: "#f9faff", 900: "#fdfdff" },
        light_bronze: { DEFAULT: "#F59E0B", 100: "#1e1b4b", 200: "#312e81", 300: "#D97706", 400: "#C2410C", 500: "#818cf8", 600: "#a5b4fc", 700: "#c7d2fe", 800: "#e0e7ff", 900: "#eef0ff" },

        /* ── Sidebar surface (light, default) ── */
        sidebar: {
          0: "#F5F1EA",
          1: "#F5F1EA",
          2: "#FAF8F5",
        },

        /* ── Workspace surface (light, default) ── */
        ws: {
          0: "#FAF8F5",
          1: "#ffffff",
          2: "#F5F1EA",
          3: "#FDF3E7",
        },

        /* ── Text hierarchy ── */
        "text-1": "#1C1917",
        "text-2": "#44403C",
        "text-3": "#57534E",

        /* ── Status — kept independent of the brand palette (functional signals, Rule 25) ── */
        status: {
          success: "#10B981",
          warning: "#F59E0B",
          error:   "#EF4444",
          cyan:    "#06B6D4",
        },

        /* ── 9-agent colors (frontend_design.md SOT §11) — kept independent of the
           earth palette; earth hues (tea_green/beige) are too close in hue to stay
           distinguishable from each other if substituted here. ── */
        agent: {
          ingestion: "#06B6D4",
          rewriter:  "#7C3AED",
          builder:   "#06B6D4",
          compressor:"#3B82F6",
          evaluator: "#F59E0B",
          observer:  "#38BDF8",
          diagnoser: "#EF4444",
          improver:  "#7C3AED",
          deployer:  "#10B981",
        },

        /* ── Workspace surface tokens (light, default — 26-Jul-2026 warm reskin) ── */
        accent: {
          DEFAULT: "#F59E0B",   // amber-500
          light:   "#FBBF24",   // amber-400
          border:  "#FDE68A",   // amber-200
        },
        bg: {
          main:        "#FAF8F5",   // warm stone canvas
          sidebar:     "#F5F1EA",   // warm stone-100
          card:        "#ffffff",
          "card-hover":"#FAF8F5",
          input:       "#ffffff",
        },
        line: {
          DEFAULT: "#E7E5E4",   // stone-200
          accent:  "#FDE68A",   // amber-200
        },

        /* ── shadcn/ui neutral aliases — CSS-var-driven (ADR-010) ──
           24-Jul-2026: previously hardcoded to literal hex (bypassing the
           CSS-var tokens in globals.css entirely — see git history for the
           19-Jul-2026 comment documenting that exact bug for the dark
           theme). Wired to `hsl(var(--x))` so `bg-card`/`border`/`bg-muted`/
           `text-muted-foreground` (Card, Button outline, Input, Select,
           Dialog...) now genuinely respond to the `.dark` class toggle
           instead of being statically bound to one theme. */
        background:        "hsl(var(--background))",
        foreground:        "hsl(var(--foreground))",
        muted:              "hsl(var(--muted))",
        "muted-foreground": "hsl(var(--muted-foreground))",
        card:               "hsl(var(--card))",
        "card-foreground":  "hsl(var(--card-foreground))",
        border:             "hsl(var(--border))",
      },

      fontFamily: {
        /* Typography spec (26-Jul-2026 warm retheme, user-provided) -- Plus
           Jakarta Sans is the primary body & display font: all UI elements,
           headings, status indicators, buttons, card content, and analytics
           data. Monospace stays system-mono (JetBrains Mono) for technical
           metadata/hashes/IDs/JSON. Playfair Display (editorial/landing-page
           accent) is not yet wired -- add when a landing-page page is reskinned. */
        head: ["var(--font-plus-jakarta)", "system-ui", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        sans: ["var(--font-plus-jakarta)", "system-ui", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)","monospace"],  // all numbers/data
        /* SOT aliases */
        heading: ["var(--font-plus-jakarta)", "system-ui", "sans-serif"],
        body:    ["var(--font-plus-jakarta)", "system-ui", "sans-serif"],
        /* Retained for any not-yet-retheme'd screens still using font-space-grotesk / font-inter directly. */
        "space-grotesk": ["var(--font-space-grotesk)", "sans-serif"],
        inter: ["var(--font-inter)", "system-ui", "sans-serif"],
      },

      fontSize: {
        /* Doc 04 type scale — 6 steps */
        display: ["3.5rem",  { lineHeight: "1.1",  fontWeight: "700", letterSpacing: "-0.01em" }], // 56px
        h1:      ["2.625rem",{ lineHeight: "1.1",  fontWeight: "700", letterSpacing: "-0.01em" }], // 42px
        h2:      ["2rem",    { lineHeight: "1.3",  fontWeight: "700" }], // 32px
        h3:      ["1.5rem",  { lineHeight: "1.3",  fontWeight: "600" }], // 24px
        body:    ["1rem",    { lineHeight: "1.55", fontWeight: "400" }], // 16px
        caption: ["0.8125rem",{ lineHeight: "1.55",fontWeight: "400" }], // 13px
        /* Legacy aliases kept for existing components */
        "body-lg":  ["1rem",     { lineHeight: "1.5rem", fontWeight: "400" }],
        "body-sm":  ["0.875rem", { lineHeight: "1.25rem",fontWeight: "400" }],
        tiny:       ["0.6875rem",{ lineHeight: "1rem",   fontWeight: "400" }],
        kpi:        ["1.875rem", { lineHeight: "1",      fontWeight: "600" }], // 30px mono KPI
      },

      borderRadius: {
        sm: "8px",
        md: "16px",
        lg: "24px",
        xl: "32px",
      },

      maxWidth: {
        content: "1440px",
      },

      borderColor: {
        DEFAULT: "#E7E5E4",
      },

      transitionDuration: {
        "250": "250ms",
      },
    },
  },
  plugins: [],
};

export default config;
