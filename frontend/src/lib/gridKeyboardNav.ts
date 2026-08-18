import { useEffect, useRef, useState } from "react";

// docs/roadmap-v2.md 4.3: "Arrow-key cell movement and Enter to open the
// inspector would make the grid usable without a mouse - the thing that
// most distinguishes a professional data tool from a web page." Scoped
// per table (a week table in the timetable grids) rather than globally -
// each week is its own independent grid, same as Tab already treats them.
//
// Cells register themselves as (row, col) -> DOM node via registerCell;
// move() computes the next in-bounds position and imperatively focuses
// that node (native focus + native scroll-into-view, not a re-implemented
// substitute for either). Cells are expected to carry tabIndex={-1} so
// they're reachable via this imperative focus() but skipped by normal Tab
// order - only the grid's own wrapper is a Tab stop.
export interface GridFocus {
  r: number;
  c: number;
}

export function useGridKeyboardNav(rowCount: number, colCount: number) {
  const [focus, setFocus] = useState<GridFocus | null>(null);
  const cellRefs = useRef<(HTMLElement | null)[][]>([]);

  useEffect(() => {
    if (focus) cellRefs.current[focus.r]?.[focus.c]?.focus();
  }, [focus]);

  function registerCell(r: number, c: number, el: HTMLElement | null) {
    if (!cellRefs.current[r]) cellRefs.current[r] = [];
    cellRefs.current[r][c] = el;
  }

  function move(key: string): GridFocus | null {
    if (rowCount === 0 || colCount === 0) return null;
    const current = focus ?? { r: 0, c: 0 };
    let { r, c } = current;
    if (key === "ArrowUp") r = Math.max(0, r - 1);
    else if (key === "ArrowDown") r = Math.min(rowCount - 1, r + 1);
    else if (key === "ArrowLeft") c = Math.max(0, c - 1);
    else if (key === "ArrowRight") c = Math.min(colCount - 1, c + 1);
    else return null;
    const next = { r, c };
    setFocus(next);
    return next;
  }

  // Tabbing into the grid for the first time (or clicking it without
  // clicking a specific cell) starts keyboard navigation at (0, 0)
  // instead of leaving focus in limbo until the first arrow key.
  function focusDefault() {
    setFocus((f) => f ?? { r: 0, c: 0 });
  }

  return { focus, setFocus, registerCell, move, focusDefault };
}
