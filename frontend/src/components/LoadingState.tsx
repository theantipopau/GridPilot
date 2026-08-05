import { IconSpinner } from "./icons";

export default function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-2 text-slate-400">
      <IconSpinner className="h-6 w-6" />
      <p className="text-sm">{label}</p>
    </div>
  );
}
