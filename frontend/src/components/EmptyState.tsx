import type { ReactNode } from "react";

interface Props {
  icon: ReactNode;
  title: string;
  description?: string;
  tone?: "neutral" | "positive";
}

export default function EmptyState({ icon, title, description, tone = "neutral" }: Props) {
  const toneClasses =
    tone === "positive" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-slate-50 text-slate-500";
  const iconClasses = tone === "positive" ? "text-emerald-500" : "text-slate-300";

  return (
    <div className={`flex flex-col items-center gap-2 rounded-lg border border-dashed px-6 py-10 text-center ${toneClasses}`}>
      <div className={iconClasses}>{icon}</div>
      <p className="text-sm font-medium">{title}</p>
      {description && <p className="max-w-sm text-xs opacity-80">{description}</p>}
    </div>
  );
}
