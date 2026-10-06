import { Switch } from "../ui/Toggle";
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
    <div className="mb-2">
      <Switch
        label="Animations"
        checked={enabled}
        onChange={(next) => setMotionPreference(next ? "on" : "off")}
        title={
          offBySystem
            ? "Your system is set to reduce motion, so animations are off. Click to turn them on for GridPilot."
            : "Turn interface animations on or off. Defaults to your system setting."
        }
      />
      {offBySystem && <p className="px-1.5 text-[11px] leading-tight text-text-muted">Off - your system asks for reduced motion.</p>}
    </div>
  );
}
