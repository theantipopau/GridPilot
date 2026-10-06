import type { ReactNode } from "react";
import { cx } from "./cx";
import { Breadcrumb, type BreadcrumbItem } from "./Tabs";

interface PageHeaderProps {
  title: string;
  /** One sentence of what this screen is for - the audit kept these, they
   *  state honestly what is derived, inferred or not mutable. */
  description?: ReactNode;
  icon?: ReactNode;
  breadcrumb?: BreadcrumbItem[];
  /** Primary/secondary actions. Always right-aligned, always in the same
   *  vertical position regardless of description length. */
  actions?: ReactNode;
  /** Status chips under the description (counts, import state). */
  meta?: ReactNode;
  /** Rendering as h1 suppresses the duplicate when a shell already titles. */
  headingLevel?: 1 | 2;
  className?: string;
  /** Timetable and other full-height workspaces don't want the bottom margin. */
  compact?: boolean;
}

/** The one page-heading pattern: location, purpose, status, actions. */
export function PageHeader({
  title,
  description,
  icon,
  breadcrumb,
  actions,
  meta,
  headingLevel = 1,
  className,
  compact,
}: PageHeaderProps) {
  const Heading = headingLevel === 1 ? "h1" : "h2";
  return (
    <header
      className={cx(
        "flex flex-wrap items-start justify-between gap-x-6 gap-y-3",
        !compact && "mb-5",
        className,
      )}
    >
      <div className="min-w-0 flex-1">
        {breadcrumb && breadcrumb.length > 0 && <Breadcrumb items={breadcrumb} className="mb-1.5" />}
        <div className="flex min-w-0 items-start gap-3">
          {icon && (
            <span
              aria-hidden="true"
              className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-surface text-brand"
            >
              {icon}
            </span>
          )}
          <div className="min-w-0">
            <Heading className="text-page-title truncate">{title}</Heading>
            {description && <div className="mt-1 max-w-3xl text-body">{description}</div>}
            {meta && <div className="mt-2 flex flex-wrap items-center gap-1.5">{meta}</div>}
          </div>
        </div>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
