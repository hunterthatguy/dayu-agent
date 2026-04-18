import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface StatusBadgeProps {
  state: "pending" | "running" | "succeeded" | "failed" | "skipped" | string;
  className?: string;
  children?: ReactNode;
}

const STATE_CLASSES: Record<string, string> = {
  pending: "status-pending",
  running: "status-running",
  succeeded: "status-succeeded",
  failed: "status-failed",
  skipped: "status-skipped",
};

const STATE_LABELS: Record<string, string> = {
  pending: "等待",
  running: "运行中",
  succeeded: "完成",
  failed: "失败",
  skipped: "跳过",
};

export default function StatusBadge({
  state,
  className,
  children,
}: StatusBadgeProps) {
  const cls = STATE_CLASSES[state] ?? "status-pending";
  const label = STATE_LABELS[state] ?? state;

  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium",
        cls,
        className,
      )}
    >
      {children ?? label}
    </span>
  );
}