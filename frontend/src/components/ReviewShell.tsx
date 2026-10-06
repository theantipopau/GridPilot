import type { ReactNode } from "react";
import { FilterBar, Input, PageHeader, Tabs, type FilterChip, type TabItem } from "../ui";
import { cx } from "../ui/cx";
import { useReviewerName } from "../lib/reviewer";

/** Shared furniture for every review surface (Findings, Composite Review,
 *  Room Constraints, Teacher Capabilities, Teaching Requirements):
 *  heading -> reviewer identity -> status tabs -> filter bar -> list.
 *  Same position, same spacing, same wording everywhere, so a queue learned
 *  once is a queue known everywhere (docs/ui-ux-audit.md §4). */
export interface ReviewShellProps<T extends string> {
  icon: ReactNode;
  title: string;
  description?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  tabs: TabItem<T>[];
  tabValue: T;
  onTabChange: (id: T) => void;
  /** Status-tab panel id, wired through to aria-controls. */
  panelId?: string;
  search?: ReactNode;
  chips?: FilterChip[];
  onClearAll?: () => void;
  /** Live result count shown right-aligned in the filter bar. */
  count?: ReactNode;
  /** Extra controls in the filter bar (sort, grouping). */
  controls?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function ReviewShell<T extends string>({
  icon,
  title,
  description,
  meta,
  actions,
  tabs,
  tabValue,
  onTabChange,
  panelId,
  search,
  chips,
  onClearAll,
  count,
  controls,
  children,
  className,
}: ReviewShellProps<T>) {
  return (
    <div className={cx("p-6", className)}>
      <PageHeader icon={icon} title={title} description={description} meta={meta} actions={actions} />
      <Tabs
        label={`${title} status`}
        tabs={tabs}
        value={tabValue}
        onChange={onTabChange}
        panelId={panelId}
        className="mb-3"
      />
      {(search || chips || controls || count) && (
        <FilterBar search={search} chips={chips} onClearAll={onClearAll} count={count} className="mb-3">
          {controls}
        </FilterBar>
      )}
      {children}
    </div>
  );
}

/** The one "reviewing as" input. Reads and writes the shared reviewer store,
 *  so a name typed on Findings is already there on Room Constraints, and the
 *  hint states where the name ends up (the audit trail). */
export function ReviewerField({ error, className }: { error?: string | null; className?: string }) {
  const [reviewer, setReviewer] = useReviewerName();
  return (
    <Input
      containerClassName={cx("w-56", className)}
      size="sm"
      label="Reviewing as"
      placeholder="Your name"
      value={reviewer}
      error={error ?? undefined}
      hint="Recorded in the audit trail"
      onChange={(e) => setReviewer(e.target.value)}
    />
  );
}
