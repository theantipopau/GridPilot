import type { ReactNode } from "react";
import { EmptyState as DesignSystemEmptyState } from "../ui/EmptyState";

interface Props {
  icon: ReactNode;
  title: string;
  description?: string;
  tone?: "neutral" | "positive";
  action?: ReactNode;
}

/** Legacy adapter over `ui/EmptyState` - same props, one implementation. */
export default function EmptyState(props: Props) {
  return <DesignSystemEmptyState {...props} />;
}
