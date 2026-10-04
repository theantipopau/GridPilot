import { useLayoutEffect, useRef } from "react";
import { motionEnabled } from "./motion";

const MAX_TRAVEL_PX = 360;

/** FLIP reordering for a vertical list: when `order` changes, each row
 *  that moved slides from where it was to where it now is, instead of the
 *  list snapping into its new order. The person changed the sort or the
 *  filter and the list shows *what moved*.
 *
 *  Usage: `const flipRef = useFlip(orderKey)`, then on each row
 *  `ref={flipRef(row.id)}`. The list container must be `position: relative`
 *  (rows are measured by offsetTop, which - unlike getBoundingClientRect -
 *  doesn't change as the page scrolls between renders). Rows that just
 *  appeared don't animate; neither does anything while animations
 *  are turned off (lib/motion.ts). */
export function useFlip(order: string) {
  const nodes = useRef(new Map<string, HTMLElement>());
  const previous = useRef(new Map<string, number>());

  useLayoutEffect(() => {
    const current = new Map<string, number>();
    nodes.current.forEach((el, key) => current.set(key, el.offsetTop));

    if (motionEnabled()) {
      nodes.current.forEach((el, key) => {
        const before = previous.current.get(key);
        const after = current.get(key);
        if (before === undefined || after === undefined || Math.abs(before - after) < 2) return;
        // A row that jumps across a long list would otherwise streak
        // thousands of pixels in a third of a second. Capping the distance
        // keeps a big re-sort legible: far-moving rows still glide, just
        // from nearby rather than from the other end of the list.
        const travel = Math.max(-MAX_TRAVEL_PX, Math.min(MAX_TRAVEL_PX, before - after));
        el.animate(
          [{ transform: `translateY(${travel}px)` }, { transform: "translateY(0)" }],
          { duration: 360, easing: "cubic-bezier(0.16, 1, 0.3, 1)" },
        );
      });
    }
    previous.current = current;
  }, [order]);

  return (key: string) => (el: HTMLElement | null) => {
    if (el) nodes.current.set(key, el);
    else nodes.current.delete(key);
  };
}
