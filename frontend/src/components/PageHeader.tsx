import type { ReactNode } from "react";
import { PageHeader as DesignSystemPageHeader } from "../ui/PageHeader";

interface Props {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  /** Kept as `action` (singular) so every existing page compiles unchanged. */
  action?: ReactNode;
  meta?: ReactNode;
  breadcrumb?: { label: string; onClick?: () => void }[];
  headingLevel?: 1 | 2;
  compact?: boolean;
}

/** Legacy adapter: pages import `components/PageHeader`, the markup comes from
 *  `ui/PageHeader`. One heading pattern everywhere without touching fifteen
 *  pages at once - the shell phase's rule (docs/ui-ux-implementation-plan.md). */
export default function PageHeader(props: Props) {
  const { action, ...rest } = props;
  return <DesignSystemPageHeader {...rest} actions={action} />;
}
