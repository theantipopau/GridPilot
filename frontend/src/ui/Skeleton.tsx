import { cx } from "./cx";

interface SkeletonProps {
  className?: string;
  /** Inline width for text lines; otherwise fills its container. */
  width?: string;
  height?: string;
  radius?: string;
  /** Stagger index so a stack of lines shimmers in sequence, not in unison. */
  delay?: number;
}

/** Shimmering placeholder shaped like the content that is coming, so the
 *  layout does not jump when real data lands. Always decorative:
 *  the live region that announces loading sits beside it (see LoadingState). */
export function Skeleton({ className, width, height, radius, delay = 0 }: SkeletonProps) {
  return (
    <span
      aria-hidden="true"
      className={cx("skeleton block", className)}
      style={{
        width,
        height,
        borderRadius: radius,
        animationDelay: delay ? `${delay}ms` : undefined,
      }}
    />
  );
}

interface SkeletonTextProps {
  lines?: number;
  className?: string;
  /** Width of the last (partial) line, e.g. "60%". */
  lastLineWidth?: string;
}

export function SkeletonText({ lines = 3, className, lastLineWidth = "65%" }: SkeletonTextProps) {
  return (
    <span className={cx("flex flex-col gap-2", className)} aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton
          key={i}
          height="0.75rem"
          width={i === lines - 1 ? lastLineWidth : "100%"}
          radius="4px"
          delay={i * 80}
        />
      ))}
    </span>
  );
}
