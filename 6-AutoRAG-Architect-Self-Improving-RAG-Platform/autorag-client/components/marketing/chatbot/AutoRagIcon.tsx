"use client";

interface AutoRagIconProps {
  size?: number;
  thinking?: boolean;
  showNotificationBadge?: boolean;
  showGreeting?: boolean;
  greetingText?: string;
  className?: string;
}

/**
 * Squircle-framed AutoRAG assistant avatar: a stylized human bust
 * (illustrated, not a photo) on the same gradient canvas/interaction
 * pattern used everywhere else (chatbot header, launcher, Hero CTA).
 */
export function AutoRagIcon({
  size = 44,
  thinking = false,
  showNotificationBadge = false,
  showGreeting = false,
  greetingText = "Hi, I'm AIRA — your AI assistant",
  className = "",
}: AutoRagIconProps) {
  return (
    // Icon and greeting label share one centered flex column, anchored as a
    // single unit, so the icon is never off-center relative to the (wider)
    // label below it -- and both stay fully on-screen together.
    <div className={`inline-flex flex-col items-center gap-2 ${className}`}>
      <div
        className="relative shrink-0 transition-transform duration-200 ease-out hover:scale-[1.03] hover:-translate-y-0.5 active:scale-[0.96]"
        style={{ width: size, height: size }}
      >
      <svg
        width={size}
        height={size}
        viewBox="0 0 64 64"
        className={thinking ? "animate-pulse" : ""}
        style={{ filter: "drop-shadow(0 0 10px rgba(249, 115, 22, 0.35))" }}
      >
        <defs>
          <linearGradient id="autorag-icon-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FFB347" />
            <stop offset="100%" stopColor="#F97316" />
          </linearGradient>
          <clipPath id="autorag-icon-clip">
            <rect x="1" y="1" width="62" height="62" rx="19" />
          </clipPath>
        </defs>

        {/* Squircle canvas */}
        <rect x="1" y="1" width="62" height="62" rx="19" fill="url(#autorag-icon-grad)" />

        {/* Stylized human bust avatar, clipped to the squircle */}
        <g clipPath="url(#autorag-icon-clip)">
          {/* Shoulders, tapering into a visible neck rather than a floating head */}
          <ellipse cx="32" cy="64" rx="17" ry="14" fill="white" fillOpacity="0.95" />
          <path d="M27 34 L26 42 Q32 46 38 42 L37 34 Z" fill="white" fillOpacity="0.95" />

          {/* Head */}
          <circle cx="32" cy="25" r="10" fill="white" fillOpacity="0.95" className={thinking ? "animate-pulse" : ""} />
          {/* Hairline, for a human (not android) silhouette */}
          <path d="M22.3 23 A9.7 9.7 0 0 1 41.7 23 Q37 18 32 18 Q27 18 22.3 23 Z" fill="#3B2A1E" fillOpacity="0.85" />

          {/* Face: eyes + a calm smile */}
          <circle cx="28" cy="25" r="1.3" fill="#F97316" />
          <circle cx="36" cy="25" r="1.3" fill="#F97316" />
          <path d="M27.5 30 q4.5 3.5 9 0" fill="none" stroke="#F97316" strokeWidth="1.4" strokeLinecap="round" />
        </g>

        {/* Futuristic HUD ring + orbiting sensor nodes around the head */}
        <circle cx="32" cy="25" r="15" fill="none" stroke="#FDE7CE" strokeOpacity="0.65" strokeWidth="1" strokeDasharray="1.5 3" className={thinking ? "animate-spin-slow" : ""} />
        <circle cx="47" cy="25" r="1.6" fill="#FDE7CE" fillOpacity="0.9" />
        <circle cx="17" cy="25" r="1.2" fill="#FDE7CE" fillOpacity="0.7" />

        {/* Thinking indicator ring around the head */}
        {thinking && <circle cx="32" cy="25" r="14" fill="none" stroke="white" strokeOpacity="0.5" strokeWidth="1.5" className="animate-ping" />}
      </svg>

        {showNotificationBadge && (
          <span className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-orange-500 border-2 border-slate-950 animate-pulse" />
        )}
      </div>

      {showGreeting && (
        <div className="w-36 max-w-[55vw] px-2.5 py-1.5 rounded-xl bg-slate-900/85 backdrop-blur-sm text-[11px] font-semibold text-white text-center leading-snug break-words shadow-lg animate-fade-in-up">
          {greetingText}
        </div>
      )}
    </div>
  );
}
