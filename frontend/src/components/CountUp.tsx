import { useEffect, useRef, useState } from "react";
import { motionEnabled } from "../lib/motion";


/** Eases a number from 0 up to `value` once on mount, and between values
 *  afterwards. Used for the headline figures on a page's first paint - one
 *  deliberate moment, not a constant flicker - and skipped entirely for
 *  anyone with animations turned off (see lib/motion.ts). */
export function useCountUp(value: number, durationMs = 800): number {
  const [display, setDisplay] = useState(() => (motionEnabled() ? 0 : value));
  const fromRef = useRef(display);

  useEffect(() => {
    if (!motionEnabled()) {
      setDisplay(value);
      return;
    }
    const from = fromRef.current;
    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = t === 1 ? 1 : 1 - Math.pow(2, -10 * t); // ease-out-expo
      const next = from + (value - from) * eased;
      fromRef.current = next;
      setDisplay(next);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, durationMs]);

  return display;
}

export default function CountUp({
  value,
  decimals = 0,
  className,
}: {
  value: number;
  decimals?: number;
  className?: string;
}) {
  const shown = useCountUp(value);
  return <span className={className}>{shown.toLocaleString(undefined, { maximumFractionDigits: decimals, minimumFractionDigits: decimals })}</span>;
}
