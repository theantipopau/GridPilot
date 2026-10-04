import { setMotionPreference, systemReducesMotion, useMotionEnabled, useMotionPreference } from "../lib/motion";

// Animations default to the operating system's setting, but Windows quietly
// turns animation effects off on many managed and remote desktops - so this
// is a visible switch rather than something buried, and it says *why* it's
// off when the system is the reason.
export default function MotionToggle() {
  const enabled = useMotionEnabled();
  const preference = useMotionPreference();
  const offBySystem = !enabled && preference === "system" && systemReducesMotion();

  return (
    <div className="mb-3">
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        onClick={() => setMotionPreference(enabled ? "off" : "on")}
        className="flex w-full items-center justify-between rounded-md px-1 py-1 text-sm text-slate-600 hover:text-slate-900"
        title={
          offBySystem
            ? "Your system is set to reduce motion, so animations are off. Click to turn them on for GridPilot."
            : "Turn interface animations on or off. Defaults to your system setting."
        }
      >
        <span>Animations</span>
        <span
          aria-hidden="true"
          className={`relative h-[18px] w-8 rounded-full transition-colors duration-200 ${enabled ? "bg-sky-600" : "bg-slate-300"}`}
        >
          <span
            className={`absolute top-0.5 left-0.5 h-[14px] w-[14px] rounded-full bg-white shadow-sm transition-transform duration-200 ease-[var(--ease-out-expo)] ${
              enabled ? "translate-x-[14px]" : ""
            }`}
          />
        </span>
      </button>
      {offBySystem && <p className="px-1 text-[11px] leading-tight text-ink-muted">Off - your system asks for reduced motion.</p>}
    </div>
  );
}
