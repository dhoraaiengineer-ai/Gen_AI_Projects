"use client";

interface ScoreGaugeProps {
  score: number | null;
  label?: string;
}

function getColors(score: number | null): { stroke: string; text: string } {
  if (score === null) return { stroke: "#4B5563", text: "#9CA3AF" };
  if (score >= 0.85) return { stroke: "#10B981", text: "#10B981" };
  if (score >= 0.70) return { stroke: "#F59E0B", text: "#F59E0B" };
  return { stroke: "#EF4444", text: "#EF4444" };
}

export function ScoreGauge({ score, label }: ScoreGaugeProps): JSX.Element {
  const { stroke, text } = getColors(score);
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const progress = score !== null ? Math.max(0, Math.min(1, score)) : 0;
  const dashOffset = circumference * (1 - progress);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-28 h-28">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          {/* Track */}
          <circle
            cx="50" cy="50" r={radius}
            fill="none"
            stroke="#1F2937"
            strokeWidth="9"
          />
          {/* Progress arc */}
          <circle
            cx="50" cy="50" r={radius}
            fill="none"
            stroke={stroke}
            strokeWidth="9"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            style={{ transition: "stroke-dashoffset 0.7s ease-out, stroke 0.3s" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold tabular-nums" style={{ color: text }}>
            {score !== null ? (score * 100).toFixed(0) : "—"}
          </span>
          {score !== null && (
            <span className="text-[10px] text-text-3 tracking-wide">/100</span>
          )}
        </div>
      </div>
      {label && (
        <span className="text-xs text-text-3 text-center">{label}</span>
      )}
    </div>
  );
}
