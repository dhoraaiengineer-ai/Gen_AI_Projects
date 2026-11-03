interface AutoRagLogoProps {
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
  showTagline?: boolean;
  /** 'light' for a light background, 'dark' for a dark background (e.g. the sidebar). */
  variant?: "light" | "dark";
}

/**
 * Brand mark + wordmark (26-Jul-2026, ported from site_design/AutoRagLogo.tsx)
 * -- theme-aware SVG replacing the static /AutoRAG_logo.png, which baked
 * "Auto" in dark navy directly into the raster image and went invisible once
 * the sidebar chrome reverted to dark (site_design reference rollout).
 */
export function AutoRagLogoMark({ className = "", size = 42 }: { className?: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 160 160"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 ${className}`}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="navyLegGrad" x1="20" y1="20" x2="80" y2="140" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#1E3A8A" />
          <stop offset="50%" stopColor="#0F172A" />
          <stop offset="100%" stopColor="#020617" />
        </linearGradient>
        <linearGradient id="circuitGrad" x1="0" y1="0" x2="50" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38BDF8" />
          <stop offset="100%" stopColor="#0284C7" />
        </linearGradient>
        <linearGradient id="orangeSwooshGrad" x1="50" y1="120" x2="110" y2="20" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#FF7A00" />
          <stop offset="60%" stopColor="#F97316" />
          <stop offset="100%" stopColor="#C2410C" />
        </linearGradient>
        <linearGradient id="chartBlueGrad" x1="0" y1="0" x2="0" y2="20" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38BDF8" />
          <stop offset="100%" stopColor="#0284C7" />
        </linearGradient>
        <linearGradient id="chartOrangeGrad" x1="0" y1="0" x2="0" y2="20" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#FB923C" />
          <stop offset="100%" stopColor="#EA580C" />
        </linearGradient>
        <filter id="markShadow" x="-10%" y="-10%" width="120%" height="120%">
          <feDropShadow dx="0" dy="2" stdDeviation="2.5" floodColor="#0F172A" floodOpacity="0.15" />
        </filter>
      </defs>

      <g filter="url(#markShadow)">
        <path d="M 38 42 L 28 42 L 20 36 L 12 36" stroke="url(#circuitGrad)" strokeWidth="3" strokeLinecap="round" />
        <circle cx="10" cy="36" r="3.5" fill="#0284C7" stroke="#FFFFFF" strokeWidth="1" />
        <path d="M 34 56 L 22 56 L 16 50 L 8 50" stroke="url(#circuitGrad)" strokeWidth="3" strokeLinecap="round" />
        <circle cx="6" cy="50" r="3.5" fill="#0284C7" stroke="#FFFFFF" strokeWidth="1" />
        <path d="M 30 70 L 18 70" stroke="url(#circuitGrad)" strokeWidth="3" strokeLinecap="round" />
        <circle cx="14" cy="70" r="3.5" fill="#0284C7" stroke="#FFFFFF" strokeWidth="1" />
        <path d="M 28 84 L 18 84 L 12 90 L 6 90" stroke="url(#circuitGrad)" strokeWidth="3" strokeLinecap="round" />
        <circle cx="4" cy="90" r="3.5" fill="#0284C7" stroke="#FFFFFF" strokeWidth="1" />
        <path d="M 26 98 L 20 98 L 14 104 L 10 104" stroke="url(#circuitGrad)" strokeWidth="3" strokeLinecap="round" />
        <circle cx="8" cy="104" r="3.5" fill="#0284C7" stroke="#FFFFFF" strokeWidth="1" />

        <path d="M 68 18 L 32 108 L 48 108 L 62 68 L 74 68 L 82 48 L 68 18 Z" fill="url(#navyLegGrad)" />
        <path d="M 68 18 L 48 108 L 32 108 L 68 18 Z" fill="#1E293B" opacity="0.3" />
        <path
          d="M 68 18 L 84 18 C 96 40, 106 65, 116 108 L 96 108 C 88 80, 78 58, 62 48 C 50 40, 36 68, 54 108 L 36 108 C 22 68, 48 28, 68 18 Z"
          fill="url(#orangeSwooshGrad)"
        />
        <path d="M 46 76 C 60 58, 80 50, 104 54 C 84 66, 68 82, 54 108 L 46 76 Z" fill="#FF7A00" />

        <g transform="translate(94, 18)">
          <path
            d="M 2 2 L 26 2 L 36 12 L 36 44 C 36 46, 34 48, 32 48 L 2 48 C 0 48, -2 46, -2 44 L -2 4 C -2 2, 0 2, 2 2 Z"
            fill="#0F172A"
          />
          <path d="M 26 2 L 26 12 L 36 12 Z" fill="#334155" />
          <line x1="4" y1="18" x2="22" y2="18" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" />
          <line x1="4" y1="26" x2="26" y2="26" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" />
          <line x1="4" y1="34" x2="18" y2="34" stroke="#F97316" strokeWidth="2.5" strokeLinecap="round" />
        </g>

        <g transform="translate(102, 58)">
          <path d="M 26 26 L 38 38" stroke="#0F172A" strokeWidth="6" strokeLinecap="round" />
          <circle cx="16" cy="16" r="16" fill="#FFFFFF" stroke="#0F172A" strokeWidth="4" />
          <rect x="6" y="20" width="3.5" height="5" rx="1" fill="url(#chartBlueGrad)" />
          <rect x="11" y="16" width="3.5" height="9" rx="1" fill="url(#chartBlueGrad)" />
          <rect x="16" y="11" width="3.5" height="14" rx="1" fill="url(#chartOrangeGrad)" />
          <rect x="21" y="7" width="3.5" height="18" rx="1" fill="url(#chartOrangeGrad)" />
        </g>
      </g>
    </svg>
  );
}

export function AutoRagLogo({ className = "", size = "md", showTagline = true, variant = "light" }: AutoRagLogoProps) {
  const pixelSize = size === "sm" ? 32 : size === "md" ? 42 : size === "lg" ? 56 : 72;
  const autoTextColor = variant === "dark" ? "text-white" : "text-[#0F172A]";
  const subtextColor = variant === "dark" ? "text-slate-300" : "text-slate-700";

  return (
    <div className={`inline-flex flex-col items-start ${className}`}>
      <div className="flex items-center gap-3">
        <AutoRagLogoMark size={pixelSize} />
        <div className="flex flex-col justify-center">
          <div className="flex items-center leading-none tracking-tight font-black">
            <span
              className={`font-black tracking-tighter ${autoTextColor}`}
              style={{ fontSize: `${pixelSize * 0.72}px` }}
            >
              Auto
            </span>
            <span
              className="bg-gradient-to-r from-orange-500 via-amber-500 to-orange-600 bg-clip-text text-transparent font-black tracking-tight"
              style={{ fontSize: `${pixelSize * 0.72}px` }}
            >
              RAG
            </span>
          </div>

          {showTagline && size !== "sm" && (
            <div className="mt-1 flex items-center gap-1.5">
              <span className="h-[1.5px] w-3.5 bg-sky-500" />
              <span className={`text-[8px] font-black uppercase tracking-widest sm:text-[9.5px] ${subtextColor}`}>
                Self-Improving RAG Platform
              </span>
              <span className="h-[1.5px] w-3.5 bg-orange-500" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
