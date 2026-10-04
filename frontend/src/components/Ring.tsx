import { useEffect, useState } from "react";

interface Props {
  percent: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
  trackColor?: string;
}

export default function Ring({ percent, size = 56, strokeWidth = 6, color = "#0284c7", trackColor = "#e2e8f0" }: Props) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, percent));

  // Starts empty and sweeps to its value on mount (a CSS transition on the
  // dash offset) - the ring "fills" once, in step with the count-up beside
  // it, and re-sweeps smoothly if the value later changes.
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setShown(clamped));
    return () => cancelAnimationFrame(frame);
  }, [clamped]);
  const offset = circumference * (1 - shown / 100);

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" role="img" aria-label={`${clamped}%`}>
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={trackColor} strokeWidth={strokeWidth} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        style={{ transition: "stroke-dashoffset 900ms var(--ease-out-expo)" }}
      />
    </svg>
  );
}
