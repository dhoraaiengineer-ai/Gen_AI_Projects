"use client";

export type AgentIconId =
  | "ingestion"
  | "query"
  | "builder"
  | "compressor"
  | "evaluator"
  | "deployer"
  | "observer"
  | "diagnoser"
  | "improver";

interface AgentIconProps {
  id: AgentIconId | string;
  className?: string;
  size?: number;
  glow?: boolean;
}

export function AgentRealisticIcon({ id, className = "w-6 h-6", size = 28, glow = true }: AgentIconProps) {
  const normId = id.toLowerCase();

  switch (normId) {
    case "ingestion":
      // Parse & Chunk: Database + Vector Matrix Scan
      return (
        <svg viewBox="0 0 48 48" width={size} height={size} className={className} fill="none">
          <defs>
            <linearGradient id="ingest-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#06b6d4" />
              <stop offset="100%" stopColor="#2563eb" />
            </linearGradient>
            <filter id="ingest-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor="#06b6d4" floodOpacity="0.6" />
            </filter>
          </defs>
          <g filter={glow ? "url(#ingest-glow)" : undefined}>
            <path d="M8 14C8 10.686 15.163 8 24 8C32.837 8 40 10.686 40 14V20C40 23.314 32.837 26 24 26C15.163 26 8 23.314 8 20V14Z" fill="url(#ingest-grad)" opacity="0.85" />
            <ellipse cx="24" cy="14" rx="16" ry="6" fill="#38bdf8" />
            <path d="M8 22C8 25.314 15.163 28 24 28C32.837 28 40 25.314 40 22V28C40 31.314 32.837 34 24 34C15.163 34 8 31.314 8 28V22Z" fill="url(#ingest-grad)" opacity="0.7" />
            <path d="M8 30C8 33.314 15.163 36 24 36C32.837 36 40 33.314 40 30V36C40 39.314 32.837 42 24 42C15.163 42 8 39.314 8 36V30Z" fill="url(#ingest-grad)" opacity="0.95" />
            <line x1="4" y1="26" x2="44" y2="26" stroke="#a5f3fc" strokeWidth="2.5" strokeDasharray="3 2" />
            <circle cx="24" cy="26" r="3" fill="#ffffff" />
          </g>
        </svg>
      );

    case "query":
      // HyDE Rewriter: Glowing Magnifier + Neural Expansion Waves
      return (
        <svg viewBox="0 0 48 48" width={size} height={size} className={className} fill="none">
          <defs>
            <linearGradient id="query-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#a855f7" />
              <stop offset="100%" stopColor="#6366f1" />
            </linearGradient>
            <filter id="query-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3.5" floodColor="#a855f7" floodOpacity="0.6" />
            </filter>
          </defs>
          <g filter={glow ? "url(#query-glow)" : undefined}>
            <circle cx="21" cy="21" r="17" stroke="#c084fc" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.6" />
            <circle cx="21" cy="21" r="13" stroke="url(#query-grad)" strokeWidth="3" fill="#1e1b4b" fillOpacity="0.8" />
            <circle cx="21" cy="21" r="5" fill="#f472b6" />
            <path d="M17 21H25M21 17V25" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
            <path d="M30 30L41 41" stroke="url(#query-grad)" strokeWidth="5" strokeLinecap="round" />
            <path d="M30 30L41 41" stroke="#e9d5ff" strokeWidth="2" strokeLinecap="round" />
          </g>
        </svg>
      );

    case "builder":
      // DAG Constructor: Holographic Graph Network
      return (
        <svg viewBox="0 0 48 48" width={size} height={size} className={className} fill="none">
          <defs>
            <linearGradient id="build-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#f59e0b" />
              <stop offset="100%" stopColor="#ea580c" />
            </linearGradient>
            <filter id="build-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3.5" floodColor="#f59e0b" floodOpacity="0.6" />
            </filter>
          </defs>
          <g filter={glow ? "url(#build-glow)" : undefined}>
            <line x1="24" y1="10" x2="10" y2="34" stroke="#fbbf24" strokeWidth="2.5" />
            <line x1="24" y1="10" x2="38" y2="34" stroke="#fbbf24" strokeWidth="2.5" />
            <line x1="10" y1="34" x2="38" y2="34" stroke="#f97316" strokeWidth="2.5" strokeDasharray="3 2" />
            <line x1="24" y1="10" x2="24" y2="26" stroke="#ffffff" strokeWidth="2" />
            <circle cx="24" cy="10" r="6" fill="url(#build-grad)" stroke="#fef3c7" strokeWidth="2" />
            <circle cx="10" cy="34" r="5" fill="url(#build-grad)" stroke="#fef3c7" strokeWidth="2" />
            <circle cx="38" cy="34" r="5" fill="url(#build-grad)" stroke="#fef3c7" strokeWidth="2" />
            <circle cx="24" cy="26" r="4" fill="#fbbf24" />
          </g>
        </svg>
      );

    case "compressor":
      // Token Squeezer: High-Density Singularity Vise
      return (
        <svg viewBox="0 0 48 48" width={size} height={size} className={className} fill="none">
          <defs>
            <linearGradient id="comp-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#f43f5e" />
              <stop offset="100%" stopColor="#be123c" />
            </linearGradient>
            <filter id="comp-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3.5" floodColor="#f43f5e" floodOpacity="0.6" />
            </filter>
          </defs>
          <g filter={glow ? "url(#comp-glow)" : undefined}>
            <rect x="8" y="8" width="32" height="7" rx="3" fill="url(#comp-grad)" stroke="#fda4af" strokeWidth="1.5" />
            <rect x="8" y="33" width="32" height="7" rx="3" fill="url(#comp-grad)" stroke="#fda4af" strokeWidth="1.5" />
            <path d="M16 15V33M32 15V33" stroke="#fb7185" strokeWidth="2" strokeDasharray="3 2" />
            <circle cx="24" cy="24" r="6" fill="#ffffff" />
            <circle cx="24" cy="24" r="10" stroke="#f43f5e" strokeWidth="1.5" opacity="0.8" />
          </g>
        </svg>
      );

    case "evaluator":
      // RAGAS Scorer: Precision Shield & Score Matrix
      return (
        <svg viewBox="0 0 48 48" width={size} height={size} className={className} fill="none">
          <defs>
            <linearGradient id="eval-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="#0d9488" />
            </linearGradient>
            <filter id="eval-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3.5" floodColor="#10b981" floodOpacity="0.6" />
            </filter>
          </defs>
          <g filter={glow ? "url(#eval-glow)" : undefined}>
            <path d="M24 6L38 12V22C38 31.5 32 39.5 24 43C16 39.5 10 31.5 10 22V12L24 6Z" fill="url(#eval-grad)" fillOpacity="0.85" stroke="#6ee7b7" strokeWidth="2" />
            <path d="M17 23L22 28L31 17" stroke="#ffffff" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
          </g>
        </svg>
      );

    case "deployer":
      // Canary Release: Rocket Thruster Launch Pod
      return (
        <svg viewBox="0 0 48 48" width={size} height={size} className={className} fill="none">
          <defs>
            <linearGradient id="dep-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" />
              <stop offset="100%" stopColor="#4f46e5" />
            </linearGradient>
            <filter id="dep-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3.5" floodColor="#38bdf8" floodOpacity="0.6" />
            </filter>
          </defs>
          <g filter={glow ? "url(#dep-glow)" : undefined}>
            <path d="M24 6C24 6 33 13 33 26C33 32 30 35 30 35H18C18 35 15 32 15 26C15 13 24 6 24 6Z" fill="url(#dep-grad)" stroke="#bae6fd" strokeWidth="2" />
            <circle cx="24" cy="20" r="4" fill="#0284c7" stroke="#ffffff" strokeWidth="1.5" />
            <path d="M15 28L8 35V38H16V34" fill="#2563eb" />
            <path d="M33 28L40 35V38H32V34" fill="#2563eb" />
            <path d="M20 36L24 44L28 36Z" fill="#f97316" />
            <path d="M22 36L24 41L26 36Z" fill="#fef08a" />
          </g>
        </svg>
      );

    case "observer":
      // Span Telemetry: Holographic Eye
      return (
        <svg viewBox="0 0 48 48" width={size} height={size} className={className} fill="none">
          <defs>
            <linearGradient id="obs-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#d946ef" />
              <stop offset="100%" stopColor="#9333ea" />
            </linearGradient>
            <filter id="obs-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3.5" floodColor="#d946ef" floodOpacity="0.6" />
            </filter>
          </defs>
          <g filter={glow ? "url(#obs-glow)" : undefined}>
            <path d="M6 24C6 24 13 10 24 10C35 10 42 24 42 24C42 24 35 38 24 38C13 38 6 24 6 24Z" fill="#1e1b4b" fillOpacity="0.8" stroke="url(#obs-grad)" strokeWidth="2.5" />
            <circle cx="24" cy="24" r="8" fill="url(#obs-grad)" stroke="#f0abfc" strokeWidth="2" />
            <circle cx="24" cy="24" r="3" fill="#ffffff" />
            <circle cx="26" cy="22" r="1.5" fill="#f0abfc" />
          </g>
        </svg>
      );

    case "diagnoser":
      // Root Cause AI: Neural Chip & ECG Diagnostic Wave
      return (
        <svg viewBox="0 0 48 48" width={size} height={size} className={className} fill="none">
          <defs>
            <linearGradient id="diag-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#14b8a6" />
              <stop offset="100%" stopColor="#059669" />
            </linearGradient>
            <filter id="diag-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3.5" floodColor="#14b8a6" floodOpacity="0.6" />
            </filter>
          </defs>
          <g filter={glow ? "url(#diag-glow)" : undefined}>
            <rect x="10" y="10" width="28" height="28" rx="6" fill="url(#diag-grad)" stroke="#99f6e4" strokeWidth="2" />
            <path d="M16 6V10M24 6V10M32 6V10M16 38V42M24 38V42M32 38V42M6 16H10M6 24H10M6 32H10M38 16H42M38 24H42M38 32H42" stroke="#5eead4" strokeWidth="2" strokeLinecap="round" />
            <path d="M14 24H19L22 17L26 31L29 21L31 24H34" stroke="#ffffff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          </g>
        </svg>
      );

    case "improver":
      // Auto-Tuning Engine: Turbo Neural Gear
      return (
        <svg viewBox="0 0 48 48" width={size} height={size} className={className} fill="none">
          <defs>
            <linearGradient id="imp-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#eab308" />
              <stop offset="100%" stopColor="#d97706" />
            </linearGradient>
            <filter id="imp-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3.5" floodColor="#eab308" floodOpacity="0.6" />
            </filter>
          </defs>
          <g filter={glow ? "url(#imp-glow)" : undefined}>
            <circle cx="24" cy="24" r="16" fill="none" stroke="url(#imp-grad)" strokeWidth="4" strokeDasharray="6 4" />
            <circle cx="24" cy="24" r="10" fill="#292524" stroke="#fef08a" strokeWidth="2" />
            <path d="M17 29L23 23L26 26L31 19" stroke="#facc15" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M26 19H31V24" stroke="#facc15" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          </g>
        </svg>
      );

    default:
      return (
        <svg viewBox="0 0 48 48" width={size} height={size} className={className} fill="none">
          <circle cx="24" cy="24" r="16" fill="#f97316" />
        </svg>
      );
  }
}
