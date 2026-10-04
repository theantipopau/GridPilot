import gridPilotLogo from "../assets/gridpilot-logo.png";

interface Props {
  label?: string;
  /** "page" (default) sketches the shape of a typical page inside the app
   *  shell; "screen" is for before the shell exists (first paint, before
   *  anything is imported). */
  variant?: "page" | "screen";
}

// A skeleton shaped like the page that's coming - header, a row of cards,
// a list - rather than a spinner over blank space, so the layout doesn't
// jump when the data lands. The label stays available to screen readers.
export default function LoadingState({ label = "Loading…", variant = "page" }: Props) {
  if (variant === "screen") {
    return (
      <div role="status" className="flex min-h-screen flex-col items-center justify-center gap-3 bg-slate-50">
        <img src={gridPilotLogo} alt="" className="h-9 w-auto animate-pulse" />
        <p className="text-sm text-ink-muted">{label}</p>
      </div>
    );
  }

  return (
    <div role="status" aria-live="polite" className="p-6">
      <span className="sr-only">{label}</span>
      <div className="mb-6 flex items-start gap-3">
        <div className="skeleton h-9 w-9 shrink-0" />
        <div className="flex flex-col gap-2 pt-1">
          <div className="skeleton h-4 w-40" />
          <div className="skeleton h-3 w-80 max-w-full" />
        </div>
      </div>
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton h-24" style={{ animationDelay: `${i * 90}ms` }} />
        ))}
      </div>
      <div className="flex flex-col gap-2">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="skeleton h-12" style={{ animationDelay: `${i * 90}ms` }} />
        ))}
      </div>
    </div>
  );
}
