"use client";

import { scoreBand, DEPLOY_GATE, HITL_LOWER } from "@/lib/score";

interface UnifiedScoreGaugeProps {
  score: number;
}

const RADIUS = 78;
const INNER_R = 64;
const CX = 100;
const CY = 100;
// Half-circle arc length (180° span = π × r)
const HALF_CIRC = Math.PI * RADIUS;

// score ∈ [0,1] → math angle in degrees (left=180°, top=90°, right=0°)
function scoreToAngle(s: number): number {
  return 180 - s * 180;
}

// Convert math angle + radius to SVG (x, y) — SVG y axis is flipped
function toSvg(angleDeg: number, r: number): { x: number; y: number } {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: CX + r * Math.cos(rad), y: CY - r * Math.sin(rad) };
}

const STROKE_COLOR: Record<ReturnType<typeof scoreBand>, string> = {
  deploy: "#10b981", // emerald-500
  hitl: "#f59e0b",  // amber-500
  retry: "#ef4444", // red-500
};

const BAND_LABEL: Record<ReturnType<typeof scoreBand>, string> = {
  deploy: "Production Ready",
  hitl: "HITL Required",
  retry: "Hard Block",
};

// Shared path: left → top → right (sweep=0 = counterclockwise = TOP half arc)
const ARC_PATH = `M ${CX - RADIUS} ${CY} A ${RADIUS} ${RADIUS} 0 0 0 ${CX + RADIUS} ${CY}`;

export function UnifiedScoreGauge({ score }: UnifiedScoreGaugeProps) {
  const band = scoreBand(score);
  const strokeColor = STROKE_COLOR[band];
  const filledArc = Math.max(0, Math.min(1, score)) * HALF_CIRC;

  // Tick positions for deployment gate (0.85) and HITL band (0.70)
  const gateOuter = toSvg(scoreToAngle(DEPLOY_GATE), RADIUS);
  const gateInner = toSvg(scoreToAngle(DEPLOY_GATE), INNER_R);
  const hitlOuter = toSvg(scoreToAngle(HITL_LOWER), RADIUS);
  const hitlInner = toSvg(scoreToAngle(HITL_LOWER), INNER_R);

  return (
    <div className="flex flex-col items-center">
      <svg
        viewBox="0 0 200 110"
        role="img"
        aria-label={`Unified Score gauge: ${Math.round(score * 100)}%, ${BAND_LABEL[band]}`}
        className="w-full max-w-[220px]"
      >
        {/* Track (full half-circle) */}
        <path
          d={ARC_PATH}
          fill="none"
          stroke="#1e293b"
          strokeWidth={14}
          strokeLinecap="round"
        />

        {/* Filled arc — grows from left (score=0) through top to right (score=1) */}
        <path
          d={ARC_PATH}
          fill="none"
          stroke={strokeColor}
          strokeWidth={14}
          strokeLinecap="round"
          strokeDasharray={`${filledArc} ${HALF_CIRC}`}
          className="motion-safe:transition-all motion-safe:duration-700"
        />

        {/* Deployment gate tick at 0.85 */}
        <line
          x1={gateInner.x} y1={gateInner.y}
          x2={gateOuter.x} y2={gateOuter.y}
          stroke="#10b981"
          strokeWidth={2}
          opacity={0.7}
        />
        {/* HITL threshold tick at 0.70 */}
        <line
          x1={hitlInner.x} y1={hitlInner.y}
          x2={hitlOuter.x} y2={hitlOuter.y}
          stroke="#f59e0b"
          strokeWidth={2}
          opacity={0.7}
        />

        {/* Score value — vertically centred in the arc's open space */}
        <text
          x={CX}
          y={CY - 18}
          textAnchor="middle"
          fontSize="30"
          fontWeight="700"
          fill={strokeColor}
          fontFamily="var(--font-jetbrains-mono, monospace)"
        >
          {Math.round(score * 100)}%
        </text>

        {/* Scale labels */}
        <text x={CX - RADIUS + 4} y={CY + 14} fontSize="8" fill="#475569" textAnchor="middle">0%</text>
        <text x={CX + RADIUS - 4} y={CY + 14} fontSize="8" fill="#475569" textAnchor="middle">100%</text>
      </svg>

      <p className="mt-1 text-sm font-semibold" style={{ color: strokeColor }}>
        {BAND_LABEL[band]}
      </p>
    </div>
  );
}
