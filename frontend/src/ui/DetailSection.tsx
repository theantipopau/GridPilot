import { useId, useState, type ReactNode } from "react";
import { cx } from "./cx";

interface DetailSectionProps {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  /** Collapsible for long entity inspectors; open by default so content is
   *  never hidden from a keyboard user who didn't ask for it. */
  collapsible?: boolean;
  defaultOpen?: boolean;
  /** Right-aligned count/summary shown in the header row. */
  aside?: ReactNode;
  className?: string;
  /** Heading level inside the section (page structure matters for AT). */
  headingLevel?: 2 | 3;
}

/** A titled block inside a page or inspector: consistent heading weight,
 *  consistent spacing, optional actions. Replaces the four different
 *  "section title" treatments the audit found. */
export function DetailSection({
  title,
  description,
  actions,
  children,
  collapsible,
  defaultOpen = true,
  aside,
  className,
  headingLevel = 3,
}: DetailSectionProps) {
  const id = useId();
  const [open, setOpen] = useState(defaultOpen);
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const isOpen = collapsible ? open : true;

  return (
    <section className={cx("rounded-lg border border-border bg-surface", className)}>
      <div
        className={cx(
          "flex items-start justify-between gap-3 px-4",
          collapsible ? "py-2.5" : "border-b border-border px-4 py-3",
          isOpen && collapsible && "border-b border-border",
        )}
      >
        <div className="min-w-0 flex-1">
          {collapsible ? (
            <button
              type="button"
              aria-expanded={isOpen}
              aria-controls={id}
              onClick={() => setOpen((v) => !v)}
              className="flex items-center gap-2 rounded text-left"
            >
              <svg
                viewBox="0 0 16 16"
                aria-hidden="true"
                className={cx(
                  "h-3.5 w-3.5 shrink-0 text-text-muted transition-transform duration-150",
                  isOpen && "rotate-90",
                )}
                fill="none"
              >
                <path d="m6 4 4 4-4 4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <Heading className="text-section-title">{title}</Heading>
            </button>
          ) : (
            <Heading className="text-section-title">{title}</Heading>
          )}
          {description && <div className="mt-0.5 text-meta">{description}</div>}
        </div>
        {aside && <div className="shrink-0 text-meta">{aside}</div>}
        {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
      </div>
      {isOpen && <div className="px-4 py-3">{children}</div>}
    </section>
  );
}
