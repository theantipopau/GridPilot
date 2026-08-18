import { useEffect, useState } from "react";

// docs/roadmap-v2.md 4.2.3: "Timetablers scanning the whole school want
// compact; someone reviewing one teacher wants comfortable. Currently one
// hard-coded density serves both badly." Persisted per-browser, not
// per-account - there's no user model here, just a local preference.
export type Density = "comfortable" | "compact";

const STORAGE_KEY = "gridpilot.density";

function readStored(): Density {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === "compact" ? "compact" : "comfortable";
}

export function useDensity(): [Density, (d: Density) => void] {
  const [density, setDensityState] = useState<Density>(readStored);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, density);
  }, [density]);

  return [density, setDensityState];
}
