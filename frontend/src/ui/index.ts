/** GridPilot design system - the single import surface for every primitive.
 *
 *  Rules of the system (see docs/design-system.md):
 *  - Colour comes from semantic tokens only (@theme in index.css); no raw
 *    palette values or hex in page components.
 *  - Status is never colour-alone: pair a tone with a word or a glyph.
 *  - Every overlay uses useFocusTrap (Escape, focus containment, restoration).
 *  - Type roles are the .text-* classes (page-title, section-title, body,
 *    table, label, meta, code); numbers get .nums for tabular figures.
 */
export { cx } from "./cx";

export { Button, IconButton } from "./Button";
export type { ButtonProps, ButtonSize, ButtonVariant } from "./Button";

export { Input, SearchInput, FieldShell } from "./Input";
export type { InputProps, SearchInputProps, FieldSize } from "./Input";

export { Select, Combobox } from "./Select";
export type { SelectOption, SelectProps, ComboboxProps } from "./Select";

export { Checkbox, RadioGroup, Switch } from "./Toggle";
export type { CheckboxProps, RadioGroupProps, RadioOption, SwitchProps } from "./Toggle";

export { Badge, StatusIndicator } from "./Badge";
export type { Tone, BadgeVariant, StatusIndicatorProps } from "./Badge";
export { toneForSeverity, reviewStateTone } from "./status";
export type { ReviewStateLabel } from "./status";

export { Alert } from "./Alert";
export { Tooltip, Popover } from "./Tooltip";
export { Dialog, Drawer } from "./Overlay";
export { useFocusTrap, useScrollLock } from "./useFocusTrap";
export { Tabs, Breadcrumb } from "./Tabs";
export type { TabItem, BreadcrumbItem } from "./Tabs";
export { PageHeader } from "./PageHeader";
export { EmptyState } from "./EmptyState";
export { Skeleton, SkeletonText } from "./Skeleton";
export { DataTable } from "./DataTable";
export type { DataTableColumn, SortState, SortDirection } from "./DataTable";
export { FilterBar } from "./FilterBar";
export type { FilterChip } from "./FilterBar";
export { Pagination } from "./Pagination";
export { SummaryMetric } from "./SummaryMetric";
export type { SummaryMetricProps } from "./SummaryMetric";
export { DetailSection } from "./DetailSection";
export { ConfirmAction } from "./ConfirmAction";
